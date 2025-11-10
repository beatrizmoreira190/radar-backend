from fastapi import APIRouter, Query
import requests
from datetime import datetime

router = APIRouter()

@router.get("/licitacoes/buscar")
def buscar_licitacoes(
    termo: str = Query("livro", description="Palavra-chave da licitação"),
    data_inicio: str = Query("2025-01-01", description="Data inicial (AAAA-MM-DD)"),
    data_fim: str = Query("2025-12-31", description="Data final (AAAA-MM-DD)")
):
    """
    Busca licitações com propostas abertas no PNCP (API Consulta v3).
    Filtra por palavra-chave no objeto da licitação.
    """
    url = "https://pncp.gov.br/api/consulta/v3/contratacoes/proposta"
    params = {
        "dataInicial": data_inicio,
        "dataFinal": data_fim,
        "pagina": 1,
        "tamanhoPagina": 50
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        resultados = []
        for item in data.get("data", []):
            objeto = item.get("objeto", "")
            if termo.lower() not in objeto.lower():
                continue

            orgao = item.get("orgaoEntidade", "Não informado")
            modalidade = item.get("modalidade", "Desconhecida")
            data_abertura = item.get("dataRecebimentoProposta", None)
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
            "licitacoes": resultados[:20]
        }

    except Exception as e:
        return {"erro": f"Falha ao buscar licitações: {str(e)}"}
