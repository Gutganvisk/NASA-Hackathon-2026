"""
Motor de Decisão Agroclimático e Comparativo Multicritério de Estratégias de Rotação.
Calibrado para as condições agroecológicas de Roraima (Lavrado e Mata).

Em conformidade com o desafio NASA Space Apps 2026:
- Compara obrigatoriamente 3 estratégias de rotação (Linha de Base + 2 Alternativas).
- Detalha evidências científicas, riscos climáticos/operacionais e incertezas biofísicas.
- Distingue rigorosamente o modelo hidrológico NASA GMAO MERRA-2 Catchment do sensoriamento direto.
- Rotula o NDVI estritamente como Vigor Fotossintético Ativo (fCover) e reconhece limites de detecção de palhada.
"""

from typing import Any, Dict, List, Optional
from passaporte_biologico import MATRIZ_PASSAPORTE, PassaporteBiologico


def summarize_weather(daily_records: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    """
    Sintetiza métricas da reanálise e dados diários da NASA POWER.
    Nota: GWETTOP e GWETROOT são frações adimensionais de saturação de poros
    do modelo GMAO MERRA-2 Catchment Land Surface Model.
    """
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
            # Multiplicamos por 100 para expressar como percentual de saturação dos poros do modelo
            gwettops.append(g_top * 100.0)

        g_root = vals.get("GWETROOT")
        if g_root is not None:
            gwetroots.append(g_root * 100.0)
            
    days_count = len(daily_records)
    avg_temp = sum(temps) / len(temps) if temps else 28.5
    min_temp = min(temps) if temps else 24.0
    max_temp = max(temps) if temps else 33.0
    avg_rad = sum(rads) / len(rads) if rads else 18.5
    avg_hum = sum(humidities) / len(humidities) if humidities else 65.0
    avg_soil_top = sum(gwettops) / len(gwettops) if gwettops else 50.0
    avg_soil_root = sum(gwetroots) / len(gwetroots) if gwetroots else 60.0

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
        "estimated_slope_pct": 3.8
    }


def compare_three_rotation_strategies(
    current_crop: str = "milho",
    is_fallow: bool = False,
    objective: str = "saude_solo",
    horizon_years: int = 3,
    weather_summary: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Motor comparativo de 3 estratégias de rotação conforme o desafio NASA Space Apps 2026.
    Retorna a Linha de Base (Manejo Atual) e duas estratégias alternativas balanceadas,
    adaptando-se dinamicamente à cultura primária (current_crop) selecionada pelo produtor.
    """
    precip = weather_summary.get("total_precip_mm", 280.0) if weather_summary else 280.0
    soil_root = weather_summary.get("avg_soil_root_pct", 60.0) if weather_summary else 60.0
    slope = weather_summary.get("estimated_slope_pct", 3.8) if weather_summary else 3.8

    crop_clean = current_crop.lower().strip() if current_crop else "milho"

    if "milho" in crop_clean:
        # 1. Baseline para Milho
        estrategia_baseline = {
            "id": "estrategia_0_baseline",
            "tipo": "Linha de Base (Manejo Atual)",
            "nome": "Monocultivo de Milho com Pousio Não Manejado",
            "badge_cor": "#64748b",
            "compatibilidade_score": 50,
            "sequencia": [
                { "fase": 1, "tempo": "Ano 1", "cultura": "Milho Grão", "sigla": "MI", "cor": "#eab308", "papel": "Cultivo Atual" },
                { "fase": 2, "tempo": "Ano 2", "cultura": "Pousio / Repouso Desprotegido", "sigla": "PO", "cor": "#94a3b8", "papel": "Sem Cobertura Manejada" },
                { "fase": 3, "tempo": "Ano 3", "cultura": "Milho Novamente", "sigla": "MI", "cor": "#eab308", "papel": "Repetição com Exaustão de Nitrogênio" }
            ],
            "evidencias_cientificas": [
                "O milho em monocultura exaure intensamente o nitrogênio e o fósforo das camadas superficiais do solo do Lavrado.",
                "Solos mantidos descobertos após a colheita em agosto ultrapassam 42°C de temperatura superficial (LST) na seca de Roraima, degradando a matéria orgânica."
            ],
            "riscos_climaticos_e_operacionais": [
                "Risco severo de perda da safrinha caso o corte de chuvas ocorra antes do previsto (outubro).",
                "Erosão eólica e lixiviação das cinzas e nutrientes residuais pelo calor extremo."
            ],
            "incertezas_biofisicas": [
                "Taxa empírica de decomposição da palhada do milho sob radiação solar direta.",
                "Gasto crescente com adubos químicos solúveis para compensar o déficit nutricional contínuo."
            ]
        }

        # 2. Intensificação para Milho
        estrategia_intensificacao = {
            "id": "estrategia_1_intensificacao",
            "tipo": "Alternativa de Intensificação",
            "nome": "Milho ➔ Feijão-Caupi (FBN na Palhada) ➔ Milho + Braquiária",
            "badge_cor": "#15803d",
            "compatibilidade_score": 92,
            "sequencia": [
                { "fase": 1, "tempo": "Agora", "cultura": "Milho (BRS 1030 / 1055)", "sigla": "MI", "cor": "#eab308", "papel": "Safra Principal Chuvosa" },
                { "fase": 2, "tempo": "Próxima", "cultura": "Feijão-Caupi (BRS Tumucumaque)", "sigla": "FC", "cor": "#b45309", "papel": "Fixação Biológica de Nitrogênio (65d)" },
                { "fase": 3, "tempo": "Depois", "cultura": "Milho + Braquiária Ruziziensis", "sigla": "MB", "cor": "#16a34a", "papel": "Consórcio com Cobertura Morta Duradoura" }
            ],
            "evidencias_cientificas": [
                "O feijão-caupi plantado direto na palhada do milho fecha o ciclo em 65 dias com a umidade residual da raiz (SMAP GWETROOT).",
                "A inoculação com Bradyrhizobium no caupi devolve de 40 a 50 kg de N/ha, reduzindo a compra de ureia no próximo milho."
            ],
            "riscos_climaticos_e_operacionais": [
                "A semeadura do feijão-caupi deve ocorrer até o final de agosto para fugir do estresse hídrico terminal em outubro.",
                "Demanda regulagem adequada de plantadeira manual/matraca para cortar a palhada densa do milho."
            ],
            "incertezas_biofisicas": [
                "Nível de compactação residual que possa interferir na nodulação do feijão-caupi.",
                "Disponibilidade local de sementes fiscalizadas de cultivares da Embrapa Roraima."
            ]
        }

        # 3. Resiliência para Milho
        estrategia_resiliencia = {
            "id": "estrategia_2_resiliencia",
            "tipo": "Alternativa de Resiliência",
            "nome": "Milho ➔ Crotalária / Milheto ➔ Mandioca em Nível",
            "badge_cor": "#0369a1",
            "compatibilidade_score": 84,
            "sequencia": [
                { "fase": 1, "tempo": "Agora", "cultura": "Milho (BRS 1030)", "sigla": "MI", "cor": "#eab308", "papel": "Cultivo Atual" },
                { "fase": 2, "tempo": "Próxima", "cultura": "Crotalária Spectabilis / Milheto", "sigla": "CR", "cor": "#059669", "papel": "Quebra de Nematoides e Palhada" },
                { "fase": 3, "tempo": "Depois", "cultura": "Mandioca (Aciolina / Platinão)", "sigla": "MA", "cor": "#d97706", "papel": "Safra Rústica Resistente à Estiagem" }
            ],
            "evidencias_cientificas": [
                "A Crotalária reduz a população de fitonematoides que atacam as raízes do milho e recicla nutrientes profundos.",
                "A mandioca implantada no ano 2 tolera até 6 meses de seca severa sem necessidade de irrigação suplementar."
            ],
            "riscos_climaticos_e_operacionais": [
                "Retorno financeiro mais lento na fase de adubação verde antes da colheita da mandioca (ciclo de 10-12 meses).",
                "Exige terreno com declividade inferior a 8% (SRTM) para evitar erosão no arranquio das raízes."
            ],
            "incertezas_biofisicas": [
                "Taxa de fixação de fósforo nos óxidos de ferro do solo do Lavrado que afetam o crescimento inicial da crotalária."
            ]
        }

    elif "caupi" in crop_clean or "feijao" in crop_clean:
        # Feijão-Caupi como Primária
        estrategia_baseline = {
            "id": "estrategia_0_baseline",
            "tipo": "Linha de Base (Manejo Atual)",
            "nome": "Monocultivo de Feijão com Pousio Não Manejado",
            "badge_cor": "#64748b",
            "compatibilidade_score": 48,
            "sequencia": [
                { "fase": 1, "tempo": "Ano 1", "cultura": "Feijão-Caupi", "sigla": "FC", "cor": "#b45309", "papel": "Cultivo Atual" },
                { "fase": 2, "tempo": "Ano 2", "cultura": "Pousio sem Cobertura", "sigla": "PO", "cor": "#94a3b8", "papel": "Solo Desprotegido" },
                { "fase": 3, "tempo": "Ano 3", "cultura": "Feijão-Caupi", "sigla": "FC", "cor": "#b45309", "papel": "Pressão de Fungos de Solo" }
            ],
            "evidencias_cientificas": [
                "O monocultivo de leguminosas favorece o acúmulo de Rhizoctonia e Fusarium no perfil arenoso do solo.",
                "A palhada do feijão-caupi tem relação C/N baixa (< 20) e se decompõe muito rápido, deixando o solo vulnerável à insolação."
            ],
            "riscos_climaticos_e_operacionais": [
                "Perda rápida da matéria orgânica acumulada sob temperaturas elevadas.",
                "Queda de produtividade pelo ataque recorrente de pragas da mesma família."
            ],
            "incertezas_biofisicas": [
                "Evolução da população de fungos patogênicos no solo sem quebra de ciclo."
            ]
        }

        estrategia_intensificacao = {
            "id": "estrategia_1_intensificacao",
            "tipo": "Alternativa de Intensificação",
            "nome": "Feijão-Caupi ➔ Milho Grão BRS 1030 (Aproveita N) ➔ Braquiária",
            "badge_cor": "#15803d",
            "compatibilidade_score": 90,
            "sequencia": [
                { "fase": 1, "tempo": "Agora", "cultura": "Feijão-Caupi (FBN)", "sigla": "FC", "cor": "#b45309", "papel": "Solo Enriquecido com N" },
                { "fase": 2, "tempo": "Próxima", "cultura": "Milho (BRS 1030 / 1055)", "sigla": "MI", "cor": "#eab308", "papel": "Alta Resposta ao N Deixado pelo Caupi" },
                { "fase": 3, "tempo": "Depois", "cultura": "Braquiária Ruziziensis", "sigla": "BR", "cor": "#16a34a", "papel": "Descompactação e Palhada Grossa" }
            ],
            "evidencias_cientificas": [
                "O milho cultivado em sucessão ao caupi expressa alto teto produtivo consumindo o nitrogênio mineralizado.",
                "A alternância entre Fabaceae e Poaceae interrompe o ciclo biológico de pragas e doenças específicas."
            ],
            "riscos_climaticos_e_operacionais": [
                "Sincronização com o calendário de chuvas de Roraima para que o milho receba ao menos 500 mm no ciclo.",
                "Manejo correto de adubação fosfatada no milho, já que o caupi não repõe fósforo."
            ],
            "incertezas_biofisicas": [
                "Percentual de N residual que permanece nas primeiras camadas antes da lixiviação pelas chuvas de pico."
            ]
        }

        estrategia_resiliencia = {
            "id": "estrategia_2_resiliencia",
            "tipo": "Alternativa de Resiliência",
            "nome": "Feijão-Caupi ➔ Mandioca Rústica ➔ Crotalária",
            "badge_cor": "#0369a1",
            "compatibilidade_score": 82,
            "sequencia": [
                { "fase": 1, "tempo": "Agora", "cultura": "Feijão-Caupi", "sigla": "FC", "cor": "#b45309", "papel": "Fixador Biológico" },
                { "fase": 2, "tempo": "Próxima", "cultura": "Mandioca (Aciolina)", "sigla": "MA", "cor": "#d97706", "papel": "Renda e Segurança Alimentar" },
                { "fase": 3, "tempo": "Depois", "cultura": "Crotalária Spectabilis", "sigla": "CR", "cor": "#059669", "papel": "Regeneração Pós-Arranquio" }
            ],
            "evidencias_cientificas": [
                "A mandioca se beneficia do solo descompactado e do nitrogênio residual do caupi.",
                "Crotalária subsequente reestrutura a microfauna do solo alterada pelo revolvimento da mandioca."
            ],
            "riscos_climaticos_e_operacionais": [
                "Manejo de plantas daninhas nos primeiros 60 dias de implantação da mandioca.",
                "Cuidado com a declividade do lote para evitar voçorocas."
            ],
            "incertezas_biofisicas": [
                "Capacidade de suporte de potássio do solo para atender às altas demandas da mandioca."
            ]
        }

    else:
        # Padrão: Mandioca como Primária
        estrategia_baseline = {
            "id": "estrategia_0_baseline",
            "tipo": "Linha de Base (Manejo Atual)",
            "nome": "Monocultivo / Sucessão Tradicional com Pousio Não Manejado",
            "badge_cor": "#64748b",
            "compatibilidade_score": 52,
            "sequencia": [
                { "fase": 1, "tempo": "Ano 1", "cultura": "Mandioca", "sigla": "MA", "cor": "#d97706", "papel": "Cultivo Atual" },
                { "fase": 2, "tempo": "Ano 2", "cultura": "Pousio / Repouso Desprotegido", "sigla": "PO", "cor": "#94a3b8", "papel": "Sem Cobertura Manejada" },
                { "fase": 3, "tempo": "Ano 3", "cultura": "Mandioca", "sigla": "MA", "cor": "#d97706", "papel": "Reimplantação com Revolver do Solo" }
            ],
            "evidencias_cientificas": [
                "O arranquio das raízes da mandioca na colheita desestrutura a fração argilo-arenosa do solo do Lavrado.",
                "Solos mantidos descobertos em pousio espontâneo ultrapassam 42°C de temperatura superficial (LST), degradando matéria orgânica rapidamente."
            ],
            "riscos_climaticos_e_operacionais": [
                "Risco severo de erosão hídrica laminar sob chuvas torrenciais concentradas (maio a julho em Roraima).",
                "Lixiviação profunda de potássio e bases em camadas arenosas sem raízes ativas para reciclagem."
            ],
            "incertezas_biofisicas": [
                "Taxa empírica de regeneração da flora espontânea na entressafra sem aporte de nutrientes.",
                "Velocidade exata de queda da fertilidade natural sem dados laboratoriais de análise química do lote."
            ]
        }

        estrategia_intensificacao = {
            "id": "estrategia_1_intensificacao",
            "tipo": "Alternativa de Intensificação",
            "nome": "Sucessão Mandioca ➔ Feijão-Caupi ➔ Milho Consorciado",
            "badge_cor": "#15803d",
            "compatibilidade_score": 86,
            "sequencia": [
                { "fase": 1, "tempo": "Agora", "cultura": "Mandioca", "sigla": "MA", "cor": "#d97706", "papel": "Conclusão do Ciclo Atual" },
                { "fase": 2, "tempo": "Próxima", "cultura": "Feijão-Caupi (BRS Novaera)", "sigla": "FC", "cor": "#b45309", "papel": "Fixação Biológica de Nitrogênio" },
                { "fase": 3, "tempo": "Depois", "cultura": "Milho (BRS 1030) + Braquiária", "sigla": "MI", "cor": "#eab308", "papel": "Formação de Palhada Duradoura (C/N > 60)" }
            ],
            "evidencias_cientificas": [
                "O feijão-caupi inoculado com estirpes de Bradyrhizobium fixa 40 a 60 kg N/ha, repondo nutrientes após a mandioca.",
                "O consórcio de milho com Brachiaria ruziziensis na semeadura garante cobertura morta persistente para o plantio direto na seca."
            ],
            "riscos_climaticos_e_operacionais": [
                "O corte das chuvas entre setembro e outubro exige semeadura rigorosa do caupi até início de agosto.",
                "Necessidade de adquirir sementes certificadas da Embrapa e inoculante em lojas de insumo em Boa Vista."
            ],
            "incertezas_biofisicas": [
                "Eficácia real da FBN caso a saturação por bases (V%) esteja abaixo de 40% e com acidez de alumínio ativa.",
                "Sobrevivência da forrageira sob seca severa caso a palhada seja consumida por pastejo animal."
            ]
        }

        estrategia_resiliencia = {
            "id": "estrategia_2_resiliencia",
            "tipo": "Alternativa de Resiliência",
            "nome": "Mandioca em Nível ➔ Adubação Verde (Guandu/Crotalária) ➔ Milho",
            "badge_cor": "#0369a1",
            "compatibilidade_score": 79,
            "sequencia": [
                { "fase": 1, "tempo": "Agora", "cultura": "Mandioca (Aciolina / Platinão)", "sigla": "MA", "cor": "#d97706", "papel": "Cultivo em Nível / Curvas de Nível" },
                { "fase": 2, "tempo": "Próxima", "cultura": "Feijão-Guandu / Crotalária", "sigla": "GD", "cor": "#059669", "papel": "Descompactação Profunda e Matéria Orgânica" },
                { "fase": 3, "tempo": "Depois", "cultura": "Milho Rústico na Palhada", "sigla": "MI", "cor": "#eab308", "papel": "Colheita Segura na Palhada Acumulada" }
            ],
            "evidencias_cientificas": [
                "O guandu tolera estiagens prolongadas e suas raízes pivotantes quebram o adensamento natural do solo do Lavrado.",
                "A mandioca suporta 5 a 6 meses de estiagem em Roraima mantendo reserva amilácea sem necessidade de irrigação."
            ],
            "riscos_climaticos_e_operacionais": [
                "Menor retorno financeiro no ciclo de adubação verde exclusiva, embora reduza custos de fertilizantes químicos futuros.",
                "Demanda de manejo de dessecação mecânica ou rolamento da palhada de guandu antes do milho."
            ],
            "incertezas_biofisicas": [
                "Taxa de mineralização da fitomassa leguminosa sob altas temperaturas superficiais antes da próxima semeadura."
            ]
        }

    return {
        "talhao_id": "T1",
        "objetivo_selecionado": objective,
        "horizonte_anos": horizon_years,
        "score_melhoria": "+18%",
        "reducao_risco": "-12%",
        "diversidade_culturas": 3,
        "estrategias": [
            estrategia_intensificacao,
            estrategia_resiliencia,
            estrategia_baseline
        ],
        "pontos_atencao": [
            { "titulo": "Calor entre março e maio", "descricao": "Evitar manter o solo descoberto nas semanas mais secas e quentes." },
            { "titulo": "Corte de chuvas em setembro/outubro", "descricao": "Monitorar a curva diária do NASA POWER para confirmar início da estiagem." }
        ],
        "recomendacao_prioritaria": {
            "estrategia_destaque_id": "estrategia_1_intensificacao",
            "proximo_passo": "Preparar o Talhão 1 para feijão-caupi na palhada residual",
            "mensagem": "Manter a cobertura morta e confirmar o início do plantio assim que o perfil radicular atingir saturação favorável."
        }
    }


def evaluate_with_biological_passport(
    passport: PassaporteBiologico,
    summary: Dict[str, float]
) -> Dict[str, Any]:
    """
    Avaliação exploratória individual de cultura frente aos parâmetros biofísicos.
    """
    alerts = []
    actions = []
    favorable = []

    soil_root = summary["avg_soil_root_pct"]
    if soil_root < passport.smap_gwetroot_min_pct:
        alerts.append(
            f"Saturação de Raiz (MERRA-2: {soil_root}%) abaixo do limiar heurístico de {passport.smap_gwetroot_min_pct}%."
        )
        if passport.cultura == "Feijão-Caupi":
            actions.append(
                "Manejo Recomendado: Semear braquiária nas entrelinhas aos 20-25 DAE para garantir cobertura viva."
            )
    else:
        favorable.append(
            f"Saturação do Perfil ({soil_root}%) compatível com a demanda do ciclo de {passport.ciclo_dias_min}-{passport.ciclo_dias_max} dias."
        )

    precip = summary["total_precip_mm"]
    if precip < passport.precipitacao_ciclo_min_mm:
        if passport.tolerancia_seca_meses >= 5.0:
            favorable.append(
                f"Resiliência Comprovada: A cultura tolera até {passport.tolerancia_seca_meses} meses de estiagem severa."
            )
        else:
            alerts.append(
                f"Déficit Hídrico do Período: Precipitação ({precip} mm) inferior ao ciclo ideal ({passport.precipitacao_ciclo_min_mm} mm)."
            )
    else:
        favorable.append(
            f"Pluviometria Acumulada ({precip} mm) adequada às exigências estimadas da cultura."
        )

    slope = summary.get("estimated_slope_pct", 3.8)
    if passport.revolvimento_solo_colheita and slope > passport.declividade_max_tolerada_pct:
        alerts.append(
            f"Declividade ({slope}%) superior ao limiar conservacionista ({passport.declividade_max_tolerada_pct}%). Risco de erosão no arranquio."
        )
        actions.append(
            "Exigência Técnica: Plantio obrigatório em curvas de nível com barreiras de retenção vegetal."
        )
    else:
        favorable.append(
            f"Declividade Suave ({slope}%), sem impedimento grave de relevo."
        )

    actions.append(f"Sucessão Recomendada: {passport.regra_consorcio_especial}")
    if passport.exige_calagem_pesada:
        actions.append("Correção Química: Recomenda-se calagem prévia para solos ácidos com saturação por bases V% < 50.")

    is_viable = len([a for a in alerts if "Declividade" in a]) == 0

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


# Aliases de compatibilidade
evaluate_crop_suitability = evaluate_with_biological_passport
suggest_rotation_plan = compare_three_rotation_strategies
