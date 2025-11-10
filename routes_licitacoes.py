from fastapi import APIRouter, Query
import requests

router = APIRouter()

@router.get("/licitacoes/coletar")
def coletar_licitacoes(
    data_inicial: str = Query("20240101", description="Data inicial no formato AAAAMMDD"),
    data_final: str = Query("20241231", description="Data final no formato AAAAMMDD"),
    codigo_modalidade: int = Query(6, description="Código da modalidade (6 = Pregão Eletrônico)"),
    pagina: int = Query(1, ge=1, description="Número da página (1 = início)"),
    tamanho_pagina: int = Query(50, ge=1, le=500, description="Tamanho da página (máx. 500)")
):
    """
    Coleta bruta de licitações publicadas no PNCP (sem filtros).
    Fonte: https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao
    """
    url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
    params = {
        "dataInicial": data_inicial,
        "dataFinal": data_final,
        "codigoModalidadeContratacao": codigo_modalidade,
        "pagina": pagina,
        "tamanhoPagina": tamanho_pagina
    }

    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()

        return {
            "parametros_enviados": params,
            "quantidade_registros": len(data.get("data", [])),
            "dados": data.get("data", [])
        }

    except requests.exceptions.HTTPError as e:
        return {"erro": f"Erro HTTP PNCP: {e}", "endpoint": url, "parametros": params}
    except Exception as e:
        return {"erro": f"Falha geral: {str(e)}", "endpoint": url, "parametros": params}
