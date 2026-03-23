"""
Синхронные запросы проще в Streamlit один вызов, один ответ, без event loop
Асинхронный вариант выгоден при множестве параллельных запросов к разным URL/городам
"""
import asyncio
import time
from typing import Any, Optional, Tuple

import aiohttp
import requests

API_URL = "https://api.openweathermap.org/data/2.5/weather"

def _message_from_json_payload(data: Any) -> str:
    if isinstance(data, dict):
        msg = data.get("message")
        if isinstance(msg, str) and msg.strip():
            return msg
        cod = data.get("cod")
        return f"Ошибка API (cod={cod!r})"
    return str(data)


def _error_message_sync(resp: requests.Response) -> str:
    try:
        data = resp.json()
    except Exception:
        text = (resp.text or "").strip()
        return text if text else f"HTTP {resp.status_code}"
    return _message_from_json_payload(data)


async def get_current_weather_async(city: str, api_key: str) -> Tuple[Optional[float], str]:
    params = {"q": city, "appid": api_key, "units": "metric", "lang": "ru"}
    async with aiohttp.ClientSession() as session:
        async with session.get(API_URL, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            data = await resp.json()
            if resp.status == 200:
                return data["main"]["temp"], data["weather"][0]["description"]
            return None, _message_from_json_payload(data)


def get_current_weather_sync(city: str, api_key: str) -> Tuple[Optional[float], str]:
    params = {"q": city, "appid": api_key, "units": "metric", "lang": "ru"}
    resp = requests.get(API_URL, params=params, timeout=10)
    if resp.status_code == 200:
        data = resp.json()
        return data["main"]["temp"], data["weather"][0]["description"]
    return None, _error_message_sync(resp)


def benchmark_weather_fetch(city: str, api_key: str, repeats: int = 3) -> Tuple[float, float]:
    repeats = max(1, repeats)

    t0 = time.perf_counter()
    for _ in range(repeats):
        get_current_weather_sync(city, api_key)
    sync_avg = (time.perf_counter() - t0) / repeats

    async def _run_async_batch():
        for _ in range(repeats):
            await get_current_weather_async(city, api_key)

    t0 = time.perf_counter()
    asyncio.run(_run_async_batch())
    async_avg = (time.perf_counter() - t0) / repeats
    return sync_avg, async_avg
