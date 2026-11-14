"""
Matriz de Passaporte Biológico - Embrapa Roraima (Cerrados / Lavrado e Mata)
Funciona como o Dicionário de Tradução Agronômica para calibrar os sensores NASA/ESA.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PassaporteBiologico:
    cultura: str
    nome_cientifico: str
    cultivares_rr: List[str]               # Cultivares recomendadas pela Embrapa Roraima
    ciclo_dias_min: int
    ciclo_dias_max: int
    
    # 1. Calibragem NASA POWER & GPM (Chuva e Janela)
    janela_plantio_ideal: str              # Ex: 15/Abril a 10/Junho (evita falso início de março)
    corte_chuvas_limite: str               # Setembro/Outubro
    precipitacao_ciclo_min_mm: float
    tolerancia_seca_meses: float           # Quantos meses tolera de estiagem
    
    # 2. Calibragem NASA SMAP (Umidade do Solo)
    smap_gwetroot_min_pct: float           # Gatilho crítico na zona radicular (0-100cm)
    smap_gwettop_emergencia_pct: float     # Gatilho crítico na camada de 0-5cm
    
    # 3. Calibragem SRTM (Relevo / Declividade)
    revolvimento_solo_colheita: bool       # Se arranca raízes revolvendo o perfil
    declividade_max_tolerada_pct: float    # Se slope > limite, bloqueia ou exige curvas de nível
    
    # 4. Calibragem Sentinel-2 / Landsat & ECOSTRESS (Biomassa, C/N e LST)
    relacao_carbono_nitrogenio: str        # Alta (Milho), Média (Mandioca), Baixa (Caupi)
    potencial_cobertura_solo: str          # Excelente, Moderada, Baixa
    alerta_superaquecimento_lst: str       # Ação se ECOSTRESS detectar solo quente
    
    # 5. Calibragem Química e Manejo da Embrapa
    exige_calagem_pesada: bool             # Sensibilidade à acidez/Al3+ do Lavrado
    fixacao_biologica_n: bool              # FBN (bactérias inoculantes)
    regra_consorcio_especial: str          # Manejo de entrelinha / safrinha


MATRIZ_PASSAPORTE: Dict[str, PassaporteBiologico] = {
    "milho": PassaporteBiologico(
        cultura="Milho",
        nome_cientifico="Zea mays",
        cultivares_rr=["BRS 1030", "BRS 1055", "BRS 3046"],
        ciclo_dias_min=105,
        ciclo_dias_max=120,
        janela_plantio_ideal="15 de Abril a 31 de Maio (início real das chuvas confirmado por GPM)",
        corte_chuvas_limite="Final de Agosto / Início de Setembro",
        precipitacao_ciclo_min_mm=550.0,
        tolerancia_seca_meses=0.5,
        smap_gwetroot_min_pct=50.0,
        smap_gwettop_emergencia_pct=45.0,
        revolvimento_solo_colheita=False,
        declividade_max_tolerada_pct=15.0,
        relacao_carbono_nitrogenio="Alta (C/N > 60) - Palhada duradoura para o plantio direto",
        potencial_cobertura_solo="Excelente no fechamento do dossel (NDVI > 0.75)",
        alerta_superaquecimento_lst="Gera colchão térmico que reduz temperatura superficial do solo em até 8°C",
        exige_calagem_pesada=True,
        fixacao_biologica_n=False,
        regra_consorcio_especial="Consórcio com Braquiária ruziziensis na semeadura para formação massiva de palhada pós-colheita."
    ),

    "feijao_caupi": PassaporteBiologico(
        cultura="Feijão-Caupi",
        nome_cientifico="Vigna unguiculata",
        cultivares_rr=["BRS Novaera", "BRS Tumucumaque", "BRS Guariba", "BRS Itaim"],
        ciclo_dias_min=60,
        ciclo_dias_max=75,
        janela_plantio_ideal="Agosto a Setembro (sucessão imediata na palhada do milho)",
        corte_chuvas_limite="Outubro (utiliza água residual do solo detectada pelo SMAP)",
        precipitacao_ciclo_min_mm=300.0,
        tolerancia_seca_meses=1.0,
        smap_gwetroot_min_pct=40.0,
        smap_gwettop_emergencia_pct=38.0,
        revolvimento_solo_colheita=False,
        declividade_max_tolerada_pct=20.0,
        relacao_carbono_nitrogenio="Baixa (C/N ~ 15-20) - Decomposição rápida e liberação ágil de N",
        potencial_cobertura_solo="Moderada e temporária (NDVI médio 0.60)",
        alerta_superaquecimento_lst="Não tolera solo nu após Outubro; exige consórcio de cobertura antes da colheita",
        exige_calagem_pesada=False,
        fixacao_biologica_n=True,
        regra_consorcio_especial="Semear Braquiária ou Guandu-anão nas entrelinhas aos 20-25 dias após a emergência (DAE) para garantir cobertura viva na seca."
    ),

    "mandioca": PassaporteBiologico(
        cultura="Mandioca",
        nome_cientifico="Manihot esculenta",
        cultivares_rr=["Aciolina", "Platinão", "Pretinha", "BRS Dourada"],
        ciclo_dias_min=240,
        ciclo_dias_max=450,
        janela_plantio_ideal="Maio a Julho (aproveitando o solo úmido para brotação da maniva)",
        corte_chuvas_limite="Suporta toda a seca de Outubro a Março sem irrigação",
        precipitacao_ciclo_min_mm=600.0,
        tolerancia_seca_meses=6.0,
        smap_gwetroot_min_pct=30.0,
        smap_gwettop_emergencia_pct=35.0,
        revolvimento_solo_colheita=True,      # Arranquio na colheita desagrega o solo
        declividade_max_tolerada_pct=8.0,      # SRTM veta se for > 8% devido à erosão no Lavrado
        relacao_carbono_nitrogenio="Média (C/N ~ 30)",
        potencial_cobertura_solo="Baixa nos primeiros 90 dias (espaçamento largo deixa solo exposto)",
        alerta_superaquecimento_lst="Solo entre as leiras superaquece no verão do Lavrado; exige cobertura morta",
        exige_calagem_pesada=False,
        fixacao_biologica_n=False,
        regra_consorcio_especial="Plantio em nível obrigatório se declividade > 5%. Na colheita, entrar obrigatoriamente com gramínea para reestruturar o solo."
    )
}
