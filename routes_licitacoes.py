from fastapi import APIRouter, Query
import requests

router = APIRouter()

@router.get("/licitacoes/buscar")
def buscar_licitacoes(termo: str = Query("livro", description="Palavra-chave da licitação")):
    """
    Busca licitações reais na API pública do PNCP com base no termo informado.
    """
    url = "https://pncp.gov.br/api/search"
    params = {"termo": termo, "pagina": 1}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        return {
            "termo_busca": termo,
            "quantidade_encontrada": len(data.get("hits", [])) if "hits" in data else 0,
            "resultados": data.get("hits", [])
        }
    except Exception as e:
        return {"erro": f"Falha ao buscar licitações: {str(e)}"}
