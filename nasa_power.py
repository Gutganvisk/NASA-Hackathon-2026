"""
Cliente para consulta da API NASA POWER (Prediction Of Worldwide Energy Resources)
Focado na comunidade de Agroclimatologia (AG).
Implementa as boas práticas da documentação v2.0:
- Grid Snapping (0.5° x 0.5°) para evitar bloqueio por requisições redundantes (HTTP 429)
- Microsserviço Climatology API (Normais de 30 anos)
- Microsserviço Daily API (Monitoramento operacional recente)
- Preserva dados ausentes em vez de imputar medições
"""

import json
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple
from functools import lru_cache
from datetime import timedelta
from time import time

from http_transport import urlopen

NASA_POWER_BASE_DAILY = "https://power.larc.nasa.gov/api/temporal/daily/point"
NASA_POWER_BASE_CLIMATOLOGY = "https://power.larc.nasa.gov/api/temporal/climatology/point"

DEFAULT_PARAMETERS = [
    "PRECTOTCORR",       # Precipitação corrigida (mm/dia)
    "T2M",               # Temperatura média a 2 metros (°C)
    "T2M_MAX",           # Temperatura máxima a 2 metros (°C)
    "T2M_MIN",           # Temperatura mínima a 2 metros (°C)
    "ALLSKY_SFC_SW_DWN", # Radiação solar na superfície (MJ/m²/dia na comunidade AG)
    "RH2M",              # Umidade relativa do ar a 2 metros (%)
    "GWETTOP",           # Umidade do solo superficial: 0 a 5 cm (0 a 1)
    "GWETROOT",          # Umidade do solo na zona radicular: 0 a 100 cm (0 a 1)
]

# Cache em memória por célula da grade (evita requisições repetidas para a mesma vicinal)
_CLIMATOLOGY_CACHE: Dict[str, Dict[str, Any]] = {}


def snap_to_power_grid(lat: float, lon: float, grid_size: float = 0.5) -> Tuple[float, float]:
    """
    Arredonda as coordenadas para o centróide da célula da grade de 0.5° x 0.5°.
    Protege a aplicação contra o bloqueio de requisições repetidas da NASA (HTTP 429).
    """
    snapped_lat = round(lat / grid_size) * grid_size
    snapped_lon = round(lon / grid_size) * grid_size
    return round(snapped_lat, 2), round(snapped_lon, 2)


def fetch_climatology_normals(latitude: float, longitude: float) -> Dict[str, Any]:
    """
    Consulta as Normais Climatológicas Históricas de 30 anos (Climatology API).
    Define o calendário oficial de início e corte das chuvas para a coordenada.
    """
    s_lat, s_lon = snap_to_power_grid(latitude, longitude)
    cache_key = f"clim_{s_lat}_{s_lon}"
    if cache_key in _CLIMATOLOGY_CACHE:
        return _CLIMATOLOGY_CACHE[cache_key]

    params = {
        "parameters": "PRECTOTCORR,T2M,T2M_MAX,ALLSKY_SFC_SW_DWN",
        "community": "AG",
        "longitude": s_lon,
        "latitude": s_lat,
        "format": "JSON"
    }
    url = f"{NASA_POWER_BASE_CLIMATOLOGY}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "CropRotationPlanner/2.0"})

    try:
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            p = data.get("properties", {}).get("parameter", {})
            _CLIMATOLOGY_CACHE[cache_key] = p
            return p
    except Exception as e:
        print(f"[AVISO] Falha ao consultar Climatology API: {e}")
        return {}


def fetch_weather_data(
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    parameters: Optional[List[str]] = None,
    community: str = "AG"
) -> Dict[str, Any]:
    """
    Consulta dados diários (Daily API) com respeito à grade e cache local.
    """
    if parameters is None:
        parameters = DEFAULT_PARAMETERS

    # A própria POWER escolhe a célula de cada variável. Arredondar antes
    # da consulta pode deslocar o ponto para outra célula.
    s_lat, s_lon = latitude, longitude

    params_str = ",".join(parameters)
    query_params = {
        "parameters": params_str,
        "community": community,
        "longitude": s_lon,
        "latitude": s_lat,
        "start": start_date,
        "end": end_date,
        "time-standard": "UTC",
        "format": "JSON"
    }

    url = f"{NASA_POWER_BASE_DAILY}?{urllib.parse.urlencode(query_params)}"
    raw_data = _request_daily(url, int(time() // 900))

    properties = raw_data.get("properties", {})
    parameter_data = properties.get("parameter", {})

    daily_records: Dict[str, Dict[str, Optional[float]]] = {}
    for param_name, values_by_date in parameter_data.items():
        for date_str, value in values_by_date.items():
            if date_str not in daily_records:
                daily_records[date_str] = {}
            # Tratamento de sentinela -999 (Missing Value)
            daily_records[date_str][param_name] = None if value == -999.0 else value

    result = {
        "latitude": latitude,
        "longitude": longitude,
        "ponto_consultado": {"latitude": s_lat, "longitude": s_lon},
        "start_date": start_date,
        "end_date": end_date,
        "daily_records": daily_records
    }

    return result


@lru_cache(maxsize=128)
def _request_daily(url, refresh_slot):
    with urlopen(
        urllib.request.Request(url, headers={"User-Agent": "CropRotationPlanner/2.0"}), timeout=15
    ) as response:
        return json.load(response)


def fetch_recent_weather(latitude, longitude, today):
    """Pede os últimos 14 dias completos e mantém o atraso visível no resultado."""
    return fetch_weather_data(
        latitude, longitude,
        (today - timedelta(days=14)).strftime("%Y%m%d"),
        (today - timedelta(days=1)).strftime("%Y%m%d"),
        parameters=["PRECTOTCORR", "T2M", "T2M_MAX", "GWETROOT", "GWETTOP", "ALLSKY_SFC_SW_DWN"],
    )
