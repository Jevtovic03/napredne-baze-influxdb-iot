from __future__ import annotations

import streamlit as st
from app.config import INFLUX_BUCKET, INFLUX_ORG, INFLUX_URL
from app.services.ingestion import seed_data, write_realtime_reading
from app.services.query import query_last_24h
from app.ui.dashboard import render_dashboard


def render_connection_info() -> None:
    with st.expander("Konfiguracija konekcije", expanded=False):
        st.write(f"URL: {INFLUX_URL}")
        st.write(f"Org: {INFLUX_ORG}")
        st.write(f"Bucket: {INFLUX_BUCKET}")
        st.write("Token je ucitan iz koda za potrebe lokalnog PoC-a.")


def render_seed_section() -> None:
    st.subheader("Simulator senzora")
    if st.button("Generisi testne podatke", type="primary"):
        with st.spinner("Generisem i upisujem testne podatke..."):
            ok, message = seed_data(num_points=100)
        if ok:
            st.success(message)
        else:
            st.error(message)


def render_realtime_entry_section() -> None:
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
            ok, message = write_realtime_reading(
                temperature=float(temperature),
                humidity=float(humidity),
            )
        if ok:
            st.success(message)
        else:
            st.error(message)


def render_dashboard_section() -> None:
    st.divider()
    st.subheader("2) IoT Dashboard sa Flux upitima (poslednja 24h)")

    if st.button("Osvezi dashboard"):
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


def main() -> None:
    """Glavna Streamlit aplikacija za InfluxDB IoT dashboard."""
    st.set_page_config(page_title="IoT Dashboard - Vremenska stanica", page_icon="", layout="wide")

    st.title("IoT Dashboard za Vremensku Stanicu")

    render_connection_info()
    render_seed_section()
    render_realtime_entry_section()
    render_dashboard_section()


if __name__ == "__main__":
    main()
