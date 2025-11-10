from fastapi import APIRouter, Query
import requests
from datetime import datetime

router = APIRouter()

@router.get("/licitacoes/buscar")
def buscar_licitacoes(
    termo: str = Query("livro", description="Palavra-chave da licitação"),
    orgao_id: int = Query(26295, description="ID do órgão no PNCP (26295 = FNDE)"),
    pagina: int = Query(1, ge=1, description="Número da página"),
    tamanho_pagina: int = Query(50, ge=1, le=100, description="Tamanho da página")
):
    """
    Consulta licitações reais no PNCP (nova API oficial - base https://pncp.gov.br/api/pncp).
    Prioriza o endpoint /orgaos/{id}/licitacoes, conforme manual de integração v3.
    """

    base_url = f"https://pncp.gov.br/api/pncp/v1/orgaos/{orgao_id}/licitacoes"
    params = {
        "pagina": pagina,
        "tamanhoPagina": tamanho_pagina
    }

    try:
        r = requests.get(base_url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()

        resultados = []
        for item in data:
            objeto = item.get("objeto", "")
            if termo.lower() not in objeto.lower():
                continue

            resultados.append({
                "orgao": item.get("orgaoNome", "Não informado"),
                "objeto": objeto.strip(),
                "numeroPNCP": item.get("numeroPNCP", ""),
                "valorEstimado": item.get("valorTotalEstimado", "Não informado"),
                "dataPublicacao": item.get("dataPublicacao", ""),
                "status": item.get("situacaoCompraNome", "—")
            })

        return {
            "termo_pesquisado": termo,
            "orgao_id": orgao_id,
            "quantidade_encontrada": len(resultados),
            "licitacoes": resultados[:100],
            "fonte": base_url
        }

    except requests.exceptions.HTTPError as e:
        return {"erro": f"Erro HTTP PNCP: {e}", "endpoint": base_url}
    except Exception as e:
        return {"erro": f"Falha ao buscar licitações: {str(e)}", "endpoint": base_url}
