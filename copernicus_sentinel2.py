"""
Módulo de Integração com o Copernicus Data Space Ecosystem (CDSE) / Sentinel Hub.
Autenticação OAuth2 e Statistical API para cálculo de NDVI do Sentinel-2.
"""

import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from math import asinh, isfinite, radians, tan
from typing import Any, Dict

from http_transport import urlopen

# Carrega automaticamente variáveis do arquivo .env local se existir
def _load_env_file():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())
        except Exception:
            pass

_load_env_file()

CLIENT_ID = os.environ.get("CDSE_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("CDSE_CLIENT_SECRET", "")
TOKEN_URL = os.environ.get("CDSE_TOKEN_URL", "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token")
STATISTICS_URL = os.environ.get("CDSE_STATISTICS_URL", "https://sh.dataspace.copernicus.eu/statistics/v1")
PROCESS_URL = os.environ.get("CDSE_PROCESS_URL", "https://sh.dataspace.copernicus.eu/process/v1")

# Cache em memória do token OAuth2
_TOKEN_CACHE: Dict[str, Any] = {"token": None, "expires_at": 0}


def get_access_token() -> str:
    """
    Obtém ou renova o token OAuth2 de acesso ao Copernicus CDSE.
    """
    now = time.time()
    if _TOKEN_CACHE["token"] and _TOKEN_CACHE["expires_at"] > now + 60:
        return _TOKEN_CACHE["token"]

    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }).encode("utf-8")

    req = urllib.request.Request(
        TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    with urlopen(req, timeout=15) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        token = res.get("access_token")
        expires_in = res.get("expires_in", 1800)
        _TOKEN_CACHE["token"] = token
        _TOKEN_CACHE["expires_at"] = now + expires_in
        return token


NDVI_EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: ["B04", "B08", "SCL", "dataMask"],
    output: [
      {id: "ndvi", bands: 1, sampleType: "FLOAT32"},
      {id: "dataMask", bands: 1}
    ]
  };
}
function evaluatePixel(sample) {
  const sum = sample.B08 + sample.B04;
  // Vegetação e superfícies terrestres sem nuvem, segundo a máscara SCL.
  const valid = sample.dataMask && [4, 5].includes(sample.SCL) && sum > 0;
  return {
    ndvi: [valid ? (sample.B08 - sample.B04) / sum : 0],
    dataMask: [valid ? 1 : 0]
  };
}
"""


TRUE_COLOR_EVALSCRIPT = """//VERSION=3
function setup() {
  return {input: ["B04", "B03", "B02", "dataMask"], output: {bands: 4}};
}
function evaluatePixel(sample) {
  return [2.5 * sample.B04, 2.5 * sample.B03, 2.5 * sample.B02, sample.dataMask];
}
"""


@lru_cache(maxsize=24)
def fetch_satellite_image(bounds, utc_day):
    """Solicita uma imagem na projeção utilizada pelo mapa Leaflet."""
    if not CLIENT_ID or not CLIENT_SECRET:
        raise OSError("Credenciais CDSE ausentes")
    west, south, east, north = bounds
    earth_radius = 6378137
    bbox = [earth_radius * radians(west), earth_radius * asinh(tan(radians(south))),
            earth_radius * radians(east), earth_radius * asinh(tan(radians(north)))]
    width_m, height_m = bbox[2] - bbox[0], bbox[3] - bbox[1]
    dimension = min(640 / max(width_m, height_m), 0.1)
    width, height = max(1, round(width_m * dimension)), max(1, round(height_m * dimension))
    payload = {
        "input": {
            "bounds": {"bbox": bbox, "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/3857"}},
            "data": [{"type": "sentinel-2-l2a", "dataFilter": {
                "mosaickingOrder": "leastCC",
                "timeRange": {
                    "from": f"{utc_day - timedelta(days=60)}T00:00:00Z",
                    "to": f"{utc_day}T00:00:00Z",
                },
            }}],
        },
        "output": {"width": width, "height": height,
                   "responses": [{"identifier": "default", "format": {"type": "image/png"}}]},
        "evalscript": TRUE_COLOR_EVALSCRIPT,
    }
    request = urllib.request.Request(
        PROCESS_URL, data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {get_access_token()}", "Content-Type": "application/json"},
    )
    with urlopen(request, timeout=15) as response:
        if response.headers.get_content_type() != "image/png":
            raise OSError("Imagem Sentinel-2 inválida")
        return response.read()


def calculate_ndvi_analysis(geometry: Dict[str, Any], date_from=None, date_to=None):
    end = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")
    start = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00Z")
    try:
        if not CLIENT_ID or not CLIENT_SECRET:
            raise ValueError("Credenciais CDSE ausentes")
        result = _query_statistics(
            json.dumps(geometry, sort_keys=True), date_from or start, date_to or end,
            int(time.time() // 900),
        )
        if result:
            return {"sucesso": True, "fonte": "Copernicus Sentinel-2 L2A", **result}
        aviso = "Sem pixels terrestres válidos na janela consultada."
    except Exception as exc:
        print(f"[CDSE] Falha ao consultar NDVI: {type(exc).__name__}", flush=True)
        aviso = "Consulta Sentinel-2 indisponível."
    return {"sucesso": False, "ndvi_medio_estimado": None, "aviso": aviso}


@lru_cache(maxsize=64)
def _query_statistics(geometry_json, date_from, date_to, refresh_slot):
    payload = {
        "input": {
            "bounds": {
                "geometry": json.loads(geometry_json),
                "properties": {"crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"},
            },
            "data": [{"type": "sentinel-2-l2a", "dataFilter": {"mosaickingOrder": "mostRecent"}}],
        },
        "aggregation": {
            "timeRange": {"from": date_from, "to": date_to},
            "aggregationInterval": {"of": "P1D"},
            "width": 128,
            "height": 128,
            "evalscript": NDVI_EVALSCRIPT,
        },
    }
    request = urllib.request.Request(
        STATISTICS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {get_access_token()}", "Content-Type": "application/json"},
    )
    with urlopen(request, timeout=15) as response:
        data = json.load(response)
    if data.get("status") != "OK":
        raise ValueError("Resposta inválida da API de estatísticas")
    for interval in sorted(data["data"], key=lambda item: item["interval"]["from"], reverse=True):
        stats = interval.get("outputs", {}).get("ndvi", {}).get("bands", {}).get("B0", {}).get("stats")
        if not stats:
            continue
        valid = stats["sampleCount"] - stats["noDataCount"]
        mean = stats.get("mean")
        if valid > 0 and isinstance(mean, (int, float)) and isfinite(mean):
            return {
                "periodo_analisado": interval["interval"]["from"][:10],
                "ndvi_medio_estimado": round(mean, 3),
                "pixels_validos": valid,
                "pixels_amostrados": stats["sampleCount"],
            }
    return None
