import pandas as pd
import plotly.express as px
import streamlit as st


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
