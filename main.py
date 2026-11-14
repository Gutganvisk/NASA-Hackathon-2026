"""
Ponto de entrada via terminal (CLI) do projeto Crop Rotation.
Executa o Motor de Decisão Agroclimático calibrado com o Passaporte Biológico da Embrapa Roraima
e dados de sensoriamento remoto (NASA POWER v2.0 + SMAP + GPM).
"""

import sys

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from nasa_power import fetch_weather_data
from passaporte_biologico import MATRIZ_PASSAPORTE
from rotation_planner import evaluate_with_biological_passport, suggest_rotation_plan, summarize_weather


def run_analysis(lat: float, lon: float, start_date: str, end_date: str, location_name: str = "Localidade Selecionada"):
    print("=" * 75)
    print(" [CROP ROTATION] ANALISE AGROCLIMATICA E DE SOLO (NASA POWER v2.0)")
    print(f" Local: {location_name} (Lat: {lat}, Lon: {lon})")
    print(f" Periodo Analisado: {start_date} ate {end_date}")
    print("=" * 75)
    print("\n[+] Coletando dados da NASA POWER (Clima + Umidade do Solo)...")

    try:
        data = fetch_weather_data(
            latitude=lat,
            longitude=lon,
            start_date=start_date,
            end_date=end_date
        )
    except Exception as e:
        print(f"\n[ERRO] Falha ao consultar a API NASA POWER: {e}")
        return

    records = data["daily_records"]
    if not records:
        print("\n[AVISO] Nenhum dado retornado para o periodo/coordenadas informados.")
        return

    summary = summarize_weather(records)

    print("\n[1. METRICAS ATMOSFERICAS (NASA POWER AG)]")
    print(f" - Dias analisados: {summary['days']} dias")
    print(f" - Precipitacao total acumulada (GPM/POWER): {summary['total_precip_mm']} mm")
    print(f" - Temperatura media: {summary['avg_temp_c']} °C (Min: {summary['min_temp_c']} °C | Max: {summary['max_temp_c']} °C)")
    print(f" - Radiacao solar media diaria: {summary['avg_solar_rad_mj']} MJ/m²/dia")
    print(f" - Umidade relativa do ar media: {summary['avg_humidity_pct']} %")

    print("\n[2. METRICAS DO SOLO E RELEVO (NASA SMAP + SRTM)]")
    print(f" - Umidade Superficial (0-5 cm / GWETTOP): {summary['avg_soil_surface_pct']} % (Saturacao)")
    print(f" - Umidade Zona Radicular (0-100 cm / GWETROOT): {summary['avg_soil_root_pct']} % (Saturacao)")
    print(f" - Declividade media do lote (SRTM): {summary['estimated_slope_pct']} %")

    print("\n" + "-" * 75)
    print(" [3. AVALIACAO DE APTIDAO - PASSAPORTE BIOLOGICO EMBRAPA RORAIMA]")
    print("-" * 75)

    for crop_key, passport in MATRIZ_PASSAPORTE.items():
        res = evaluate_with_biological_passport(passport, summary)
        status_tag = "[APTO]" if res["viavel"] else "[ALERTA]"
        cultivares = ", ".join(res["cultivares_rr"])
        print(f"\n{status_tag} Cultura: {res['cultura']} ({res['nome_cientifico']})")
        print(f"   Cultivares Embrapa RR: {cultivares}")
        print(f"   Ciclo Estimado: {res['ciclo']} | Janela Ideal: {res['janela_plantio']}")
        print(f"   Dinamica de Palhada: {res['relacao_cn']}")

        if res["pontos_favoraveis"]:
            print("   Pontos Favoraveis:")
            for pt in res["pontos_favoraveis"]:
                print(f"     + {pt}")

        if res["alertas_satelite"]:
            print("   Alertas / Limitantes:")
            for al in res["alertas_satelite"]:
                print(f"     ! {al}")

        if res["acoes_manejo_embrapa"]:
            print("   Prescricao de Manejo Embrapa:")
            for ac in res["acoes_manejo_embrapa"]:
                print(f"     * {ac}")

    print("\n" + "=" * 75)
    print(" [4. PLANO RECOMENDADO DE ROTACAO / SUCESSAO SINCRONIZADA]")
    print("=" * 75)
    plan = suggest_rotation_plan()
    for step in plan:
        print(f"\n>> {step['etapa']}")
        print(f"   Cultura: {step['cultura']}")
        print(f"   Fundamentacao Agronomica: {step['justificativa']}")

    print("\n" + "=" * 75)
    print("Analise concluida com sucesso!\n")


if __name__ == "__main__":
    # Coordenadas padrao: Polo Agricola de Caracarai / Boa Vista (Roraima)
    default_lat = 1.8984
    default_lon = -60.6906
    default_start = "20241001"
    default_end = "20250228"
    default_name = "Caracarai / Roraima (Gleba Rural SICAR RR-1400175)"

    if len(sys.argv) >= 5:
        lat = float(sys.argv[1])
        lon = float(sys.argv[2])
        start = sys.argv[3]
        end = sys.argv[4]
        name = sys.argv[5] if len(sys.argv) > 5 else "Coordenada Personalizada"
        run_analysis(lat, lon, start, end, name)
    else:
        run_analysis(default_lat, default_lon, default_start, default_end, default_name)
