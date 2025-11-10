from fastapi import APIRouter, Query
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

router = APIRouter()

# ----------------- CONFIGURAÇÃO GERAL -----------------

PNCP_BASES = [
    "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao",   # API institucional
    "https://pncp.gov.br/api/consulta/v3/licitacoes",                # API pública usada pelo site
    "https://pncp.gov.br/api/consulta"                               # fallback "puro" (genérico)
]

# ----------------- FUNÇÕES AUXILIARES -----------------

def formatar_data(data_str: str) -> str:
    """Converte YYYY-MM-DD → YYYYMMDD conforme exigência do PNCP v1."""
    return data_str.replace("-", "")

def normalizar_item(item):
    """Padroniza a estrutura de uma licitação."""
    return {
        "orgao": item.get("orgaoEntidade") or item.get("orgaoNome") or "Não informado",
        "objeto": item.get("objeto") or item.get("objetoCompra") or item.get("descricaoItem") or "Sem descrição",
        "modalidade": item.get("modalidade") or item.get("modalidadeNome") or "Desconhecida",
        "situacao": item.get("situacaoCompraNome") or item.get("situacao") or "—",
        "data_publicacao": (
            item.get("dataPublicacaoPncp")
            or item.get("dataAberturaProposta")
            or item.get("dataAbertura")
        ),
        "fonte": item.get("fonte") or "PNCP"
    }

def buscar_api(url, params):
    """Tenta consultar uma API e retorna dados no formato padronizado."""
    try:
        r = requests.get(url, params=params, timeout=25)
        r.raise_for_status()
        data = r.json()
        # alguns endpoints retornam {"data": [...]}, outros uma lista direta
        return data.get("data", data)
    except Exception:
        return []

def termo_existe(item, termo):
    termo_lower = termo.lower()
    campos = [
        item.get("objeto", ""),
        item.get("objetoCompra", ""),
        item.get("descricaoItem", ""),
        item.get("descricaoLote", ""),
        item.get("descricaoGrupo", ""),
    ]
    return any(termo_lower in (c or "").lower() for c in campos)

# ----------------- ROTA PRINCIPAL -----------------

@router.get("/licitacoes/buscar")
def buscar_licitacoes(
    termo: str = Query("livros", description="Palavra-chave"),
    data_inicio: str = Query("2024-01-01", description="Data inicial (AAAA-MM-DD)"),
    data_fim: str = Query("2024-12-31", description="Data final (AAAA-MM-DD)"),
    codigo_modalidade: int = Query(6, description="Modalidade (6 = Pregão Eletrônico)"),
    codigo_modo_disputa: int = Query(1, description="Modo de disputa (1 = Aberto)"),
    pagina: int = Query(1, ge=1, description="Número da página"),
    tamanho_pagina: int = Query(50, ge=1, le=100, description="Tamanho da página")
):
    """
    Consulta híbrida PNCP:
    1️⃣ Tenta a API oficial (v1)
    2️⃣ Se vazio, tenta a pública (v3)
    3️⃣ Se ainda vazio, tenta a base pura (/api/consulta)
    Junta tudo, remove duplicados e retorna padronizado.
    """

    data_inicial_fmt = formatar_data(data_inicio)
    data_final_fmt = formatar_data(data_fim)

    params_v1 = {
        "dataInicial": data_inicial_fmt,
        "dataFinal": data_final_fmt,
        "codigoModalidadeContratacao": codigo_modalidade,
        "codigoModoDisputa": codigo_modo_disputa,
        "pagina": pagina,
        "tamanhoPagina": tamanho_pagina
    }

    params_v3 = {
        "termo": termo,
        "pagina": pagina,
        "tamanhoPagina": tamanho_pagina
    }

    resultados_brutos = []

    # Consultas paralelas para reduzir tempo
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(buscar_api, PNCP_BASES[0], params_v1),
            executor.submit(buscar_api, PNCP_BASES[1], params_v3),
            executor.submit(buscar_api, PNCP_BASES[2], params_v3),
        ]
        for future in as_completed(futures):
            resultados = future.result()
            resultados_brutos.extend(resultados)

    # Filtrar por termo em todos os campos possíveis
    filtrados = [normalizar_item(i) for i in resultados_brutos if termo_existe(i, termo)]

    # Remover duplicados (por órgão + objeto)
    vistos = set()
    unicos = []
    for r in filtrados:
        chave = (r["orgao"], r["objeto"])
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(r)

    return {
        "termo_pesquisado": termo,
        "quantidade_encontrada": len(unicos),
        "licitacoes": unicos[:100],
        "endpoints_utilizados": PNCP_BASES,
        "parametros_enviados": {"v1": params_v1, "v3": params_v3}
    }
