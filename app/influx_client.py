from influxdb_client import InfluxDBClient

from app.config import INFLUX_ORG, INFLUX_TOKEN, INFLUX_URL


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
