from fastapi import APIRouter, Query
import requests
from datetime import datetime

router = APIRouter()

@router.get("/licitacoes/buscar")
def buscar_licitacoes(
    termo: str = Query("livro", description="Palavra-chave da licitação"),
    data_inicio: str = Query("2025-01-01", description="Data inicial (AAAA-MM-DD)"),
    data_fim: str = Query("2025-12-31", description="Data final (AAAA-MM-DD)"),
    codigo_modalidade: int = Query(5, description="Código da modalidade (5 = Pregão Eletrônico)"),
    pagina: int = Query(1, ge=1, description="Número da página"),
    tamanho_pagina: int = Query(50, ge=1, le=100, description="Tamanho da página")
):
    """
    Busca licitações publicadas no PNCP (API Consulta v1).
    Filtra por palavra-chave no campo 'objeto'.
    """
    url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"

    params = {
        "dataInicial": data_inicio,
        "dataFinal": data_fim,
        "codigoModalidadeContratacao": codigo_modalidade,
        "pagina": pagina,
        "tamanhoPagina": tamanho_pagina
    }

    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()

        resultados = []
        for item in data.get("data", []):
            objeto = item.get("objeto", "") or ""
            if termo.lower() not in objeto.lower():
                continue

            orgao = item.get("orgaoEntidade", "Não informado")
            modalidade = item.get("modalidade", "Desconhecida")
            data_publicacao = item.get("dataPublicacao", None)
            if data_publicacao:
                try:
                    data_publicacao = datetime.fromisoformat(data_publicacao).strftime("%d/%m/%Y")
                except Exception:
                    pass

            resultados.append({
                "orgao": orgao,
                "objeto": objeto.strip(),
                "modalidade": modalidade,
                "data_publicacao": data_publicacao
            })

        return {
            "termo_pesquisado": termo,
            "quantidade_encontrada": len(resultados),
            "licitacoes": resultados[:20],
            "fonte": url
        }

    except requests.exceptions.HTTPError as http_err:
        return {"erro": f"Erro HTTP ao consultar PNCP: {http_err}"}
    except Exception as e:
        return {"erro": f"Falha ao buscar licitações: {str(e)}"}
