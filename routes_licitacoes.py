from fastapi import APIRouter, Query
import requests
from datetime import datetime

router = APIRouter()

@router.get("/licitacoes/buscar")
def buscar_licitacoes(
    data_inicial: str = Query("20240101", description="Data inicial no formato AAAAMMDD"),
    data_final: str = Query("20241231", description="Data final no formato AAAAMMDD"),
    codigo_modalidade: int = Query(6, description="Código da modalidade (6 = Pregão Eletrônico)"),
    pagina: int = Query(1, ge=1, description="Número da página"),
    tamanho_pagina: int = Query(50, ge=1, le=100, description="Tamanho da página (opcional)"),
    termo: str = Query("livro", description="Palavra-chave para filtrar no objeto da licitação")
):
    """
    Consulta licitações publicadas no PNCP (API oficial /api/consulta/v1/contratacoes/publicacao).
    Apenas parâmetros obrigatórios e formato de data AAAAMMDD.
    """
    base_url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
    params = {
        "dataInicial": data_inicial,
        "dataFinal": data_final,
        "codigoModalidadeContratacao": codigo_modalidade,
        "pagina": pagina,
        "tamanhoPagina": tamanho_pagina
    }

    try:
        r = requests.get(base_url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()

        resultados = []
        for item in data.get("data", []):
            objeto = item.get("objeto", "") or ""
            if termo.lower() not in objeto.lower():
                continue

            resultados.append({
                "orgao": item.get("orgaoEntidade", "Não informado"),
                "objeto": objeto.strip(),
                "modalidade": item.get("modalidadeNome", "Desconhecida"),
                "valorEstimado": item.get("valorTotalEstimado", "Não informado"),
                "dataPublicacao": item.get("dataPublicacaoPncp", ""),
                "link": item.get("linkSistemaOrigem", "")
            })

        return {
            "parametros": params,
            "termo_pesquisado": termo,
            "quantidade_encontrada": len(resultados),
            "licitacoes": resultados[:100],
            "fonte": base_url
        }

    except requests.exceptions.HTTPError as e:
        return {"erro": f"Erro HTTP PNCP: {e}", "endpoint": base_url, "parametros": params}
    except Exception as e:
        return {"erro": f"Falha ao buscar licitações: {str(e)}", "endpoint": base_url, "parametros": params}
