from fastapi import APIRouter, Query
from typing import Optional, List
import requests

router = APIRouter()

BASE_URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"

@router.get("/licitacoes/coletar")
def coletar_licitacoes(
    dataInicial: str = Query(..., description="Data inicial no formato AAAAMMDD"),
    dataFinal: str = Query(..., description="Data final no formato AAAAMMDD"),
    codigoModalidadeContratacao: List[int] = Query(
        ..., description="Lista de códigos de modalidade (ex: 1, 2, 3, 6)"
    ),
    codigoModoDisputa: Optional[int] = Query(None),
    uf: Optional[str] = Query(None),
    codigoMunicipioIbge: Optional[str] = Query(None),
    cnpj: Optional[str] = Query(None),
    codigoUnidadeAdministrativa: Optional[str] = Query(None),
    idUsuario: Optional[int] = Query(None),
    pagina: int = Query(1, ge=1),
    tamanhoPagina: int = Query(50, ge=1, le=500)
):
    """
    Consulta totalmente compatível com o endpoint oficial:
    
    GET /v1/contratacoes/publicacao

    Parâmetros baseados NO SWAGGER DO PNCP:
    https://pncp.gov.br/api/consulta/swagger-ui/
    """

    todas_licitacoes = []

    # A API NÃO ACEITA LISTA DIRETA → fazemos uma requisição por modalidade
    for modalidade in codigoModalidadeContratacao:

        params = {
            "dataInicial": dataInicial,
            "dataFinal": dataFinal,
            "codigoModalidadeContratacao": modalidade,
            "pagina": pagina,
            "tamanhoPagina": tamanhoPagina
        }

        # Só enviamos parâmetros opcionais SE forem preenchidos
        if codigoModoDisputa:
            params["codigoModoDisputa"] = codigoModoDisputa

        if uf:
            params["uf"] = uf

        if codigoMunicipioIbge:
            params["codigoMunicipioIbge"] = codigoMunicipioIbge

        if cnpj:
            params["cnpj"] = cnpj

        if codigoUnidadeAdministrativa:
            params["codigoUnidadeAdministrativa"] = codigoUnidadeAdministrativa

        if idUsuario:
            params["idUsuario"] = idUsuario

        try:
            print(f"Consultando modalidade {modalidade} na página {pagina}...")
            r = requests.get(BASE_URL, params=params, timeout=30)

            # Se o PNCP retornar erro → mostramos o texto real do PNCP
            if r.status_code != 200:
                return {
                    "erro": f"Erro HTTP {r.status_code}",
                    "mensagem_pncp": r.text,
                    "parametros": params
                }

            dados = r.json().get("data", [])
            todas_licitacoes.extend(dados)

        except Exception as e:
            return {
                "erro": str(e),
                "parametros": params,
                "dados_parciais": todas_licitacoes
            }

    # Remove duplicados pelo idCompra
    unicos = {
        item.get("idCompra"): item for item in todas_licitacoes if item.get("idCompra")
    }

    return {
        "parametros_enviados": {
            "dataInicial": dataInicial,
            "dataFinal": dataFinal,
            "codigoModalidadeContratacao": codigoModalidadeContratacao,
            "codigoModoDisputa": codigoModoDisputa,
            "uf": uf,
            "codigoMunicipioIbge": codigoMunicipioIbge,
            "cnpj": cnpj,
            "codigoUnidadeAdministrativa": codigoUnidadeAdministrativa,
            "pagina": pagina,
            "tamanhoPagina": tamanhoPagina
        },
        "quantidade_registros": len(unicos),
        "dados": list(unicos.values())
    }
