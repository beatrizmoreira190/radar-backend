from fastapi import APIRouter, Query
import requests

router = APIRouter()

# Mapa real das modalidades do PNCP
MODALIDADES = {
    1: "Concorrência",
    2: "Tomada de Preços",
    3: "Convite",
    5: "Pregão Presencial",
    6: "Pregão Eletrônico",
    7: "Concurso",
    8: "Leilão",
    14: "RDC",
    98: "Outras"
}

def extrair_modalidade(item):
    cod = (
        item.get("modalidadeLicitacao")
        or item.get("modalidade")
        or item.get("modalidadeCompra")
        or 98
    )
    return MODALIDADES.get(cod, "Outras")

def extrair_objeto(item):
    return (
        item.get("objetoCompra")
        or item.get("descricao")
        or item.get("justificativa")
        or "Descrição não informada"
    )

def extrair_uf(item):
    return (
        item.get("ufMunicipioIbge")
        or item.get("orgaoEntidade", {}).get("uf")
        or ""
    )

@router.get("/licitacoes/coletar")
def coletar_licitacoes(
    data_inicial: str = Query("20240101"),
    data_final: str = Query("20241231"),
    busca: str = Query("", description="Filtro textual no objeto"),
    uf: str = Query("", description="Ex: SP, RJ, MG"),
    modalidade: str = Query("", description="Ex: Pregão Eletrônico"),
    limite_paginas: int = Query(5, description="Máximo de páginas a coletar no MVP"),
):
    """
    MVP REALISTA — Coleta várias páginas do PNCP, normaliza dados,
    extrai informações reais e aplica filtros opcionais.
    """

    url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"

    todas = []
    pagina = 1

    while pagina <= limite_paginas:

        params = {
            "dataInicial": data_inicial,
            "dataFinal": data_final,
            "codigoModalidadeContratacao": "",  # sem filtro obrigatório
            "pagina": pagina,
            "tamanhoPagina": 200
        }

        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()

            registros = data.get("data", [])
            if not registros:
                break

            for item in registros:

                obj = extrair_objeto(item)
                mod = extrair_modalidade(item)
                uf_item = extrair_uf(item)

                # FILTROS DO MVP
                if busca and busca.lower() not in obj.lower():
                    continue

                if modalidade and modalidade.lower() != mod.lower():
                    continue

                if uf and uf.lower() != uf_item.lower():
                    continue

                todas.append({
                    "orgao": item.get("orgaoEntidade", {}).get("razaoSocial"),
                    "uf": uf_item,
                    "objeto": obj,
                    "modalidade": mod,
                    "dataPublicacao": item.get("dataPublicacaoPncp"),
                    "processo": item.get("numeroProcesso"),
                    "idCompra": item.get("idCompra"),
                    "raw": item,
                })

            pagina += 1

        except Exception as e:
            return {
                "erro": str(e),
                "pagina_erro": pagina,
                "dados_parciais": todas
            }

    return {
        "total": len(todas),
        "licitacoes": todas
    }
