"""
Perfis Agronômicos e Exigências Climáticas e de Solo:
- Milho (Zea mays)
- Feijão (Phaseolus vulgaris)
- Mandioca (Manihot esculenta)
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class CropProfile:
    name: str
    botanical_family: str
    crop_type: str                  # Gramínea, Leguminosa, Raiz/Tubérculo
    cycle_days_min: int             # Duração mínima do ciclo em dias
    cycle_days_max: int             # Duração máxima do ciclo em dias
    temp_min_ideal: float           # Temperatura mínima ideal (°C)
    temp_max_ideal: float           # Temperatura máxima ideal (°C)
    temp_base_abs_min: float        # Limite mínimo tolerado (°C)
    temp_base_abs_max: float        # Limite máximo tolerado (°C)
    water_req_min_mm: float         # Exigência mínima de chuva no ciclo (mm)
    water_req_max_mm: float         # Exigência máxima recomendada (mm)
    solar_rad_min_mj: float         # Radiação solar média mínima diária (MJ/m²/dia)
    humidity_ideal_min: float       # Umidade relativa mínima recomendada (%)
    humidity_ideal_max: float       # Umidade relativa máxima recomendada (%)
    soil_surface_min_pct: float     # Umidade superficial mínima (0 a 5 cm) para germinação/pegamento (%)
    soil_root_min_pct: float        # Umidade mínima na zona radicular (0 a 100 cm) para evitar estresse (%)
    rotation_role: str              # Papel na rotação de culturas
    benefits: List[str]             # Benefícios ecológicos e agronômicos


CROPS: Dict[str, CropProfile] = {
    "milho": CropProfile(
        name="Milho",
        botanical_family="Poaceae (Gramínea)",
        crop_type="Gramínea C4",
        cycle_days_min=110,
        cycle_days_max=150,
        temp_min_ideal=22.0,
        temp_max_ideal=30.0,
        temp_base_abs_min=10.0,
        temp_base_abs_max=36.0,
        water_req_min_mm=500.0,
        water_req_max_mm=800.0,
        solar_rad_min_mj=16.0,
        humidity_ideal_min=50.0,
        humidity_ideal_max=85.0,
        soil_surface_min_pct=45.0,    # Precisa de boa umidade superficial para emergência uniforme
        soil_root_min_pct=50.0,       # Raízes profundas exigem pelo menos 50% de umidade no pendoamento
        rotation_role="Produção abundante de biomassa e palhada duradoura para plantio direto.",
        benefits=[
            "Alta produção de palhada que protege o solo contra erosão e evaporação.",
            "Sistema radicular profundo que recicla nutrientes lixiviados.",
            "Quebra o ciclo de pragas e doenças de leguminosas (ex: fungos de solo do feijão)."
        ]
    ),
    "feijao": CropProfile(
        name="Feijão Comum",
        botanical_family="Fabaceae (Leguminosa)",
        crop_type="Leguminosa C3",
        cycle_days_min=65,
        cycle_days_max=90,
        temp_min_ideal=18.0,
        temp_max_ideal=25.0,
        temp_base_abs_min=12.0,
        temp_base_abs_max=32.0,
        water_req_min_mm=300.0,
        water_req_max_mm=450.0,
        solar_rad_min_mj=14.0,
        humidity_ideal_min=50.0,
        humidity_ideal_max=80.0,
        soil_surface_min_pct=40.0,
        soil_root_min_pct=45.0,       # Raízes rasas: se a zona radicular secar abaixo de 40-45%, aborta flores
        rotation_role="Fixação Biológica de Nitrogênio (FBN) e ciclo rápido para safrinhas ou entre-safras.",
        benefits=[
            "Fixa nitrogênio atmosférico no solo via simbiose com bactérias (Rhizobium).",
            "Ciclo curto ideal para rotação rápida sem ocupar longas janelas climáticas.",
            "Melhora a biologia do solo e deixa nutrientes residuais para a cultura sucessora."
        ]
    ),
    "mandioca": CropProfile(
        name="Mandioca",
        botanical_family="Euphorbiaceae (Euforbiácea)",
        crop_type="Raiz tuberosa C3",
        cycle_days_min=240,            # ~8 a 18 meses
        cycle_days_max=450,
        temp_min_ideal=20.0,
        temp_max_ideal=30.0,
        temp_base_abs_min=15.0,
        temp_base_abs_max=38.0,
        water_req_min_mm=600.0,
        water_req_max_mm=1200.0,
        solar_rad_min_mj=15.0,
        humidity_ideal_min=45.0,
        humidity_ideal_max=85.0,
        soil_surface_min_pct=35.0,    # Precisa de umidade inicial para brotação da maniva
        soil_root_min_pct=30.0,       # Extremamente tolerante: suporta até 30% sem colapso
        rotation_role="Exploração profunda de raízes e excelente tolerância à seca após o pegamento.",
        benefits=[
            "Alta rusticidade e resiliência a estiagens após os primeiros 90 dias.",
            "Explora horizontes mais profundos do solo acumulando amido.",
            "Sua colheita revolve o solo, sendo ideal sucedê-la com milho (para recuperar palhada) ou feijão (para repor nitrogênio)."
        ]
    )
}
