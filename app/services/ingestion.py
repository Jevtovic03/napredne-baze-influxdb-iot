from datetime import datetime, timedelta, timezone
import random

from influxdb_client import Point, WritePrecision
from influxdb_client.client.write_api import WriteOptions

from app.config import (
    INFLUX_BUCKET,
    INFLUX_ORG,
    MEASUREMENT,
    STATION_TAG,
    STATION_VALUE,
)
from app.influx_client import get_client, is_db_available


def seed_data(num_points: int = 100, station_value: str | None = None) -> tuple[bool, str]:
    """Generise nasumicna IoT ocitavanja za poslednja 24h za odabrani grad."""
    client = None
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

        station = station_value.strip() if station_value else STATION_VALUE

        for _ in range(num_points):
            seconds_ago = random.uniform(0, 24 * 60 * 60)
            point_time = now_utc - timedelta(seconds=seconds_ago)
            temperature = round(random.uniform(15.0, 35.0), 2)
            humidity = round(random.uniform(30.0, 80.0), 2)

            point = (
                Point(MEASUREMENT)
                .tag(STATION_TAG, station)
                .field("temperature", temperature)
                .field("humidity", humidity)
                .time(point_time, WritePrecision.S)
            )
            points.append(point)

        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=points)
        write_api.flush()
        return True, f"Uspesno upisano {num_points} testnih ocitavanja za grad '{station}'."
    except Exception as exc:
        return False, f"Greska pri generisanju podataka: {exc}"
    finally:
        if write_api is not None:
            write_api.close()
        if client is not None:
            client.close()


def write_realtime_reading(
    temperature: float,
    humidity: float,
    station_value: str | None = None,
) -> tuple[bool, str]:
    """Upisuje jedno rucno ocitavanje za odabrani grad u trenutnom vremenu."""
    client = None
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

        station = station_value.strip() if station_value else STATION_VALUE

        point = (
            Point(MEASUREMENT)
            .tag(STATION_TAG, station)
            .field("temperature", round(float(temperature), 2))
            .field("humidity", round(float(humidity), 2))
            .time(datetime.now(timezone.utc), WritePrecision.S)
        )

        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
        write_api.flush()
        return True, f"Rucno ocitavanje za grad '{station}' je uspesno upisano u InfluxDB."
    except Exception as exc:
        return False, f"Greska pri upisu ocitavanja: {exc}"
    finally:
        if write_api is not None:
            write_api.close()
        if client is not None:
            client.close()

