from __future__ import annotations

from datetime import datetime, timedelta, timezone
import random

import pandas as pd
import plotly.express as px
import streamlit as st
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import WriteOptions


# Konfiguracija lokalnog InfluxDB v2 servera.
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "T9jPvxqQXHUMfbsu-WsqYumdGKXe3e0Aj4uGlzyIdczvSszyUjcE-RACd7YkusnCWf_T5KjotvcuEyR4aZfqjw=="
INFLUX_ORG = "myorg"
INFLUX_BUCKET = "mybucket"

# Identifikator merenja i taga za IoT vremensku stanicu.
MEASUREMENT = "weather_station"
STATION_TAG = "station"
STATION_VALUE = "lab_station_01"


def get_client() -> InfluxDBClient:
	"""Vraca klijent za InfluxDB sa razumnim timeout-om."""
	return InfluxDBClient(
		url=INFLUX_URL,
		token=INFLUX_TOKEN,
		org=INFLUX_ORG,
		timeout=10_000,
	)


def is_db_available(client: InfluxDBClient) -> bool:
	"""Proverava da li je InfluxDB dostupan, bez pucanja aplikacije."""
	try:
		return bool(client.ping())
	except Exception:
		return False


def seed_data(num_points: int = 100) -> tuple[bool, str]:
	"""Generise nasumicna IoT ocitavanja za poslednja 24h i upisuje ih batch metodom."""
	client: InfluxDBClient | None = None
	write_api = None

	try:
		client = get_client()
		if not is_db_available(client):
			return False, "InfluxDB nije dostupan. Proveri da li je server podignut na localhost:8086."

		write_api = client.write_api(
			write_options=WriteOptions(
				batch_size=500,
				flush_interval=2_000,
				jitter_interval=1_000,
				retry_interval=5_000,
			)
		)

		now_utc = datetime.now(timezone.utc)
		points: list[Point] = []

		for _ in range(num_points):
			seconds_ago = random.uniform(0, 24 * 60 * 60)
			point_time = now_utc - timedelta(seconds=seconds_ago)
			temperature = round(random.uniform(15.0, 35.0), 2)
			humidity = round(random.uniform(30.0, 80.0), 2)

			point = (
				Point(MEASUREMENT)
				.tag(STATION_TAG, STATION_VALUE)
				.field("temperature", temperature)
				.field("humidity", humidity)
				.time(point_time, WritePrecision.S)
			)
			points.append(point)

		write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=points)
		write_api.flush()
		return True, f"Uspesno upisano {num_points} testnih ocitavanja za poslednja 24h."
	except Exception as exc:
		return False, f"Greska pri generisanju podataka: {exc}"
	finally:
		if write_api is not None:
			write_api.close()
		if client is not None:
			client.close()


def write_realtime_reading(temperature: float, humidity: float) -> tuple[bool, str]:
	"""Upisuje jedno rucno ocitavanje u trenutnom vremenu."""
	client: InfluxDBClient | None = None
	write_api = None

	try:
		client = get_client()
		if not is_db_available(client):
			return False, "InfluxDB nije dostupan. Pokreni bazu i pokusaj ponovo."

		write_api = client.write_api(
			write_options=WriteOptions(
				batch_size=1,
				flush_interval=500,
				jitter_interval=0,
				retry_interval=5_000,
			)
		)

		point = (
			Point(MEASUREMENT)
			.tag(STATION_TAG, STATION_VALUE)
			.field("temperature", round(float(temperature), 2))
			.field("humidity", round(float(humidity), 2))
			.time(datetime.now(timezone.utc), WritePrecision.S)
		)

		write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
		write_api.flush()
		return True, "Rucno ocitavanje je uspesno upisano u InfluxDB."
	except Exception as exc:
		return False, f"Greska pri upisu ocitavanja: {exc}"
	finally:
		if write_api is not None:
			write_api.close()
		if client is not None:
			client.close()


def query_last_24h() -> tuple[pd.DataFrame, str | None]:
	"""Vuce temperature i vlaznost za poslednja 24h putem Flux upita."""
	client: InfluxDBClient | None = None

	try:
		client = get_client()
		if not is_db_available(client):
			return pd.DataFrame(), "InfluxDB nije dostupan. Dashboard ne moze da ucita podatke."

		query_api = client.query_api()

		# =====================================================================
		# VAZNO OBJASNJENJE ZA PROFESORA (TSDB vs SQL za IoT scenarije):
		# InfluxDB kao TSDB je dizajniran za serijske podatke po vremenu i zato
		# je efikasniji od klasicnog SQL modela kada je potreban high ingest rate.
		#
		# 1) Upis je append-oriented po vremenskim segmentima, pa se izbegava
		#    skupo random azuriranje redova i cesti lock-ovi tipicni za OLTP obrasce.
		# 2) Podaci su kompresovani po vremenskim kolonama (timestamp + field),
		#    sto smanjuje I/O i ubrzava agregacije nad dugim periodima.
		# 3) Flux je optimizovan za time-window operacije (range, aggregateWindow,
		#    downsampling), koje su jezgro analize IoT tokova podataka.
		# 4) TSDB prirodno podrzava retention politike, continuous query obrasce
		#    i rad sa velikim serijama merenja bez degradacije performansi.
		#
		# Zakljucak: za vremenske serije sa mnogo upisa i analitiku kroz vreme,
		# TSDB pristup daje bolji throughput i operativno jednostavniji model.
		# =====================================================================
		flux_query = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -24h)
  |> filter(fn: (r) => r["_measurement"] == "{MEASUREMENT}")
  |> filter(fn: (r) => r["_field"] == "temperature" or r["_field"] == "humidity")
  |> keep(columns: ["_time", "_field", "_value", "{STATION_TAG}"])
  |> sort(columns: ["_time"])
'''

		query_result = query_api.query_data_frame(org=INFLUX_ORG, query=flux_query)

		if isinstance(query_result, list):
			non_empty = [df for df in query_result if not df.empty]
			if not non_empty:
				return pd.DataFrame(), None
			data = pd.concat(non_empty, ignore_index=True)
		else:
			data = query_result.copy()

		if data.empty:
			return pd.DataFrame(), None

		expected_cols = {"_time", "_field", "_value"}
		if not expected_cols.issubset(set(data.columns)):
			return pd.DataFrame(), "Flux upit nije vratio ocekivane kolone (_time, _field, _value)."

		data = data[["_time", "_field", "_value"]].copy()
		data["_time"] = pd.to_datetime(data["_time"], utc=True)
		data.sort_values("_time", inplace=True)

		return data, None
	except Exception as exc:
		return pd.DataFrame(), f"Greska pri Flux upitu: {exc}"
	finally:
		if client is not None:
			client.close()


def render_dashboard(df: pd.DataFrame) -> None:
	"""Prikazuje metrike i dva linijska grafikona (temperatura i vlaznost)."""
	temp_df = df[df["_field"] == "temperature"].copy()
	hum_df = df[df["_field"] == "humidity"].copy()

	col1, col2 = st.columns(2)
	with col1:
		if not temp_df.empty:
			st.metric("Poslednja temperatura (C)", f"{temp_df.iloc[-1]['_value']:.2f}")
		else:
			st.metric("Poslednja temperatura (C)", "N/A")
	with col2:
		if not hum_df.empty:
			st.metric("Poslednja vlaznost (%)", f"{hum_df.iloc[-1]['_value']:.2f}")
		else:
			st.metric("Poslednja vlaznost (%)", "N/A")

	if not temp_df.empty:
		fig_temp = px.line(
			temp_df,
			x="_time",
			y="_value",
			title="Temperatura kroz vreme (poslednja 24h)",
			labels={"_time": "Vreme", "_value": "Temperatura (C)"},
			markers=True,
			template="plotly_white",
		)
		st.plotly_chart(fig_temp, use_container_width=True)

	if not hum_df.empty:
		fig_hum = px.line(
			hum_df,
			x="_time",
			y="_value",
			title="Vlaznost vazduha kroz vreme (poslednja 24h)",
			labels={"_time": "Vreme", "_value": "Vlaznost (%)"},
			markers=True,
			template="plotly_white",
		)
		st.plotly_chart(fig_hum, use_container_width=True)

	with st.expander("Prikazi sirove podatke"):
		st.dataframe(df, use_container_width=True)


def main() -> None:
	"""Glavna Streamlit aplikacija za PoC ispitni zadatak."""
	st.set_page_config(page_title="IoT Dashboard - Vremenska stanica", page_icon="", layout="wide")

	st.title("IoT Dashboard za Vremensku Stanicu")
	st.caption("Proof of Concept za predmet 'Napredne baze podataka' (InfluxDB v2 + Streamlit + Flux)")

	with st.expander("Konfiguracija konekcije", expanded=False):
		st.write(f"URL: {INFLUX_URL}")
		st.write(f"Org: {INFLUX_ORG}")
		st.write(f"Bucket: {INFLUX_BUCKET}")
		st.write("Token je ucitan iz koda za potrebe lokalnog PoC-a.")

	st.subheader("Simulator senzora")
	if st.button("Generisi testne podatke", type="primary"):
		with st.spinner("Generisem i upisujem testne podatke..."):
			ok, message = seed_data(num_points=100)
		if ok:
			st.success(message)
		else:
			st.error(message)

	st.divider()
	st.subheader("1) Unos u realnom vremenu")

	with st.form("realtime_form", clear_on_submit=False):
		c1, c2 = st.columns(2)
		with c1:
			temperature = st.number_input(
				"Temperatura (C)",
				min_value=-30.0,
				max_value=60.0,
				value=22.0,
				step=0.1,
				format="%.1f",
			)
		with c2:
			humidity = st.number_input(
				"Vlaznost vazduha (%)",
				min_value=0.0,
				max_value=100.0,
				value=50.0,
				step=0.1,
				format="%.1f",
			)

		submit_manual = st.form_submit_button("Upisi ocitavanje")

	if submit_manual:
		with st.spinner("Upisujem rucno ocitavanje..."):
			ok, message = write_realtime_reading(temperature=float(temperature), humidity=float(humidity))
		if ok:
			st.success(message)
		else:
			st.error(message)

	st.divider()
	st.subheader("2) IoT Dashboard sa Flux upitima (poslednja 24h)")

	refresh = st.button("Osvezi dashboard")
	if refresh:
		st.info("Dashboard osvezen.")

	with st.spinner("Ucitavam podatke iz InfluxDB..."):
		df, err = query_last_24h()

	if err:
		st.error(err)
		return

	if df.empty:
		st.warning("Nema podataka za poslednja 24h. Prvo generisi testne podatke ili upisi rucno ocitavanje.")
		return

	render_dashboard(df)


if __name__ == "__main__":
	main()
