"""
joblib ускоряет обработку нескольких городов на CPU, потому что
каждый город независим. На одном городе и малом датасете выигрыш может быть нулевой или отрицательный
из‑за накладных расходов на запуск воркеров.
"""
import time

import numpy as np
import pandas as pd
from joblib import Parallel, delayed


def load_data(uploaded_file=None):
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_csv("data/temperature_data.csv")
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df


def process_single_city(city: str, city_df: pd.DataFrame):
    city_df = city_df.copy().sort_values('timestamp')

    seasonal_stats = (city_df.groupby('season')
                      .agg(mean_temp=('temperature', 'mean'),
                           std_temp=('temperature', 'std'))
                      .reset_index())
    season_mean = seasonal_stats.set_index('season')['mean_temp']
    season_std = seasonal_stats.set_index('season')['std_temp']
    city_df['season_mean'] = city_df['season'].map(season_mean)
    city_df['season_std'] = city_df['season'].map(season_std)
    city_df['is_anomaly_seasonal'] = (
        abs(city_df['temperature'] - city_df['season_mean']) > (2 * city_df['season_std'])
    )

    city_df['rolling_mean'] = city_df['temperature'].rolling(window=30, min_periods=1).mean()
    city_df['rolling_std'] = city_df['temperature'].rolling(window=30, min_periods=1).std()
    valid_roll = city_df['rolling_std'].notna() & (city_df['rolling_std'] > 0)
    city_df['is_anomaly_rolling'] = valid_roll & (
        abs(city_df['temperature'] - city_df['rolling_mean']) > (2 * city_df['rolling_std'])
    )
    city_df['is_anomaly'] = city_df['is_anomaly_rolling']

    days = (city_df['timestamp'] - city_df['timestamp'].min()).dt.days.to_numpy(dtype=float)
    y = city_df['temperature'].to_numpy()
    if len(city_df) >= 2:
        coef = np.polyfit(days, y, 1)
        city_df['trend'] = np.poly1d(coef)(days)
    else:
        city_df['trend'] = city_df['temperature']

    return city, city_df, seasonal_stats


def compare_performance(df: pd.DataFrame):
    grouped = [(city, group.copy()) for city, group in df.groupby('city')]

    start = time.time()
    _ = [process_single_city(c, g) for c, g in grouped]
    seq_time = time.time() - start

    start = time.time()
    _ = Parallel(n_jobs=-1)(delayed(process_single_city)(c, g) for c, g in grouped)
    par_time = time.time() - start

    return seq_time, par_time


def get_city_analysis(df: pd.DataFrame, selected_city: str):
    city_df = df[df['city'] == selected_city].copy()
    _, processed_df, seasonal_stats = process_single_city(selected_city, city_df)
    return processed_df, seasonal_stats