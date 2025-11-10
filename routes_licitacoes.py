from fastapi import APIRouter, Query
import requests
from datetime import datetime

router = APIRouter()

@router.get("/licitacoes/buscar")
def buscar_licitacoes(
    termo: str = Query("livros", description="Palavra-chave"),
    data_inicio: str = Query("20240101", description="Data inicial AAAAMMDD"),
    data_fim: str = Query("20241231", description="Data final AAAAMMDD"),
    codigo_modalidade: int = Query(6, description="Modalidade da contratação (6 = Pregão Eletrônico)"),
    codigo_modo_disputa: int = Query(1, description="Modo de disputa (1 = Aberto)"),
    pagina: int = Query(1, description="Número da página"),
    tamanho_pagina: int = Query(50, description="Tamanho da página (máx. 500)")
):
    """
    Busca licitações no PNCP de acordo com o Manual API Consultas v1.0.
    Usa /v1/contratacoes/publicacao conforme documentação oficial.
    """
    url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"

    params = {
        "dataInicial": data_inicio,
        "dataFinal": data_fim,
        "codigoModalidadeContratacao": codigo_modalidade,
        "codigoModoDisputa": codigo_modo_disputa,
        "pagina": pagina,
        "tamanhoPagina": tamanho_pagina
    }

    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()

        licitacoes = []
        for item in data.get("data", []):
            objeto = item.get("objetoCompra") or item.get("informacaoComplementar") or ""
            if termo.lower() not in objeto.lower():
                continue

            licitacoes.append({
                "orgao": item.get("orgaoEntidade", {}).get("razaosocial", "Não informado"),
                "modalidade": item.get("modalidadeNome", "Desconhecida"),
                "objeto": objeto.strip(),
                "valor_estimado": item.get("valorTotalEstimado", 0),
                "data_publicacao": item.get("dataPublicacaoPncp"),
                "link_origem": item.get("linkSistemaOrigem")
            })

        return {
            "termo_pesquisado": termo,
            "quantidade_encontrada": len(licitacoes),
            "licitacoes": licitacoes,
            "parametros_enviados": params
        }

    except requests.exceptions.HTTPError as e:
        return {"erro": f"Erro HTTP ao consultar PNCP: {e}", "endpoint": url, "parametros": params}
    except Exception as e:
        return {"erro": f"Falha geral: {str(e)}", "endpoint": url, "parametros": params}
