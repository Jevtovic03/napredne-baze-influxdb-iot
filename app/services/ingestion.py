from datetime import datetime, timedelta, timezone
import random

from influxdb_client import Point, WritePrecision
from influxdb_client.client.write_api import WriteOptions

from app.config import INFLUX_BUCKET, INFLUX_ORG, MEASUREMENT, STATION_TAG, STATION_VALUE
from app.influx_client import get_client, is_db_available


def seed_data(num_points: int = 100) -> tuple[bool, str]:
    """Generise nasumicna IoT ocitavanja za poslednja 24h i upisuje ih batch metodom."""
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
