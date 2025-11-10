from fastapi import APIRouter, Query
import requests
from datetime import datetime

router = APIRouter()

@router.get("/licitacoes/buscar")
def buscar_licitacoes(termo: str = Query("livro", description="Palavra-chave da licitação")):
    """
    Busca licitações reais no PNCP (endpoint v1 atualizado)
    com base no termo informado e retorna campos resumidos.
    """
    url = "https://pncp.gov.br/api/pncp/v1/licitacoes"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        resultados = []
        for item in data:
            # Filtro simples: só retorna licitações cujo objeto menciona o termo
            objeto = item.get("objeto", "")
            if termo.lower() not in objeto.lower():
                continue

            orgao = item.get("orgaoNome", "Não informado")
            modalidade = item.get("modalidade", "Desconhecida")
            data_abertura = item.get("dataAbertura", None)
            if data_abertura:
                try:
                    data_abertura = datetime.fromisoformat(data_abertura).strftime("%d/%m/%Y")
                except Exception:
                    pass

            resultados.append({
                "orgao": orgao,
                "objeto": objeto,
                "modalidade": modalidade,
                "data_abertura": data_abertura
            })

        return {
            "termo_pesquisado": termo,
            "quantidade_encontrada": len(resultados),
            "licitacoes": resultados[:20]  # limita aos 20 primeiros
        }

    except Exception as e:
        return {"erro": f"Falha ao buscar licitações: {str(e)}"}
