from fastapi import APIRouter, Query
import requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

router = APIRouter()

# ---- Funções auxiliares ----

def formatar_data_iso8601(data_str):
    """Converte AAAA-MM-DD → AAAAMMDD"""
    return data_str.replace("-", "")

def formatar_data_br(data_iso):
    """Converte data ISO → DD/MM/AAAA"""
    try:
        return datetime.fromisoformat(data_iso).strftime("%d/%m/%Y")
    except Exception:
        return data_iso

def termo_existe(item, termo):
    """Verifica se o termo aparece em qualquer campo relevante"""
    termo_lower = termo.lower()
    campos = [
        item.get("objeto", ""),
        item.get("descricaoItem", ""),
        item.get("descricaoLote", ""),
        item.get("descricaoGrupo", "")
    ]
    return any(termo_lower in (c or "").lower() for c in campos)

def normalizar_licitacao(item):
    """Padroniza os campos de cada licitação"""
    return {
        "orgao": item.get("orgaoEntidade", item.get("orgaoNome", "Não informado")),
        "objeto": item.get("objeto", item.get("descricaoItem", "Sem descrição")).strip(),
        "modalidade": item.get("modalidade", item.get("modalidadeNome", "Desconhecida")),
        "data_publicacao": formatar_data_br(item.get("dataPublicacao") or item.get("dataAbertura") or item.get("dataRecebimentoProposta")),
        "numero_aviso": item.get("numeroAviso", item.get("numeroPNCP", "")),
        "codigoUASG": item.get("codigoUASG") or item.get("cnpj"),
        "fonte": item.get("fonte", "PNCP")
    }

def buscar_endpoint(url, params):
    """Faz requisição a um endpoint do PNCP"""
    try:
        r = requests.get(url, params=params, timeout=25)
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception:
        return []

# ---- Rota principal ----

@router.get("/licitacoes/buscar")
def buscar_licitacoes(
    termo: str = Query("livro", description="Palavra-chave a ser buscada"),
    data_inicio: str = Query("2024-01-01", description="Data inicial (AAAA-MM-DD)"),
    data_fim: str = Query("2024-12-31", description="Data final (AAAA-MM-DD)"),
    codigo_modalidade: int = Query(5, description="Código da modalidade (5 = Pregão Eletrônico)"),
    codigo_modo_disputa: int = Query(1, description="Código do modo de disputa (1 = Aberta)"),
    pagina: int = Query(1, ge=1, description="Número da página"),
    tamanho_pagina: int = Query(50, ge=1, le=100, description="Tamanho da página")
):
    """
    Busca licitações reais no PNCP em múltiplos endpoints.
    Combina resultados de /publicacao, /proposta e /atualizacao.
    Faz busca por palavra-chave em campos relevantes.
    Remove duplicados automaticamente.
    """

    # ---- Configuração geral ----
    base = "https://pncp.gov.br/api/consulta/v1/contratacoes"
    data_inicio_fmt = formatar_data_iso8601(data_inicio)
    data_fim_fmt = formatar_data_iso8601(data_fim)

    endpoints = {
        "publicacao": f"{base}/publicacao",
        "proposta": f"{base}/proposta",
        "atualizacao": f"{base}/atualizacao",
    }

    parametros_comuns = {
        "dataInicial": data_inicio_fmt,
        "dataFinal": data_fim_fmt,
        "codigoModalidadeContratacao": codigo_modalidade,
        "codigoModoDisputa": codigo_modo_disputa,
        "pagina": pagina,
        "tamanhoPagina": tamanho_pagina,
    }

    # ---- Busca em paralelo nos três endpoints ----
    resultados_brutos = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(buscar_endpoint, url, parametros_comuns): nome for nome, url in endpoints.items()}
        for future in as_completed(futures):
            resultados = future.result()
            resultados_brutos.extend(resultados)

    # ---- Filtro por termo ----
    resultados_filtrados = [normalizar_licitacao(i) for i in resultados_brutos if termo_existe(i, termo)]

    # ---- Remover duplicados (usando número de aviso ou objeto como chave) ----
    vistos = set()
    unicos = []
    for r in resultados_filtrados:
        chave = (r["numero_aviso"], r["objeto"])
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(r)

    # ---- Retorno final ----
    return {
        "termo_pesquisado": termo,
        "quantidade_encontrada": len(unicos),
        "licitacoes": unicos[:100],  # limita para evitar resposta gigante
        "parametros": parametros_comuns,
        "endpoints_utilizados": list(endpoints.values()),
    }
