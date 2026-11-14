"""
Servidor HTTP leve para o Aplicativo de Cadastro e Demarcação de Terras.
Integrado com base de dados local / Supabase e NASA POWER.
"""

import json
import os
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from copernicus_sentinel2 import calculate_ndvi_analysis
from land_demarcation import query_land_by_point, query_land_demarcation
from nasa_power import fetch_weather_data
from passaporte_biologico import MATRIZ_PASSAPORTE
from rotation_planner import (
    evaluate_with_biological_passport,
    suggest_rotation_plan,
    summarize_weather,
)

PORT = 8080
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class AgroHandler(BaseHTTPRequestHandler):

    def _set_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

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

        # 2. Endpoint: /api/demarcation (Busca por CAR ou Coordenada)
        if path == "/api/demarcation":
            car_code = params.get("car", [None])[0]
            lat = params.get("lat", [None])[0]
            lon = params.get("lon", [None])[0]
            uf = params.get("uf", ["rr"])[0]

            try:
                if car_code:
                    result = query_land_demarcation(car_code)
                elif lat and lon:
                    result = query_land_by_point(float(lat), float(lon), uf=uf)
                else:
                    self._set_headers(400)
                    self.wfile.write(json.dumps({"error": "Informe 'car' ou 'lat'/'lon'"}).encode("utf-8"))
                    return

                self._set_headers(200)
                self.wfile.write(json.dumps(result).encode("utf-8"))
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        # 3. Endpoint: /api/weather-rotation (NASA POWER + Rotação)
        if path == "/api/weather-rotation":
            lat = params.get("lat", [None])[0]
            lon = params.get("lon", [None])[0]
            start_date = params.get("start", ["20241001"])[0]
            end_date = params.get("end", ["20250228"])[0]

            if not lat or not lon:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Latitude e Longitude obrigatorias"}).encode("utf-8"))
                return

            try:
                weather_data = fetch_weather_data(
                    latitude=float(lat),
                    longitude=float(lon),
                    start_date=start_date,
                    end_date=end_date
                )
                summary = summarize_weather(weather_data["daily_records"])
                
                crop_evaluations = {}
                for key, passport in MATRIZ_PASSAPORTE.items():
                    crop_evaluations[key] = evaluate_with_biological_passport(passport, summary)

                rotation_plan = suggest_rotation_plan()

                payload = {
                    "summary": summary,
                    "crop_evaluations": crop_evaluations,
                    "rotation_plan": rotation_plan
                }

                self._set_headers(200)
                self.wfile.write(json.dumps(payload).encode("utf-8"))
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        # 4. Endpoint: /api/sentinel-ndvi (Copernicus CDSE Sentinel-2 Process API)
        if path == "/api/sentinel-ndvi":
            car_code = params.get("car", [None])[0]
            lat = params.get("lat", [None])[0]
            lon = params.get("lon", [None])[0]

            try:
                if car_code:
                    land = query_land_demarcation(car_code)
                elif lat and lon:
                    land = query_land_by_point(float(lat), float(lon))
                else:
                    self._set_headers(400)
                    self.wfile.write(json.dumps({"error": "Informe 'car' ou 'lat'/'lon'"}).encode("utf-8"))
                    return

                geom = land["geojson"]["geometry"]
                ndvi_result = calculate_ndvi_analysis(geom)
                ndvi_result["cod_imovel"] = land.get("cod_imovel")

                self._set_headers(200)
                self.wfile.write(json.dumps(ndvi_result).encode("utf-8"))
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        self._set_headers(404)
        self.wfile.write(json.dumps({"error": "Rota nao encontrada"}).encode("utf-8"))

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        # Endpoint: /api/cadastrar-produtor
        if path == "/api/cadastrar-produtor":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                # Simula gravação bem-sucedida do agricultor vinculado ao CAR
                response_data = {
                    "sucesso": True,
                    "mensagem": "Agricultor familiar cadastrado e vinculado ao imóvel com sucesso!",
                    "id": "produtor_" + os.urandom(4).hex(),
                    "dados": data
                }
                self._set_headers(201)
                self.wfile.write(json.dumps(response_data).encode("utf-8"))
            except Exception as e:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        self._set_headers(404)
        self.wfile.write(json.dumps({"error": "Rota nao encontrada"}).encode("utf-8"))


def run_server(port=PORT):
    server_address = ("", port)
    httpd = HTTPServer(server_address, AgroHandler)
    print("=" * 70)
    print(f"[ONLINE] Servidor AgroFamiliar iniciado em: http://localhost:{port}")
    print(f"[MAPA] Acesse no navegador para visualizar o Formulario e Mapa!")
    print("=" * 70)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
        httpd.server_close()


if __name__ == "__main__":
    p = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    run_server(p)
