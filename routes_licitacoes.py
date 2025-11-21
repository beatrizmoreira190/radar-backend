from fastapi import APIRouter, Query
from typing import Optional, List
import requests

router = APIRouter()

@router.get("/licitacoes/coletar")
def coletar_licitacoes(
    data_inicial: str = Query("20240101"),
    data_final: str = Query("20241231"),
    codigo_modalidade: List[int] = Query([6]),
    pagina: int = Query(1, ge=1),
    tamanho_pagina: int = Query(50, ge=1, le=500)
):
    url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"

    todas = []

    # A API NÃO aceita lista → fazemos 1 requisição por modalidade
    for cod in codigo_modalidade:

        params = {
            "dataInicial": data_inicial,
            "dataFinal": data_final,
            "codigoModalidadeContratacao": cod,  # sempre int
            "pagina": pagina,
            "tamanhoPagina": tamanho_pagina
        }

        try:
            r = requests.get(url, params=params, timeout=30)

            if r.status_code != 200:
                # Mostra a mensagem REAL da API
                return {
                    "erro": f"Erro HTTP {r.status_code}",
                    "mensagem_pncp": r.text,
                    "parametros": params
                }

            dados = r.json().get("data", [])
            todas.extend(dados)

        except Exception as e:
            return {
                "erro": str(e),
                "parametros": params,
                "dados_parciais": todas
            }

    # remove duplicados
    unicos = {
        item.get("idCompra"): item
        for item in todas if item.get("idCompra")
    }

    return {
        "parametros_enviados": {
            "dataInicial": data_inicial,
            "dataFinal": data_final,
            "codigo_modalidade": codigo_modalidade,
            "pagina": pagina,
            "tamanhoPagina": tamanho_pagina
        },
        "quantidade_registros": len(unicos),
        "dados": list(unicos.values())
    }
