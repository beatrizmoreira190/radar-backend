from fastapi import APIRouter, Query
import requests
import json
import os

router = APIRouter()

# Caminho do arquivo de cache local
CACHE_FILE = "licitacoes_cache.json"

# -------------------------------------------
# 1) SEU ENDPOINT ORIGINAL (NÃO ALTEREI NADA)
# -------------------------------------------
@router.get("/licitacoes/coletar")
def coletar_licitacoes(
    data_inicial: str = Query("20240101", description="Data inicial no formato AAAAMMDD"),
    data_final: str = Query("20251231", description="Data final no formato AAAAMMDD"),
    codigo_modalidade: int = Query(6, description="Código da modalidade (6 = Pregão Eletrônico)"),
    pagina: int = Query(1, ge=1, description="Número da página (1 = início)"),
    tamanho_pagina: int = Query(50, ge=1, le=500, description="Tamanho da página (máx. 500)")
):
    """
    Coleta bruta de 1 página de licitações publicadas no PNCP (como no código original)
    """
    url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"

    params = {
        "dataInicial": data_inicial,
        "dataFinal": data_final,
        "codigoModalidadeContratacao": codigo_modalidade,
        "pagina": pagina,
        "tamanhoPagina": tamanho_pagina
    }

    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()

        return {
            "parametros_enviados": params,
            "quantidade_registros": len(data.get("data", [])),
            "dados": data.get("data", [])
        }

    except requests.exceptions.HTTPError as e:
        return {
            "erro": f"Erro HTTP PNCP: {e}",
            "endpoint": url,
            "parametros": params
        }

    except Exception as e:
        return {
            "erro": f"Falha geral: {str(e)}",
            "endpoint": url,
            "parametros": params
        }


# -------------------------------------------
# 2) NOVO: Coletar MUITAS páginas e SALVAR EM CACHE
# -------------------------------------------
@router.get("/licitacoes/salvar")
def salvar_cache(
    paginas: int = Query(20, ge=1, le=50, description="Quantas páginas buscar no PNCP"),
    tamanho_pagina: int = Query(50, ge=1, le=500)
):
    """
    Coleta VÁRIAS páginas do PNCP e salva um arquivo local com TODAS as licitações.
    Ideal pra ter 500–2000 licitações reais para o MVP.
    """
    url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
    todas = []

    for pagina in range(1, paginas + 1):
        params = {
            "dataInicial": "20240101",
            "dataFinal": "20251231",
            "codigoModalidadeContratacao": 6,
            "pagina": pagina,
            "tamanhoPagina": tamanho_pagina
        }

        try:
            r = requests.get(url, params=params, timeout=60)
            r.raise_for_status()
            data = r.json().get("data", [])

            if not data:
                break

            todas.extend(data)
        except Exception as e:
            return {
                "erro": str(e),
                "pagina": pagina,
                "dados_parciais": len(todas)
            }

    # Remove duplicados
    unicos = {item.get("idCompra"): item for item in todas if item.get("idCompra")}

    # Salvar JSON
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(unicos.values()), f, indent=2, ensure_ascii=False)

    return {
        "status": "OK",
        "salvo_em": CACHE_FILE,
        "quantidade": len(unicos)
    }


# -------------------------------------------
# 3) NOVO: Listar dados salvos no cache
# -------------------------------------------
@router.get("/licitacoes/listar")
def listar_cache():
    """
    Retorna o JSON salvo localmente para o frontend.
    Super rápido e sem depender do PNCP.
    """
    if not os.path.exists(CACHE_FILE):
        return {"erro": "Nenhum cache encontrado. Execute /licitacoes/salvar primeiro."}

    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        dados = json.load(f)

    return {
        "total": len(dados),
        "dados": dados
    }


# -------------------------------------------
# 4) NOVO: Filtrar o JSON salvo
# -------------------------------------------
@router.get("/licitacoes/filtrar")
def filtrar_cache(
    busca: str = "",
    uf: str = "",
    modalidade: str = "",
):
    """
    Filtra o JSON SALVO LOCALMENTE.
    """
    if not os.path.exists(CACHE_FILE):
        return {"erro": "Nenhum cache encontrado. Execute /licitacoes/salvar primeiro."}

    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        dados = json.load(f)

    resultado = []

    for item in dados:
        objeto = (item.get("objetoCompra") or item.get("descricao") or "").lower()
        orgao = item.get("orgaoEntidade", {}).get("razaoSocial", "").lower()
        uf_item = item.get("orgaoEntidade", {}).get("uf", "").lower()
        modalidade_item = str(item.get("modalidadeLicitacao") or "").lower()

        if busca and busca.lower() not in objeto:
            continue
        if uf and uf.lower() != uf_item:
            continue
        if modalidade and modalidade.lower() not in modalidade_item:
            continue

        resultado.append(item)

    return {
        "filtrados": len(resultado),
        "dados": resultado
    }
