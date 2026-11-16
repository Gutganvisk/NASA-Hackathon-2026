"""
Servidor HTTP REST para a Plataforma de Prescrição Agroclimática e Rotação de Culturas.
Padrão Mobile-First e conformidade com o desafio NASA Space Apps 2026.
"""

import base64
import json
import os
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from math import isfinite
from statistics import mean
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from copernicus_sentinel2 import calculate_ndvi_analysis, fetch_satellite_image
from land_demarcation import exterior_points, perimeter_reference, query_land_by_point, query_land_demarcation
from nasa_power import fetch_recent_weather, fetch_weather_data
from passaporte_biologico import MATRIZ_PASSAPORTE
from rotation_planner import (
    compare_three_rotation_strategies,
    evaluate_with_biological_passport,
    summarize_weather,
)

from supabase_client import is_supabase_configured, salvar_plano
from talhao_geometry import parse_ring, validate_plot

PORT = int(os.environ.get("PORT", 8080))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_ASSETS = {
    "/assets/crop-rotation-logo.png": "image/png",
    "/assets/crop-rotation-icon.png": "image/png",
    "/assets/ui-icons.svg": "image/svg+xml",
    "/assets/boa-vista-20261116.jpg": "image/jpeg",
}

def coordinates(lat, lon):
    try:
        lat, lon = float(lat), float(lon)
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    except (TypeError, ValueError):
        pass
    raise ValueError("Informe coordenadas válidas (lat e lon) ou consulte com o CAR.")


def recent_weather(lat, lon):
    try:
        return fetch_recent_weather(lat, lon, datetime.now(timezone.utc).date())
    except (OSError, ValueError) as exc:
        print(f"[POWER] Consulta indisponível: {type(exc).__name__}", flush=True)
        return {}


def water_alerts(records, end_date, crops):
    if not end_date or not crops:
        return []

    def root_wetness(day):
        value = records.get(day.strftime("%Y%m%d"), {}).get("GWETROOT")
        return value * 100 if value is not None and 0 <= value <= 1 else None

    end = date.fromisoformat(end_date)
    # Não inferir persistência em dados antigos ou com lacunas na sequência.
    recent = [end - timedelta(days=offset) for offset in range(4)]
    latest = next((day for day in recent if root_wetness(day) is not None), None)
    if latest is None:
        return []
    samples = [root_wetness(latest - timedelta(days=offset)) for offset in range(3)]
    if any(value is None for value in samples):
        return []
    alerts = []
    for crop in crops:
        passport = MATRIZ_PASSAPORTE.get(crop)
        if passport and all(value < passport.smap_gwetroot_min_pct for value in samples):
            alerts.append({
                "cultura": passport.cultura,
                "saturacao_recente_pct": round(samples[0], 1),
                "ultima_leitura": latest.isoformat(),
                "dias_consecutivos": len(samples),
            })
    return alerts


def area_diagnosis(lat, lon, geometry, crops=()):
    with ThreadPoolExecutor(max_workers=2) as pool:
        weather_task = pool.submit(recent_weather, lat, lon)
        ndvi_task = pool.submit(calculate_ndvi_analysis, geometry) if geometry else None
        weather = weather_task.result()
        ndvi = ndvi_task.result() if ndvi_task else {}

    records = weather.get("daily_records", {})

    def power_card(title, variable, unit, aggregate, factor=1):
        values = [
            (day, value)
            for day, record in sorted(records.items())
            if (value := record.get(variable)) is not None and isfinite(value)
        ]
        count = len(values)
        number = round(aggregate([value for _, value in values]) * factor, 2) if count else None
        return {
            "titulo": title,
            "valor": f"{number:g} {unit}" if count else "Indisponível",
            "medicao": number,
            "status": f"{count}/14 dias com dados" if count else "Sem dados na janela",
            "datas_com_dados": [day for day, _ in values],
            "fonte": "NASA POWER / " + variable,
        }

    ndvi_value = ndvi.get("ndvi_medio_estimado") if ndvi.get("sucesso") else None
    cards = {
        "chuva_recente": power_card("Chuva acumulada nos dias disponíveis", "PRECTOTCORR", "mm", sum),
        "temperatura": power_card("Temperatura média", "T2M", "°C", mean),
        "radiacao_solar": power_card("Radiação solar média", "ALLSKY_SFC_SW_DWN", "MJ/m²/dia", mean),
        "temperatura_maxima": power_card("Maior temperatura máxima diária", "T2M_MAX", "°C", max),
        "umidade_solo": power_card("Saturação relativa do solo (0–100 cm)", "GWETROOT", "%", mean, 100),
        "saturacao_superficial": power_card("Saturação relativa do solo (0–5 cm)", "GWETTOP", "%", mean, 100),
        "cobertura_vegetal": {
            "titulo": "Vigor da vegetação (NDVI)",
            "valor": str(ndvi_value) if ndvi_value is not None else "Indisponível",
            "medicao": ndvi_value,
            "status": ndvi.get("periodo_analisado") or ndvi.get("aviso") or "Informe um contorno ou CAR",
            "fonte": "Copernicus Sentinel-2 L2A",
        },
        "relevo": {"titulo": "Relevo", "valor": "Indisponível", "status": "Declividade não medida"},
        "condicao_solo": {"titulo": "Condição do solo", "valor": "Indisponível", "status": "Requer análise de campo"},
    }
    has_data = any(card.get("medicao") is not None for card in cards.values())
    return {
        "status": "partial" if has_data else "unavailable",
        "condicao_geral": "Diagnóstico parcial" if has_data else "Dados indisponíveis",
        "score_geral": None,
        "coordenadas": {"latitude": lat, "longitude": lon},
        "periodo_power": {"inicio": weather.get("start_date"), "fim": weather.get("end_date")},
        "leitura_simples": "A chuva soma os dias disponíveis. A saturação vem de um modelo regional e o NDVI indica vigor da vegetação verde.",
        "cards": cards,
        "alertas_hidricos": water_alerts(records, weather.get("end_date"), crops),
        "sentinel": ndvi or None,
    }


ZARC_RR = (
    "https://www.gov.br/agricultura/pt-br/assuntos/riscos-seguro/"
    "programa-nacional-de-zoneamento-agricola-de-risco-climatico/portarias/safra-vigente/roraima/roraima-rr"
)

AGENDA_RR = {
    "regiao": "Roraima",
    "janela_climatica_geral": "A distribuição da chuva varia entre municípios e entre anos.",
    "eventos_chave": [
        {
            "data_estimada": "Antes do plantio",
            "cultura": "Milho",
            "etapa": "Conferir a janela de semeadura",
            "orientacao": "Consulte o ZARC de milho ou milho com braquiária, conforme o sistema de cultivo, e confirme umidade no campo.",
        },
        {
            "data_estimada": "Antes do plantio",
            "cultura": "Feijão-caupi",
            "etapa": "Avaliar a janela depois da colheita anterior",
            "orientacao": "Verifique se ainda há janela de semeadura no ZARC para o município e o ciclo escolhido. Avalie a disponibilidade de água até a maturação.",
        },
        {
            "data_estimada": "No estabelecimento",
            "cultura": "Mandioca",
            "etapa": "Planejar o estabelecimento das plantas",
            "orientacao": "Ajuste o plantio para reduzir o risco de falta de água nos primeiros cinco meses e evite terrenos sujeitos a encharcamento.",
        },
    ],
    "avisos_agronomicos": [
        "Para definir a data de plantio, confira a combinação de município, solo, grupo de cultivar e nível de risco na portaria vigente.",
    ],
    "fontes": [
        {"nome": "MAPA — ZARC vigente de Roraima", "url": ZARC_RR},
        {
            "nome": "Embrapa — O Cultivo da Mandioca em Roraima",
            "url": "https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/1155484/1/O-Cultivo-da-Mandioca-em-Roraima.pdf",
        },
    ],
}


class AgroHandler(BaseHTTPRequestHandler):

    def log_request(self, code="-", size="-"):
        path = urllib.parse.urlsplit(self.path).path
        self.log_message("%s %s %s", self.command, path, code)

    def _set_headers(self, status=200, content_type="application/json", cache_control="no-store"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", cache_control)
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()

    def _json(self, status, payload):
        self._set_headers(status, "application/json; charset=utf-8")
        self.wfile.write(json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"))

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        params = urllib.parse.parse_qs(parsed_url.query)

        # 1. Servir Frontend (index.html)
        if path == "/" or path == "/index.html":
            file_path = os.path.join(BASE_DIR, "index.html")
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    self._set_headers(200, "text/html; charset=utf-8")
                    self.wfile.write(f.read())
            else:
                self._set_headers(404, "text/plain")
                self.wfile.write(b"index.html nao encontrado")
            return

        if path == "/healthz":
            self._json(200, {"status": "ok"})
            return

        if path in STATIC_ASSETS:
            try:
                with open(os.path.join(BASE_DIR, path.lstrip("/")), "rb") as asset:
                    content = asset.read()
            except FileNotFoundError:
                self._json(404, {"error": "Imagem indisponível."})
                return
            policy = "public, max-age=604800, immutable" if path == "/assets/boa-vista-20261116.jpg" else "no-store"
            self._set_headers(200, STATIC_ASSETS[path], policy)
            self.wfile.write(content)
            return

        if path in ("/api/demarcation", "/api/condicoes-completas"):
            self._area_request(path, {key: values[0] for key, values in params.items()})
            return

        # 4. Endpoint: /api/agenda-manejo (Calendário Fenoclimático e Lembretes de Roraima)
        if path == "/api/agenda-manejo":
            self._json(200, AGENDA_RR)
            return

        # 6. Endpoint legado: /api/weather-rotation
        if path == "/api/weather-rotation":
            lat = float(params.get("lat", [1.8984])[0])
            lon = float(params.get("lon", [-60.6906])[0])
            start_date = params.get("start", ["20241001"])[0]
            end_date = params.get("end", ["20250228"])[0]

            try:
                weather_data = fetch_weather_data(latitude=lat, longitude=lon, start_date=start_date, end_date=end_date)
                summary = summarize_weather(weather_data["daily_records"])
                crop_evaluations = {}
                for key, passport in MATRIZ_PASSAPORTE.items():
                    crop_evaluations[key] = evaluate_with_biological_passport(passport, summary)
                strat = compare_three_rotation_strategies(weather_summary=summary)

                payload = {
                    "summary": summary,
                    "crop_evaluations": crop_evaluations,
                    "rotation_plan": strat["estrategias"]
                }
                self._set_headers(200)
                self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        # 7. Endpoint legado: /api/sentinel-ndvi
        if path == "/api/sentinel-ndvi":
            car_code = params.get("car", [None])[0]
            try:
                if not car_code:
                    self._json(400, {"error": "Informe o código CAR para consultar o NDVI."})
                    return
                land = query_land_demarcation(car_code)
                geom = land["geojson"]["geometry"]
                ndvi_result = calculate_ndvi_analysis(geom)
                ndvi_result["cod_imovel"] = land.get("cod_imovel")
                self._json(200, ndvi_result)
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
            except LookupError:
                self._json(404, {"error": "Imóvel CAR não localizado."})
            except OSError:
                self._json(503, {"error": "Consulta de perímetro CAR indisponível."})
            return

        self._set_headers(404)
        self.wfile.write(json.dumps({"error": "Rota nao encontrada"}).encode("utf-8"))

    def _area_request(self, path, params):
        if any(key in params and not isinstance(params[key], str) for key in ("car", "uf")):
            self._json(400, {"error": "CAR e UF devem ser textos."})
            return
        if path == "/api/mapa-satelite":
            self._satellite_map(params.get("car"), params.get("recorte"), params.get("formato", "png"))
            return
        # 2. Endpoint: /api/demarcation (Busca por CAR ou Coordenada)
        if path == "/api/demarcation":
            car_code = params.get("car", None)
            lat = params.get("lat", None)
            lon = params.get("lon", None)
            uf = params.get("uf", "rr")

            try:
                if car_code:
                    result = query_land_demarcation(car_code)
                elif lat is not None and lon is not None:
                    result = query_land_by_point(*coordinates(lat, lon), uf=uf)
                else:
                    self._json(400, {"error": "Informe o CAR ou as coordenadas."})
                    return

                self._json(200, result)
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
            except LookupError:
                self._json(404, {"error": "Imóvel CAR não localizado."})
            except OSError:
                self._json(503, {"error": "Consulta de perímetro CAR indisponível."})
            return

        # 3. Endpoint: /api/condicoes-completas (Diagnóstico Agroclimático - Etapa 6)
        if path == "/api/condicoes-completas":
            try:
                car = params.get("car")
                crops = params.get("culturas", [])
                if not isinstance(crops, list) or len(crops) > 6 or any(not isinstance(crop, str) for crop in crops):
                    raise ValueError("Informe as culturas do talhão em uma lista.")
                geometry = None
                if "contorno" in params:
                    ring = parse_ring(params["contorno"])
                    geometry = {"type": "Polygon", "coordinates": [ring]}
                    point = perimeter_reference(geometry)
                    lat, lon = coordinates(point.get("latitude"), point.get("longitude"))
                elif car:
                    land = query_land_demarcation(car)
                    geometry = (land.get("geojson") or {}).get("geometry")
                    point = land.get("centroid") or {}
                    lat, lon = coordinates(point.get("latitude"), point.get("longitude"))
                else:
                    lat, lon = coordinates(params.get("lat"), params.get("lon"))
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
                return
            except LookupError:
                self._json(404, {"error": "CAR não localizado."})
                return
            except OSError:
                self._json(503, {"error": "Consulta de perímetro CAR indisponível."})
                return

            self._json(200, area_diagnosis(lat, lon, geometry, dict.fromkeys(crops)))
            return

    def _satellite_map(self, car, recorte, formato):
        # Vista pública de Boa Vista enquanto o usuário não informa um CAR.
        bounds = (-60.9, 2.6, -60.44, 3.04)
        try:
            if formato not in ("jpeg", "png"):
                raise ValueError("Formato de imagem inválido.")
            image_type = "image/" + formato
            if recorte is not None:
                if not isinstance(recorte, list) or len(recorte) != 4 or any(
                    type(value) not in (int, float) for value in recorte
                ):
                    raise ValueError("Recorte inválido.")
                west, south, east, north = recorte
                # Limita as consultas de detalhe à região atendida no norte do Brasil.
                if not (-66 <= west < east <= -58 and -3 <= south < north <= 6
                        and east - west <= .25 and north - south <= .25):
                    raise ValueError("O recorte está fora da região ou do nível de zoom atendido.")
                bounds = tuple(round(value, 4) for value in recorte)
            elif car:
                geometry = query_land_demarcation(car)["geojson"]["geometry"]
                x, y = zip(*[(point[0], point[1]) for point in exterior_points(geometry)])
                padding = max(max(x) - min(x), max(y) - min(y), 0.002) * 0.3
                bounds = (min(x) - padding, min(y) - padding, max(x) + padding, max(y) + padding)
            west, south, east, north = bounds
            if not (-180 <= west < east <= 180 and -85 <= south < north <= 85):
                raise ValueError("Limites inválidos para gerar a imagem.")
            image, resolution = fetch_satellite_image(bounds, datetime.now(timezone.utc).date(), image_type)
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
        except LookupError:
            self._json(404, {"error": "Imóvel CAR não localizado."})
        except OSError:
            self._json(503, {"error": "Imagem de satélite indisponível."})
        else:
            self._json(200, {
                "bounds": [[south, west], [north, east]],
                "image": f"data:{image_type};base64," + base64.b64encode(image).decode("ascii"),
                "resolucao_m": resolution,
            })

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        content_length = int(self.headers.get("Content-Length", 0))
        if path in ("/api/validar-talhao", "/api/condicoes-completas") and content_length > 65536:
            self._json(413, {"error": "Contorno grande demais."})
            return
        try:
            body_str = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            body_data = json.loads(body_str)
        except ValueError:
            self._json(400, {"error": "JSON inválido."})
            return

        if not isinstance(body_data, dict):
            self._json(400, {"error": "Envie um objeto JSON."})
            return
        if path == "/api/validar-talhao":
            car = body_data.get("car", "")
            plot = body_data.get("talhao_id")
            others = body_data.get("outros", {})
            if (not isinstance(car, str) or plot not in ("T1", "T2", "T3") or not isinstance(others, dict)
                    or any(key not in ("T1", "T2", "T3") or key == plot for key in others)):
                self._json(400, {"error": "Parâmetros inválidos para o talhão."})
                return
            try:
                geometry = query_land_demarcation(car)["geojson"]["geometry"] if car else None
                result = validate_plot(body_data.get("contorno"), geometry, others)
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
            except LookupError:
                self._json(404, {"error": "CAR não localizado."})
            except OSError:
                self._json(503, {"error": "Não foi possível validar o perímetro do CAR."})
            else:
                self._json(200, result)
            return
        if path in ("/api/demarcation", "/api/condicoes-completas", "/api/mapa-satelite"):
            self._area_request(path, body_data)
            return

        # 1. Endpoint: /api/simular-rotacao (Comparativo Obrigatório de 3 Estratégias)
        if path == "/api/simular-rotacao":
            cultura = body_data.get("cultura_atual", "mandioca")
            objetivo = body_data.get("objetivo", "saude_solo")
            horizonte = body_data.get("periodo_anos", 3)
            area = body_data.get("area_ha")
            if cultura not in ("mandioca", "milho", "feijao_caupi"):
                self._json(400, {"error": "Selecione mandioca, milho ou feijão-caupi para simular."})
                return
            if objetivo not in ("saude_solo", "renda", "clima") or horizonte not in (2, 3, 4, "2", "3", "4"):
                self._json(400, {"error": "Selecione um objetivo válido e um horizonte de 2 a 4 anos."})
                return
            if area is not None and (type(area) not in (int, float) or not 0 <= area < float("inf")):
                self._json(400, {"error": "Área do talhão inválida."})
                return

            res = compare_three_rotation_strategies(
                current_crop=cultura, objective=objetivo, horizon_years=int(horizonte)
            )
            self._json(200, {"talhao_id": body_data.get("talhao_id"), "area_ha": area, **res})
            return

        if path in ("/api/planos", "/api/cadastrar-produtor"):
            if not is_supabase_configured():
                self._json(503, {"error": "Armazenamento Supabase indisponível."})
                return
            try:
                self._json(201, salvar_plano(body_data))
            except ValueError as exc:
                self._json(400, {"error": str(exc)})
            except OSError:
                self._json(503, {"error": "O Supabase não confirmou a gravação."})
            return
        self._set_headers(404)
        self.wfile.write(json.dumps({"error": "Rota POST nao encontrada"}).encode("utf-8"))


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True

def run_server(port=PORT):
    server_address = ("", port)
    httpd = ReusableThreadingHTTPServer(server_address, AgroHandler)
    print("=" * 70)
    print(f"[ONLINE] Servidor AgroFamiliar Mobile-First iniciado em: http://localhost:{port}")
    print(f"[MAPA] Interface interativa Poppins com suporte a 3 Estratégias e Agenda!")
    print("=" * 70)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
        httpd.server_close()


if __name__ == "__main__":
    p = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    run_server(p)
