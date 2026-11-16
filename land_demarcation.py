"""
Módulo de Demarcação Geoespacial de Terras para Agricultura Familiar.
Suporte híbrido: Base local de alta velocidade (Shapefile/Supabase) + WFS SICAR como fallback.
"""

import json
import os
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from http_transport import urlopen

LOCAL_DB_PATH = os.path.join(os.path.dirname(__file__), "imoveis_rr_sample.json")
SICAR_GEOSERVER_WFS = "https://geoserver.car.gov.br/geoserver/sicar/ows"

# Cache em memória para buscas instantâneas (< 1ms)
_LOCAL_IMOVEIS_CACHE: Optional[Dict[str, Dict[str, Any]]] = None


def load_local_imoveis_cache() -> Dict[str, Dict[str, Any]]:
    global _LOCAL_IMOVEIS_CACHE
    if _LOCAL_IMOVEIS_CACHE is None:
        _LOCAL_IMOVEIS_CACHE = {}
        if os.path.exists(LOCAL_DB_PATH):
            try:
                with open(LOCAL_DB_PATH, "r", encoding="utf-8") as f:
                    items = json.load(f)
                    for item in items:
                        cod = item.get("cod_imovel")
                        if cod:
                            _LOCAL_IMOVEIS_CACHE[cod.strip()] = item
            except Exception as e:
                print(f"[AVISO] Falha ao carregar cache local: {e}")
    return _LOCAL_IMOVEIS_CACHE


def exterior_points(geometry):
    polygons = geometry["coordinates"]
    if geometry["type"] == "Polygon":
        polygons = [polygons]
    points = [point for polygon in polygons for point in polygon[0][:-1]]
    if not points:
        raise ValueError("Perímetro sem coordenadas.")
    return points


def perimeter_reference(geometry):
    """Ponto representativo para a consulta regional à NASA POWER."""
    points = exterior_points(geometry)
    return {
        "latitude": round(sum(point[1] for point in points) / len(points), 6),
        "longitude": round(sum(point[0] for point in points) / len(points), 6),
    }


def car_result(code, municipality, area, feature, source, status=None):
    geometry = feature.get("geometry") or {}
    if geometry.get("type") not in ("Polygon", "MultiPolygon"):
        raise ValueError("Perímetro CAR sem geometria válida.")
    return {
        "source": source,
        "cod_imovel": code,
        "municipio": municipality,
        "uf": code[:2],
        "status": status,
        "area_total_ha": area,
        "area_total_m2": round(area * 10000, 2) if area is not None else None,
        "area_consolidada_ha": None,
        "area_reserva_legal_ha": None,
        "centroid": perimeter_reference(geometry),
        "geojson": {"type": "Feature", "geometry": geometry, "properties": {}},
    }


def query_land_demarcation(cod_imovel: str) -> Dict[str, Any]:
    code = cod_imovel.strip().upper()
    if not re.fullmatch(r"[A-Z]{2}-[0-9]{7}-[A-F0-9]{32}", code):
        raise ValueError("Código CAR inválido.")

    from supabase_client import buscar_propriedade_por_car

    item = buscar_propriedade_por_car(code)
    if item and (item.get("geojson") or {}).get("geometry"):
        return car_result(code, item.get("municipio"), item.get("area_total_ha"),
                          item["geojson"], "Supabase / perímetro CAR")

    item = load_local_imoveis_cache().get(code)
    if item:
        return car_result(code, item.get("municipio"), item.get("area_total_ha"),
                          item["geojson"], "SICAR / cópia local", item.get("status_imovel"))

    return query_sicar_wfs(code, code[:2].lower())


def query_land_by_point(lat: float, lon: float, uf: str = "rr") -> Dict[str, Any]:
    if not re.fullmatch(r"[a-z]{2}", uf, flags=re.IGNORECASE):
        raise ValueError("UF inválida.")
    return query_sicar_wfs(None, uf, point=(lat, lon))


def query_sicar_wfs(cod_imovel, uf, timeout=10, point=None):
    if point is None:
        cql = f"cod_imovel='{cod_imovel}'"
    else:
        lat, lon = point
        cql = f"INTERSECTS(geom, SRID=4326;POINT({lon} {lat}))"
    query_params = {
        "service": "WFS",
        "version": "1.0.0",
        "request": "GetFeature",
        "typeName": f"sicar:sicar_imoveis_{uf.lower()}",
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        "CQL_FILTER": cql,
        "maxFeatures": 1,
    }
    url = f"{SICAR_GEOSERVER_WFS}?{urllib.parse.urlencode(query_params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "AgroFamiliar/1.0"})
    try:
        with urlopen(req, timeout=timeout) as response:
            data = json.load(response)
        features = data["features"]
    except (OSError, ValueError, KeyError) as exc:
        raise OSError("SICAR WFS indisponível.") from exc
    if not features:
        raise LookupError("Imóvel CAR não encontrado.")

    feature = features[0]
    props = feature.get("properties") or {}
    code = props.get("cod_imovel") or cod_imovel
    if not code:
        raise OSError("SICAR não retornou o código do imóvel.")
    area = props.get("num_area")
    return car_result(code, props.get("nom_municipio"), float(area) if area is not None else None,
                      feature, "SICAR WFS", props.get("ind_status"))
