from __future__ import annotations

import streamlit as st
from app.config import INFLUX_BUCKET, INFLUX_ORG, INFLUX_URL, STATION_TAG, STATION_VALUE
from app.services.ingestion import seed_data, write_realtime_reading
from app.services.query import query_last_24h
from app.ui.dashboard import render_dashboard


def init_station_state() -> None:
    if "stations" not in st.session_state:
        st.session_state["stations"] = [STATION_VALUE]


def render_connection_info() -> None:
    with st.expander("Konfiguracija konekcije", expanded=False):
        st.write(f"URL: {INFLUX_URL}")
        st.write(f"Org: {INFLUX_ORG}")
        st.write(f"Bucket: {INFLUX_BUCKET}")
        st.write("Token je ucitan iz koda za potrebe lokalnog PoC-a.")


def render_station_management_section() -> None:
    st.subheader("Merna mesta (gradovi)")

    with st.form("station_add_form", clear_on_submit=True):
        new_station = st.text_input("Dodaj novo merno mesto", placeholder="npr. Beograd")
        add_station = st.form_submit_button("Dodaj grad")

    if add_station:
        station = (new_station or "").strip()
        if not station:
            st.warning("Unesi naziv grada pre dodavanja.")
        elif station in st.session_state["stations"]:
            st.info("Ovaj grad vec postoji u listi.")
        else:
            st.session_state["stations"].append(station)
            st.success(f"Dodat grad: {station}")

    st.caption("Aktivna merna mesta: " + ", ".join(st.session_state["stations"]))


def render_seed_section() -> None:
    st.subheader("Simulator senzora")

    selected_seed_station = st.selectbox(
        "Grad za generisanje testnih podataka",
        options=st.session_state["stations"],
        key="seed_station",
    )
    num_points = st.slider("Broj testnih ocitavanja", min_value=10, max_value=500, value=100, step=10)

    if st.button("Generisi testne podatke", type="primary"):
        with st.spinner("Generisem i upisujem testne podatke..."):
            ok, message = seed_data(num_points=num_points, station_value=selected_seed_station)
        if ok:
            st.success(message)
        else:
            st.error(message)


def render_realtime_entry_section() -> None:
    st.divider()
    st.subheader("1) Unos u realnom vremenu")

    with st.form("realtime_form", clear_on_submit=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            station = st.selectbox("Grad", options=st.session_state["stations"], key="realtime_station")
        with c2:
            temperature = st.number_input(
                "Temperatura (C)",
                min_value=-30.0,
                max_value=60.0,
                value=22.0,
                step=0.1,
                format="%.1f",
            )
        with c3:
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
            ok, message = write_realtime_reading(
                temperature=float(temperature),
                humidity=float(humidity),
                station_value=station,
            )
        if ok:
            st.success(message)
        else:
            st.error(message)


def render_dashboard_section() -> None:
    st.divider()
    st.subheader("2) IoT Dashboard sa Flux upitima")

    if "temp_threshold" not in st.session_state:
        st.session_state["temp_threshold"] = 30.0
    st.session_state["temp_threshold"] = st.number_input(
        "Prag temperature za oznacavanje (C)",
        value=float(st.session_state["temp_threshold"]),
        step=0.1,
    )

    with st.spinner("Ucitavam podatke iz InfluxDB..."):
        df, err = query_last_24h()

    if err:
        st.error(err)
        return

    if df.empty:
        st.warning("Nema podataka za poslednja 24h. Prvo generisi testne podatke ili upisi rucno ocitavanje.")
        return

    data_stations = sorted([s for s in df[STATION_TAG].dropna().astype(str).unique().tolist()])
    known_stations = sorted(set(st.session_state["stations"]) | set(data_stations))
    st.session_state["stations"] = known_stations

    selected_stations = st.multiselect(
        "Prikazi gradove",
        options=known_stations,
        default=data_stations if data_stations else known_stations,
        key="dashboard_stations",
    )

    if not selected_stations:
        st.info("Izaberi bar jedan grad za prikaz grafikona.")
        return

    for station in selected_stations:
        station_df = df[df[STATION_TAG] == station].copy()
        if station_df.empty:
            st.info(f"Nema podataka za grad '{station}' u poslednja 24h.")
            continue
        st.markdown(f"### Grad: {station}")
        render_dashboard(
            station_df,
            temp_threshold=float(st.session_state["temp_threshold"]),
            location_name=station,
        )

    # Analytics: aggregate stats and export
    temp_df = df[df["_field"] == "temperature"].copy()
    hum_df = df[df["_field"] == "humidity"].copy()

    stats_col1, stats_col2 = st.columns(2)
    with stats_col1:
        if not temp_df.empty:
            st.metric("Temperatura - Prosečno (C)", f"{temp_df['_value'].mean():.2f}")
            st.metric("Temperatura - Min (C)", f"{temp_df['_value'].min():.2f}")
            st.metric("Temperatura - Max (C)", f"{temp_df['_value'].max():.2f}")
        else:
            st.write("Nema podataka za temperaturu u odabranom rasponu.")
    with stats_col2:
        if not hum_df.empty:
            st.metric("Vlaznost - Prosečno (%)", f"{hum_df['_value'].mean():.2f}")
            st.metric("Vlaznost - Min (%)", f"{hum_df['_value'].min():.2f}")
            st.metric("Vlaznost - Max (%)", f"{hum_df['_value'].max():.2f}")
        else:
            st.write("Nema podataka za vlaznost u odabranom rasponu.")

    # CSV export
    csv = df.to_csv(index=False)
    st.download_button("Preuzmi CSV", data=csv, file_name="iot_last_24h.csv", mime="text/csv")


def render_game_section() -> None:
    pass


def main() -> None:
    """Glavna Streamlit aplikacija za InfluxDB IoT dashboard."""
    st.set_page_config(page_title="IoT Dashboard - Vremenska stanica", page_icon="", layout="wide")

    st.title("IoT Dashboard za Vremensku Stanicu")

    init_station_state()
    render_connection_info()
    render_station_management_section()
    render_seed_section()
    render_realtime_entry_section()
    render_dashboard_section()


if __name__ == "__main__":
    main()
