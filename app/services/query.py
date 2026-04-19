import pandas as pd

from app.config import INFLUX_BUCKET, INFLUX_ORG, MEASUREMENT, STATION_TAG
from app.influx_client import get_client, is_db_available


def query_last_24h() -> tuple[pd.DataFrame, str | None]:
    """Vuce temperature i vlaznost za poslednja 24h putem Flux upita."""
    client = None

    try:
        client = get_client()
        if not is_db_available(client):
            return pd.DataFrame(), "InfluxDB nije dostupan. Dashboard ne moze da ucita podatke."

        query_api = client.query_api()

        # InfluxDB je TSDB optimizovana za vreme-serijske tokove podataka.
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
