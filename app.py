import streamlit as st
from datetime import datetime
import plotly.graph_objects as go

from utils.analysis import load_data, get_city_analysis, compare_performance
from utils.api import get_current_weather_sync, benchmark_weather_fetch

st.set_page_config(page_title="Температурный мониторинг", layout="wide")
st.title("Анализ температурных данных")

uploaded_file = st.file_uploader("Загрузите temperature_data.csv", type="csv")
df = load_data(uploaded_file)

cities = sorted(df["city"].unique())
selected_city = st.selectbox("Выберите город", cities)

processed_df, seasonal_stats = get_city_analysis(df, selected_city)

st.subheader("Описательная статистика")
st.dataframe(processed_df["temperature"].describe(), use_container_width=True)

st.subheader("Временной ряд температур с аномалиями и трендом")
fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=processed_df["timestamp"],
        y=processed_df["temperature"],
        name="Температура",
        mode="lines",
    )
)
fig.add_trace(
    go.Scatter(
        x=processed_df["timestamp"],
        y=processed_df["rolling_mean"],
        name="Скользящее среднее (30 дней)",
        mode="lines",
    )
)
fig.add_trace(
    go.Scatter(
        x=processed_df["timestamp"],
        y=processed_df["trend"],
        name="Линейный тренд (весь ряд)",
        mode="lines",
        line=dict(dash="dash", width=2),
    )
)
roll_a = processed_df[processed_df["is_anomaly_rolling"]]
fig.add_trace(
    go.Scatter(
        x=roll_a["timestamp"],
        y=roll_a["temperature"],
        mode="markers",
        name="Аномалии",
        marker=dict(color="red", size=8),
    )
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Сезонные профили")
fig_season = go.Figure()
for _, row in seasonal_stats.iterrows():
    fig_season.add_trace(
        go.Bar(
            x=[row["season"]],
            y=[row["mean_temp"]],
            error_y=dict(type="data", array=[row["std_temp"] * 2]),
            name=row["season"],
        )
    )
st.plotly_chart(fig_season, use_container_width=True)

st.subheader("Текущая температура")
api_key = st.text_input("Введите API-ключ OpenWeatherMap", type="password")

if api_key:
    with st.spinner("Получаем данные..."):
        temp, desc = get_current_weather_sync(selected_city, api_key)

        if temp is None:
            st.error(desc)
        else:
            st.success(f"**{selected_city}**: {temp:.1f}°C, {desc}")

            month = datetime.now().month
            season_map = {
                12: "winter",
                1: "winter",
                2: "winter",
                3: "spring",
                4: "spring",
                5: "spring",
                6: "summer",
                7: "summer",
                8: "summer",
                9: "autumn",
                10: "autumn",
                11: "autumn",
            }
            current_season = season_map[month]

            match = seasonal_stats[seasonal_stats["season"] == current_season]
            if match.empty:
                st.warning("Нет исторических данных для текущего сезона.")
            else:
                season_row = match.iloc[0]
                mean_season = season_row["mean_temp"]
                std_season = season_row["std_temp"]

                if abs(temp - mean_season) > 2 * std_season:
                    st.error(f"Аномальная температура для сезона {current_season}")
                else:
                    st.success(f"Нормальная температура для сезона {current_season}")
else:
    st.info("Введите API-ключ для отображения текущей погоды")

with st.expander("Сравнение производительности"):
    seq_t, par_t = compare_performance(df)
    st.write(f"Последовательный анализ (все города): {seq_t:.3f} с")
    st.write(f"Параллельный анализ (joblib, все города): {par_t:.3f} с")

    st.divider()
    if api_key:
        if st.button("Замерить sync и async для выбранного города"):
            with st.spinner("Выполняются запросы к API..."):
                sync_avg, async_avg = benchmark_weather_fetch(selected_city, api_key, repeats=3)
            st.write(f"Среднее время синхронного запроса: **{sync_avg:.3f}** с")
            st.write(f"Среднее время асинхронного запроса: **{async_avg:.3f}** с")
    else:
        st.info("Введите API-ключ выше, чтобы доступен замер запросов.")
