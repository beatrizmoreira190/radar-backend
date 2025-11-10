from fastapi import APIRouter, Query
import requests
from datetime import datetime

router = APIRouter()

@router.get("/licitacoes/buscar")
def buscar_licitacoes(termo: str = Query("livro", description="Palavra-chave da licitação")):
    """
    Busca licitações reais na API pública do PNCP com base no termo informado
    e retorna apenas os campos mais relevantes.
    """
    url = "https://pncp.gov.br/api/search"
    params = {"termo": termo, "pagina": 1}

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Estrutura esperada da API PNCP: data["hits"] contém as licitações
        licitacoes_brutas = data.get("hits", [])
        resultados = []

        for item in licitacoes_brutas:
            # Cada licitação tem um dicionário interno com dados básicos
            fonte = item.get("fonte", "Desconhecida")
            orgao = item.get("orgao", "Não informado")
            objeto = item.get("objeto", "Sem descrição")
            data_abertura = item.get("data_abertura", None)
            valor = item.get("valor_estimado", "Não informado")

            if data_abertura:
                try:
                    data_abertura = datetime.fromisoformat(data_abertura).strftime("%d/%m/%Y")
                except Exception:
                    pass

            resultados.append({
                "fonte": fonte,
                "orgao": orgao,
                "objeto": objeto,
                "data_abertura": data_abertura,
                "valor_estimado": valor
            })

        return {
            "termo_pesquisado": termo,
            "quantidade_encontrada": len(resultados),
            "licitacoes": resultados
        }

    except Exception as e:
        return {"erro": f"Falha ao buscar licitações: {str(e)}"}
