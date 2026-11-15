"""
Cliente Supabase Data API (PostgREST) em Python Puro.
Permite persistência de produtores, talhões e planos de rotação no PostgreSQL / PostGIS
sem necessidade de dependências C ou pacotes externos pesados (compatível com Cloud Run).
"""

import json
import os
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional


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

# Armazenamento em memória local como fallback caso o Supabase não esteja configurado
_LOCAL_STORAGE: Dict[str, List[Dict[str, Any]]] = {
    "produtores_planos": [],
    "propriedades": []
}


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

    with urllib.request.urlopen(req, timeout=12) as response:
        content = response.read().decode("utf-8")
        if content:
            return json.loads(content)
        return {"status": "ok", "code": response.status}


def salvar_produtor_e_plano(dados: Dict[str, Any]) -> Dict[str, Any]:
    """
    Salva ou atualiza um plano de rotação e os dados do produtor.
    Usa Supabase se configurado; caso contrário, persiste em memória local com segurança.
    """
    payload = {
        "nome_produtor": dados.get("nome") or dados.get("nome_produtor") or "Produtor Familiar",
        "telefone": dados.get("telefone", ""),
        "cod_car": dados.get("cod_car", "RR-1400175-3772D7A9BD394DA195CD145D10183419"),
        "nome_propriedade": dados.get("nome_propriedade", "Sítio Boa Esperança"),
        "talhao_id": dados.get("talhao_id", "T1"),
        "area_ha": float(dados.get("area_ha") or dados.get("area") or 6.2),
        "cultura_atual": dados.get("cultura_atual", "mandioca"),
        "objetivo": dados.get("objetivo", "saude_solo"),
        "horizonte_anos": int(dados.get("periodo_anos") or dados.get("horizonte_anos") or 3),
        "estrategia_selecionada": dados.get("estrategia_selecionada") or dados.get("estrategia") or {},
        "dados_climaticos": dados.get("dados_climaticos") or dados.get("condicoes") or {},
        "observacoes": dados.get("observacoes", "")
    }

    if is_supabase_configured():
        try:
            res = _supabase_request("produtores_planos", method="POST", data=payload)
            registro = res[0] if isinstance(res, list) and res else res
            return {
                "sucesso": True,
                "storage": "supabase",
                "id": registro.get("id"),
                "mensagem": "Plano salvo com sucesso no banco Supabase PostGIS!",
                "registro": registro
            }
        except Exception as e:
            # Fallback transparente para não travar a aplicação
            payload["id"] = "local_" + os.urandom(4).hex()
            _LOCAL_STORAGE["produtores_planos"].append(payload)
            return {
                "sucesso": True,
                "storage": "local_fallback",
                "id": payload["id"],
                "mensagem": "Plano gravado em cache local (Supabase indisponível no momento).",
                "aviso": str(e),
                "registro": payload
            }
    else:
        # Modo local / offline
        payload["id"] = "local_" + os.urandom(4).hex()
        _LOCAL_STORAGE["produtores_planos"].append(payload)
        return {
            "sucesso": True,
            "storage": "local_cache",
            "id": payload["id"],
            "mensagem": "Plano registrado em memória local (SUPABASE_URL e SUPABASE_KEY não configurados).",
            "registro": payload
        }


def salvar_propriedade(dados: Dict[str, Any]) -> Dict[str, Any]:
    """
    Registra ou atualiza os limites da propriedade e talhões.
    """
    cod_car = dados.get("cod_car", "RR-1400175-3772D7A9BD394DA195CD145D10183419")
    payload = {
        "cod_car": cod_car,
        "nome": dados.get("nome", "Sítio Boa Esperança"),
        "municipio": dados.get("municipio", "Boa Vista"),
        "uf": dados.get("uf", "RR"),
        "area_total_ha": float(dados.get("area_ha") or dados.get("area_total_ha") or 87.11),
        "area_consolidada_ha": float(dados.get("area_consolidada_ha") or 17.4),
        "talhoes": dados.get("talhoes") or {}
    }

    if is_supabase_configured():
        try:
            # Upsert via PostgREST usando Prefer: resolution=merge-duplicates
            res = _supabase_request(
                "propriedades_rurais",
                method="POST",
                data=payload,
                prefer="resolution=merge-duplicates,return=representation"
            )
            registro = res[0] if isinstance(res, list) and res else res
            return {"sucesso": True, "storage": "supabase", "registro": registro}
        except Exception as e:
            _LOCAL_STORAGE["propriedades"].append(payload)
            return {"sucesso": True, "storage": "local_fallback", "aviso": str(e), "registro": payload}
    else:
        _LOCAL_STORAGE["propriedades"].append(payload)
        return {"sucesso": True, "storage": "local_cache", "registro": payload}


def listar_planos_salvos(cod_car: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Recupera os planos de rotação salvos no Supabase ou no cache local.
    """
    if is_supabase_configured():
        try:
            endpoint = "produtores_planos?select=*&order=created_at.desc"
            if cod_car:
                endpoint += f"&cod_car=eq.{urllib.parse.quote(cod_car)}"
            res = _supabase_request(endpoint, method="GET")
            if isinstance(res, list):
                return res
            return []
        except Exception:
            pass

    # Fallback local
    itens = _LOCAL_STORAGE["produtores_planos"]
    if cod_car:
        return [i for i in itens if i.get("cod_car") == cod_car]
    return itens
