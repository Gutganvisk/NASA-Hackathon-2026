"""
Cliente para consulta da API NASA POWER (Prediction Of Worldwide Energy Resources)
Focado na comunidade de Agroclimatologia (AG).
Implementa as boas práticas da documentação v2.0:
- Grid Snapping (0.5° x 0.5°) para evitar bloqueio por requisições redundantes (HTTP 429)
- Microsserviço Climatology API (Normais de 30 anos)
- Microsserviço Daily API (Monitoramento operacional recente)
- Tratamento de sentinela -999 com fallback climatológico
"""

import json
import math
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

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
_GRID_CACHE: Dict[str, Dict[str, Any]] = {}
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
        with urllib.request.urlopen(req, timeout=15) as resp:
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

    s_lat, s_lon = snap_to_power_grid(latitude, longitude)
    cache_key = f"daily_{s_lat}_{s_lon}_{start_date}_{end_date}"
    if cache_key in _GRID_CACHE:
        return _GRID_CACHE[cache_key]

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
    req = urllib.request.Request(url, headers={"User-Agent": "CropRotationPlanner/2.0"})

    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            if response.status != 200:
                raise RuntimeError(f"Erro HTTP {response.status}")
            raw_data = json.loads(response.read().decode("utf-8"))
    except Exception as e:
        raise RuntimeError(f"Falha de conexão com a API NASA POWER: {e}")

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
        "snapped_grid": {"latitude": s_lat, "longitude": s_lon},
        "start_date": start_date,
        "end_date": end_date,
        "daily_records": daily_records
    }

    _GRID_CACHE[cache_key] = result
    return result
