from fastapi import APIRouter, Query
import requests

router = APIRouter()

@router.get("/licitacoes/coletar")
def coletar_licitacoes(
    data_inicial: str = Query("20240101"),
    data_final: str = Query("20241231"),
    pagina: int = Query(1, ge=1),
    tamanho_pagina: int = Query(200, ge=1, le=500),
    codigo_modalidade: int = Query(6, description="Código da modalidade (6 = Pregão Eletrônico)")
):
    """
    Coleta estável do PNCP, mantendo o filtro que a API exige.
    """
    url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
    params = {
        "dataInicial": data_inicial,
        "dataFinal": data_final,
        "codigoModalidadeContratacao": codigo_modalidade,
        "pagina": pagina,
        "tamanhoPagina": tamanho_pagina,
    }

    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()

        return {
            "parametros_enviados": params,
            "quantidade_registros": len(data.get("data", [])),
            "dados": data.get("data", []),
        }

    except Exception as e:
        return {
            "erro": str(e),
            "endpoint": url,
            "parametros": params,
            "dados": []
        }
