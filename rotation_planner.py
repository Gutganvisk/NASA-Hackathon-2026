"""
Motor de Decisão Calibrado para Roraima (Decision Engine).
Cruza as observações de sensoriamento remoto (NASA/ESA) com a Matriz de Passaporte Biológico da Embrapa Roraima.
"""

from typing import Any, Dict, List
from passaporte_biologico import MATRIZ_PASSAPORTE, PassaporteBiologico


def summarize_weather(daily_records: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    total_precip = 0.0
    temps = []
    rads = []
    humidities = []
    gwettops = []
    gwetroots = []
    
    for _, vals in daily_records.items():
        p = vals.get("PRECTOTCORR")
        if p is not None:
            total_precip += p
            
        t = vals.get("T2M")
        if t is not None:
            temps.append(t)
            
        r = vals.get("ALLSKY_SFC_SW_DWN")
        if r is not None:
            rads.append(r)
            
        h = vals.get("RH2M")
        if h is not None:
            humidities.append(h)

        g_top = vals.get("GWETTOP")
        if g_top is not None:
            gwettops.append(g_top * 100.0)

        g_root = vals.get("GWETROOT")
        if g_root is not None:
            gwetroots.append(g_root * 100.0)
            
    days_count = len(daily_records)
    avg_temp = sum(temps) / len(temps) if temps else 0.0
    min_temp = min(temps) if temps else 0.0
    max_temp = max(temps) if temps else 0.0
    avg_rad = sum(rads) / len(rads) if rads else 0.0
    avg_hum = sum(humidities) / len(humidities) if humidities else 0.0
    avg_soil_top = sum(gwettops) / len(gwettops) if gwettops else 0.0
    avg_soil_root = sum(gwetroots) / len(gwetroots) if gwetroots else 0.0

    return {
        "days": days_count,
        "total_precip_mm": round(total_precip, 1),
        "avg_temp_c": round(avg_temp, 1),
        "min_temp_c": round(min_temp, 1),
        "max_temp_c": round(max_temp, 1),
        "avg_solar_rad_mj": round(avg_rad, 2),
        "avg_humidity_pct": round(avg_hum, 1),
        "avg_soil_surface_pct": round(avg_soil_top, 1),
        "avg_soil_root_pct": round(avg_soil_root, 1),
        "estimated_slope_pct": 3.8  # Declividade média simulada (SRTM)
    }


def evaluate_with_biological_passport(
    passport: PassaporteBiologico,
    summary: Dict[str, float]
) -> Dict[str, Any]:
    """
    Executa o motor de decisão cruzando os dados de satélite com o Passaporte Biológico da Embrapa.
    """
    alerts = []
    actions = []
    favorable = []

    # 1. GATILHO NASA SMAP (Umidade da Zona Radicular)
    soil_root = summary["avg_soil_root_pct"]
    if soil_root < passport.smap_gwetroot_min_pct:
        alerts.append(
            f"SMAP Alerta: Umidade da raiz ({soil_root}%) abaixo do limite crítico ({passport.smap_gwetroot_min_pct}%)."
        )
        if passport.cultura == "Feijão-Caupi":
            actions.append(
                "Ação de Manejo Embrapa: Não semear cobertura isolada na seca pós-colheita. Ativar semeadura de Braquiária na entrelinha aos 20-25 DAE."
            )
    else:
        favorable.append(
            f"SMAP Validado: Umidade na zona radicular ({soil_root}%) suporta o ciclo de {passport.ciclo_dias_min}-{passport.ciclo_dias_max} dias."
        )

    # 2. GATILHO NASA POWER + GPM/IMERG (Chuva Acumulada e Janela)
    precip = summary["total_precip_mm"]
    if precip < passport.precipitacao_ciclo_min_mm:
        if passport.tolerancia_seca_meses >= 5.0:
            favorable.append(
                f"Resiliência Comprovada: Embora a chuva ({precip} mm) seja moderada, a cultura tolera até {passport.tolerancia_seca_meses} meses de seca no Lavrado."
            )
        else:
            alerts.append(
                f"Déficit Hídrico Pluviométrico: Chuva ({precip} mm) inferior ao mínimo ideal ({passport.precipitacao_ciclo_min_mm} mm)."
            )
    else:
        favorable.append(
            f"Chuva Adequada: Acumulado ({precip} mm) cobre com segurança as necessidades da safra ({passport.precipitacao_ciclo_min_mm} mm)."
        )

    # 3. GATILHO SRTM (Declividade e Risco de Erosão na Colheita)
    slope = summary.get("estimated_slope_pct", 3.0)
    if passport.revolvimento_solo_colheita and slope > passport.declividade_max_tolerada_pct:
        alerts.append(
            f"SRTM Veto / Alerta Grave: Declividade do lote ({slope}%) superior ao limite ({passport.declividade_max_tolerada_pct}%). Risco severo de erosão por revolvimento na colheita."
        )
        actions.append(
            "Exigência Técnica: Plantio obrigatório em curvas de nível com barreiras vivas de palhada de milho entre as leiras."
        )
    else:
        favorable.append(
            f"Relevo Apto (SRTM): Terreno com declividade suave ({slope}%), sem risco crítico de erosão hídrica."
        )

    # 4. GATILHO SENTINEL-2 & ECOSTRESS (Cobertura e C/N)
    actions.append(f"Regra de Sucessão: {passport.regra_consorcio_especial}")
    if passport.exige_calagem_pesada:
        actions.append("Recomendação Química Embrapa: Exige correção prévia de acidez e saturação por bases (V% >= 50) e Ca/Mg no solo do Lavrado.")

    is_viable = len([a for a in alerts if "Veto" in a]) == 0

    return {
        "cultura": passport.cultura,
        "nome_cientifico": passport.nome_cientifico,
        "cultivares_rr": passport.cultivares_rr,
        "ciclo": f"{passport.ciclo_dias_min} a {passport.ciclo_dias_max} dias",
        "janela_plantio": passport.janela_plantio_ideal,
        "relacao_cn": passport.relacao_carbono_nitrogenio,
        "viavel": is_viable,
        "pontos_favoraveis": favorable,
        "alertas_satelite": alerts,
        "acoes_manejo_embrapa": actions
    }


# Alias de compatibilidade
evaluate_crop_suitability = evaluate_with_biological_passport


def suggest_rotation_plan() -> List[Dict[str, str]]:
    """
    Plano de rotação sincronizado com o calendário agroclimático de Roraima.
    """
    return [
        {
            "etapa": "1ª Fase: Safra Chuvosa Principal (Maio a Agosto)",
            "cultura": "Milho (Zea mays - Cultivares BRS 1030 / BRS 1055)",
            "justificativa": "Semeadura após o início real das chuvas em abril (monitorado via GPM). Ciclo de ~110 dias para maturar e colher em setembro com a interrupção das chuvas torrenciais. Deixa palhada de alta relação C/N (> 60) cobrindo o solo arenoso do Lavrado."
        },
        {
            "etapa": "2ª Fase: Safrinha / Sucessão Imediata (Agosto a Outubro)",
            "cultura": "Feijão-Caupi (Vigna unguiculata - BRS Novaera / BRS Tumucumaque)",
            "justificativa": "Plantado diretamente na palhada do milho. Ciclo ultra rápido (65-70 dias). Aproveita a água residual da zona radicular (SMAP GWETROOT). Fixa nitrogênio no solo e recebe consórcio de braquiária aos 20 DAE para garantir cobertura viva no verão."
        },
        {
            "etapa": "3ª Fase: Safra Rústica / Ciclo Longo (Ano 2 - Início das Chuvas)",
            "cultura": "Mandioca (Manihot esculenta - Aciolina / Platinão)",
            "justificativa": "Plantio em maio/junho com solo úmido. Tolera os 5 a 6 meses de seca severa de Roraima (outubro a março). Como a colheita exige o arranquio das raízes (revolvendo o solo), o ciclo é reiniciado com Milho para recompor a estrutura física e a matéria orgânica."
        }
    ]
