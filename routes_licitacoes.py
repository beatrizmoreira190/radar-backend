from fastapi import APIRouter, Query
from typing import Optional, List
from datetime import date, timedelta
import requests

router = APIRouter()

@router.get("/licitacoes/coletar")
def coletar_licitacoes(
    data_inicial: Optional[str] = Query(
        None, description="Data inicial AAAAMMDD (padrão: últimos 30 dias)"
    ),
    data_final: Optional[str] = Query(
        None, description="Data final AAAAMMDD (padrão: hoje)"
    ),
    codigo_modalidade: List[int] = Query(
        [6],
        description="Modalidades de contratação (ex: 1, 2, 3, 6)."
    ),
    pagina_inicial: int = Query(
        1, ge=1, description="Página inicial"
    ),
    limite_paginas: int = Query(
        5, ge=1, le=10, description="Número máximo de páginas a coletar"
    ),
    tamanho_pagina: int = Query(
        200, ge=1, le=500, description="Tamanho de página"
    )
):
    """
    MVP REALISTA com suporte a múltiplas modalidades.
    """
    # Default: últimos 30 dias
    if not data_inicial or not data_final:
        hoje = date.today()
        data_final = hoje.strftime("%Y%m%d")
        data_inicial = (hoje - timedelta(days=30)).strftime("%Y%m%d")

    url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
    todas_licitacoes = []
    pagina = pagina_inicial

    while pagina < pagina_inicial + limite_paginas:

        # A API do PNCP **não aceita lista direta**
        # então fazemos 1 requisição por modalidade
        for modalidade in codigo_modalidade:
            params = {
                "dataInicial": data_inicial,
                "dataFinal": data_final,
                "codigoModalidadeContratacao": modalidade,  # nunca vazio
                "pagina": pagina,
                "tamanhoPagina": tamanho_pagina,
            }

            try:
                r = requests.get(url, params=params, timeout=30)
                r.raise_for_status()
                data = r.json()

                registros = data.get("data", [])
                if not registros:
                    continue  # tenta outras modalidades ou encerra

                todas_licitacoes.extend(registros)

            except Exception as e:
                return {
                    "erro": str(e),
                    "parametros": params,
                    "dados_parciais": todas_licitacoes
                }

        pagina += 1

    # Tratamento básico de duplicação (caso várias mods tragam o mesmo registro)
    # idCompra existe praticamente em todas
    unique = {item.get("idCompra"): item for item in todas_licitacoes if item.get("idCompra")}

    return {
        "parametros_enviados": {
            "dataInicial": data_inicial,
            "dataFinal": data_final,
            "codigo_modalidade": codigo_modalidade,
            "pagina_inicial": pagina_inicial,
            "limite_paginas": limite_paginas,
            "tamanhoPagina": tamanho_pagina,
        },
        "quantidade_registros": len(unique),
        "dados": list(unique.values())
    }
