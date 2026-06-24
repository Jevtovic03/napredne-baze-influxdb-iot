import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def render_dashboard(
    df: pd.DataFrame,
    temp_threshold: float | None = None,
    location_name: str | None = None,
) -> None:
    """Prikazuje metrike i linijske grafikone sa istaknutim temperaturnim pragom."""
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
        fig_temp = go.Figure()
        fig_temp.add_trace(
            go.Scatter(
                x=temp_df["_time"],
                y=temp_df["_value"],
                mode="lines",
                name="Temperatura",
                line=dict(color="#1f77b4", width=2),
            )
        )

        if temp_threshold is not None:
            below_threshold = temp_df[temp_df["_value"] <= temp_threshold]
            above_threshold = temp_df[temp_df["_value"] > temp_threshold]

            if not below_threshold.empty:
                fig_temp.add_trace(
                    go.Scatter(
                        x=below_threshold["_time"],
                        y=below_threshold["_value"],
                        mode="markers",
                        name="Ispod praga",
                        marker=dict(color="#2ca02c", size=8),
                    )
                )

            if not above_threshold.empty:
                fig_temp.add_trace(
                    go.Scatter(
                        x=above_threshold["_time"],
                        y=above_threshold["_value"],
                        mode="markers",
                        name="Iznad praga",
                        marker=dict(color="#d62728", size=10, symbol="circle-open"),
                    )
                )

            fig_temp.add_hline(
                y=temp_threshold,
                line_dash="dash",
                line_color="#d62728",
                annotation_text=f"Prag {temp_threshold:.1f}C",
                annotation_position="top left",
            )

        temp_title = "Temperatura kroz vreme (poslednja 24h)"
        if location_name:
            temp_title = f"Temperatura kroz vreme - {location_name} (poslednja 24h)"

        fig_temp.update_layout(
            title=temp_title,
            xaxis_title="Vreme",
            yaxis_title="Temperatura (C)",
            template="plotly_white",
            legend_title_text="",
        )
        st.plotly_chart(fig_temp, use_container_width=True)

    if not hum_df.empty:
        fig_hum = go.Figure(
            data=[
                go.Scatter(
                    x=hum_df["_time"],
                    y=hum_df["_value"],
                    mode="lines+markers",
                    name="Vlaznost",
                    line=dict(color="#17becf", width=2),
                    marker=dict(size=7),
                )
            ]
        )
        hum_title = "Vlaznost vazduha kroz vreme (poslednja 24h)"
        if location_name:
            hum_title = f"Vlaznost vazduha kroz vreme - {location_name} (poslednja 24h)"

        fig_hum.update_layout(
            title=hum_title,
            xaxis_title="Vreme",
            yaxis_title="Vlaznost (%)",
            template="plotly_white",
            legend_title_text="",
        )
        st.plotly_chart(fig_hum, use_container_width=True)

    raw_label = "Prikazi sirove podatke"
    if location_name:
        raw_label = f"Prikazi sirove podatke - {location_name}"
    with st.expander(raw_label):
        st.dataframe(df, use_container_width=True)
