"""
Cliente Supabase Data API (PostgREST) em Python Puro.
Permite persistência de produtores, talhões e planos de rotação no PostgreSQL / PostGIS
sem necessidade de dependências C ou pacotes externos pesados (compatível com Cloud Run).
"""

import json
import os
import urllib.parse
import urllib.request
from uuid import uuid4
from typing import Any, Dict, Optional

from http_transport import urlopen


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

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", os.environ.get("SUPABASE_SERVICE_ROLE_KEY", os.environ.get("SUPABASE_ANON_KEY", "")))

def is_supabase_configured() -> bool:
    """Verifica se a URL e a chave de API do Supabase estão definidas."""
    return bool(SUPABASE_URL and SUPABASE_KEY and "supabase.co" in SUPABASE_URL)


def _supabase_request(
    endpoint: str,
    method: str = "GET",
    data: Optional[Dict[str, Any]] = None,
    prefer: str = "return=representation"
) -> Dict[str, Any]:
    """
    Executa uma requisição HTTP REST contra a Data API (PostgREST) do Supabase.
    """
    if not is_supabase_configured():
        raise ValueError("Supabase não configurado. Defina SUPABASE_URL e SUPABASE_KEY.")

    url = f"{SUPABASE_URL}/rest/v1/{endpoint}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": prefer
    }

    req_data = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)

    with urlopen(req, timeout=12) as response:
        content = response.read().decode("utf-8")
        if content:
            return json.loads(content)
        return {"status": "ok", "code": response.status}


def salvar_plano(dados: Dict[str, Any]) -> Dict[str, Any]:
    """Persiste somente os parâmetros agronômicos usados pela simulação."""
    cultura = dados.get("cultura_atual")
    objetivo = dados.get("objetivo")
    horizonte = dados.get("periodo_anos")
    estrategia = dados.get("estrategia_id")
    if (
        cultura not in ("mandioca", "milho", "feijao_caupi")
        or objetivo not in ("saude_solo", "renda", "clima")
        or type(horizonte) is not int or horizonte not in (2, 3, 4)
        or estrategia not in ("estrategia_0_baseline", "estrategia_1_intensificacao", "estrategia_2_resiliencia")
    ):
        raise ValueError("Gere uma simulação válida antes de salvar o plano.")

    plan_id = str(uuid4())
    _supabase_request(
        "produtores_planos", method="POST", prefer="return=minimal",
        data={
            "id": plan_id,
            "nome_produtor": "",  # Colunas obrigatórias do schema legado.
            "cod_car": "",
            "cultura_atual": cultura,
            "objetivo": objetivo,
            "horizonte_anos": horizonte,
            "estrategia_selecionada": {"id": estrategia},
        },
    )
    return {"sucesso": True, "storage": "supabase", "id": plan_id}


def buscar_propriedade_por_car(cod_car: str) -> Optional[Dict[str, Any]]:
    """
    Busca os dados e delimitação de uma propriedade rural no Supabase pelo código CAR.
    Retorna o registro com área, município, módulos fiscais e geojson em milissegundos (<30ms).
    """
    if not cod_car:
        return None

    clean_code = cod_car.strip()
    if is_supabase_configured():
        try:
            endpoint = f"propriedades_rurais?cod_car=eq.{urllib.parse.quote(clean_code)}&limit=1"
            res = _supabase_request(endpoint, method="GET")
            if isinstance(res, list) and len(res) > 0:
                return res[0]
        except Exception:
            pass

    return None
