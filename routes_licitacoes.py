from fastapi import APIRouter, Query, Depends, HTTPException
import requests
import json
import os
from sqlalchemy.orm import Session

from database import get_db
from models import Licitacao, Orgao, ColetaHistorico

router = APIRouter()

# Caminho do arquivo de cache local
CACHE_FILE = "licitacoes_cache.json"


# =======================================================
# 1) SEU ENDPOINT ORIGINAL (NÃO FOI ALTERADO)
# =======================================================
@router.get("/licitacoes/coletar")
def coletar_licitacoes(
    data_inicial: str = Query("20250101", description="Data inicial no formato AAAAMMDD"),
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
        r = requests.get(url, params=params, timeout=180)
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


# =======================================================
# 2) SEU ENDPOINT ORIGINAL: SALVAR CACHE LOCAL
# =======================================================
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
            "dataInicial": "20250101",
            "dataFinal": "20251231",
            "codigoModalidadeContratacao": 6,
            "pagina": pagina,
            "tamanhoPagina": tamanho_pagina
        }

        try:
            r = requests.get(url, params=params, timeout=180)
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

    # Remove duplicados por idCompra
    unicos = {item.get("idCompra"): item for item in todas if item.get("idCompra")}

    # Salvar JSON
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(unicos.values()), f, indent=2, ensure_ascii=False)

    return {
        "status": "OK",
        "salvo_em": CACHE_FILE,
        "quantidade": len(unicos)
    }


# =======================================================
# 3) SEU ENDPOINT ORIGINAL: LISTAR CACHE
# =======================================================
@router.get("/licitacoes/listar")
def listar_cache():
    """
    Retorna o JSON salvo localmente para o frontend.
    """
    if not os.path.exists(CACHE_FILE):
        return {"erro": "Nenhum cache encontrado. Execute /licitacoes/salvar primeiro."}

    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        dados = json.load(f)

    return {
        "total": len(dados),
        "dados": dados
    }


# =======================================================
# 4) SEU ENDPOINT ORIGINAL: FILTRAR CACHE
# =======================================================
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


# =======================================================
# ⬇⬇⬇ AQUI COMEÇA A PARTE NOVA DO BANCO ⬇⬇⬇
# =======================================================

def salvar_licitacao_no_banco(item, db: Session):
    """
    Converte o item do PNCP → tabela 'licitacoes'
    """

    id_externo = item.get("idCompra") or item.get("numeroControlePNCP")
    if not id_externo:
        return False

    # --------------------
    # ORGÃO
    # --------------------
    orgao_nome = item.get("orgaoEntidade", {}).get("razaoSocial")
    uf = item.get("orgaoEntidade", {}).get("uf")
    municipio = item.get("orgaoEntidade", {}).get("municipio")

    orgao = None
    if orgao_nome:
        orgao = db.query(Orgao).filter(
            Orgao.nome == orgao_nome,
            Orgao.uf == uf,
            Orgao.municipio == municipio
        ).first()

        if not orgao:
            orgao = Orgao(
                nome=orgao_nome,
                uf=uf,
                municipio=municipio
            )
            db.add(orgao)
            db.flush()

    # --------------------
    # LICITAÇÃO
    # --------------------
    existente = db.query(Licitacao).filter(Licitacao.id_externo == id_externo).first()

    if not existente:
        nova = Licitacao(
            id_externo=id_externo,
            numero=item.get("numeroCompra"),
            objeto=item.get("objetoCompra") or item.get("descricao"),
            modalidade=str(item.get("modalidadeLicitacao")),
            orgao_id=orgao.id if orgao else None,
            uf=uf,
            municipio=municipio,
            data_publicacao=item.get("dataPublicacaoPncp"),
            data_abertura=item.get("dataAberturaProposta"),
            url_externa=item.get("linkSistemaOrigem"),
            json_raw=item
        )
        db.add(nova)
        return True

    else:
        existente.numero = item.get("numeroCompra")
        existente.objeto = item.get("objetoCompra") or item.get("descricao")
        existente.modalidade = str(item.get("modalidadeLicitacao"))
        existente.orgao_id = orgao.id if orgao else None
        existente.uf = uf
        existente.municipio = municipio
        existente.data_publicacao = item.get("dataPublicacaoPncp")
        existente.data_abertura = item.get("dataAberturaProposta")
        existente.url_externa = item.get("linkSistemaOrigem")
        existente.json_raw = item
        return False


# =======================================================
# 5) NOVO: SALVAR DADOS DO CACHE NO BANCO
# =======================================================
@router.post("/licitacoes/salvar_no_banco")
def salvar_cache_no_banco(db: Session = Depends(get_db)):
    """
    Lê o arquivo licitacoes_cache.json e grava todas as licitações no banco.
    """
    if not os.path.exists(CACHE_FILE):
        raise HTTPException(400, "Nenhum cache encontrado. Execute /licitacoes/salvar primeiro.")

    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        dados = json.load(f)

    inseridos = 0
    atualizados = 0

    for item in dados:
        criado = salvar_licitacao_no_banco(item, db)
        if criado:
            inseridos += 1
        else:
            atualizados += 1

    historico = ColetaHistorico(
        fonte="CACHE_LOCAL",
        url="arquivo local",
        quantidade=len(dados)
    )
    db.add(historico)

    db.commit()

    return {
        "total_processados": len(dados),
        "inseridos": inseridos,
        "atualizados": atualizados
    }


# =======================================================
# 6) NOVO: LISTAR LICITAÇÕES DO BANCO
# =======================================================
@router.get("/licitacoes/listar_banco")
def listar_licitacoes_banco(
    busca: str = "",
    uf: str = "",
    modalidade: str = "",
    limite: int = 200,
    db: Session = Depends(get_db)
):
    """
    Lista licitações já salvas no banco (versão persistente e filtrável).
    """
    query = db.query(Licitacao)

    if busca:
        query = query.filter(Licitacao.objeto.ilike(f"%{busca}%"))

    if uf:
        query = query.filter(Licitacao.uf == uf.upper())

    if modalidade:
        query = query.filter(Licitacao.modalidade.ilike(f"%{modalidade}%"))

    query = query.order_by(Licitacao.id.desc()).limit(limite)
    dados = query.all()

    return {
        "total": len(dados),
        "dados": [
            {
                "id": lic.id,
                "id_externo": lic.id_externo,
                "numero": lic.numero,
                "objeto": lic.objeto,
                "modalidade": lic.modalidade,
                "orgao": lic.orgao.nome if lic.orgao else None,
                "uf": lic.uf,
                "municipio": lic.municipio,
                "data_publicacao": lic.data_publicacao,
                "data_abertura": lic.data_abertura,
                "url_externa": lic.url_externa,
            }
            for lic in dados
        ]
    }
# =======================================================
# 7) NOVO: COLETAR + SALVAR DIRETO NO BANCO
# =======================================================
@router.get("/licitacoes/coletar_e_salvar")
def coletar_e_salvar(
    data_inicial: str = Query("20250101", description="Data inicial AAAAMMDD"),
    data_final: str = Query("20251231", description="Data final AAAAMMDD"),
    codigo_modalidade: int = Query(6, description="Código modalidade PNCP"),
    pagina: int = Query(1, ge=1, description="Número da página (1)"),
    tamanho_pagina: int = Query(50, ge=1, le=500, description="Tamanho da página"),
    db: Session = Depends(get_db)
):
    """
    Coleta UMA página da API do PNCP e SALVA diretamente no banco.
    Mais leve e ideal para o Render Free.
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
        r = requests.get(url, params=params, timeout=180)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao coletar PNCP: {e}")

    itens = data.get("data", []) or []

    if not itens:
        return {
            "status": "SEM_DADOS",
            "mensagem": "A API retornou 0 registros.",
            "parametros": params
        }

    inseridos = 0
    atualizados = 0

    for item in itens:
        criado = salvar_licitacao_no_banco(item, db)
        if criado:
            inseridos += 1
        else:
            atualizados += 1

    historico = ColetaHistorico(
        fonte="PNCP_DIRETO",
        url=r.url,
        quantidade=len(itens)
    )
    db.add(historico)
    db.commit()

    return {
        "status": "OK",
        "coletados": len(itens),
        "inseridos": inseridos,
        "atualizados": atualizados,
        "parametros": params
    }
