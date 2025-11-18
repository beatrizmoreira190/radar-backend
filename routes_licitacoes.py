from fastapi import APIRouter, Query
import requests

router = APIRouter()

PNCP_URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"

# MAPA COMPLETO DE MODALIDADES (PNCP)
MODALIDADES = {
    1: "Concorrência",
    2: "Tomada de Preços",
    3: "Convite",
    5: "Pregão Presencial",
    6: "Pregão Eletrônico",
    7: "Concurso",
    8: "Leilão",
    10: "Consulta",
    14: "RDC",
    98: "Outras"
}

def extrair_modalidade(item):
    cod = item.get("modalidadeLicitacao") or item.get("modalidade") or 98
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
    modalidade: str = Query("", description="Ex: Pregão Eletrônico"),
    uf: str = Query("", description="UF da licitação"),
    busca: str = Query("", description="Termo para busca no objeto"),
):
    """
    Coletor COMPLETO do PNCP — com paginação automática,
    extração correta de modalidade, UF, objeto e filtros reais.
    """

    todas_licitacoes = []
    pagina = 1

    while True:
        params = {
            "dataInicial": data_inicial,
            "dataFinal": data_final,
            "pagina": pagina,
            "tamanhoPagina": 200  # máximo permitido
        }

        try:
            r = requests.get(PNCP_URL, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            lista = data.get("data", [])

            # Se não vier nada → acabou a paginação
            if not lista:
                break

            # Processa cada item
            for item in lista:
                obj = extrair_objeto(item)
                mod = extrair_modalidade(item)
                uf_item = extrair_uf(item)

                # FILTROS OPCIONAIS
                if modalidade and modalidade.lower() != mod.lower():
                    continue
                if uf and uf.lower() != uf_item.lower():
                    continue
                if busca and busca.lower() not in obj.lower():
                    continue

                todas_licitacoes.append({
                    "orgao": item.get("orgaoEntidade", {}).get("razaoSocial"),
                    "uf": uf_item,
                    "objeto": obj,
                    "modalidade": mod,
                    "dataPublicacaoPncp": item.get("dataPublicacaoPncp"),
                    "processo": item.get("numeroProcesso", ""),
                    "id": item.get("idCompra", ""),
                    "raw": item
                })

            pagina += 1

        except Exception as e:
            # Fallback para não quebrar o frontend
            return {
                "erro": str(e),
                "pagina_atual": pagina,
                "parametros": params,
                "dados": todas_licitacoes
            }

    return {
        "total_encontrado": len(todas_licitacoes),
        "dados": todas_licitacoes
    }
