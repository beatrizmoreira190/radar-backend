from fastapi import APIRouter, Query, Depends, HTTPException
import requests
import json
import os
import time
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from database import get_db
from models import Licitacao, Orgao, ColetaHistorico

router = APIRouter()

# Caminho do arquivo de cache local
CACHE_FILE = "licitacoes_cache.json"


# =======================================================
# 1) COLETAR 1 PÁGINA BRUTA DO PNCP (SEM SALVAR)
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
    Coleta bruta de 1 página de licitações publicadas no PNCP (sem salvar no banco).
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
            "quantidade_registros": len(data.get("data", []) or []),
            "dados": data.get("data", []) or []
        }

    except Exception as e:
        return {
            "erro": f"Falha ao consultar PNCP: {str(e)}",
            "endpoint": url,
            "parametros": params
        }


# =======================================================
# 2) SALVAR CACHE LOCAL EM ARQUIVO JSON
# =======================================================
@router.get("/licitacoes/salvar")
def salvar_cache(
    paginas: int = Query(20, ge=1, le=50, description="Quantas páginas buscar no PNCP"),
    tamanho_pagina: int = Query(50, ge=1, le=500)
):
    """
    Coleta VÁRIAS páginas do PNCP e salva um arquivo local com TODAS as licitações.
    Ideal pra ter 500–2000 licitações reais para testes locais.
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
            data = r.json().get("data", []) or []

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
# 3) LISTAR CACHE LOCAL
# =======================================================
@router.get("/licitacoes/listar")
def listar_cache():
    """
    Retorna o JSON salvo localmente (apenas para testes).
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
# 4) FILTRAR CACHE LOCAL
# =======================================================
@router.get("/licitacoes/filtrar")
def filtrar_cache(
    busca: str = "",
    uf: str = "",
    modalidade: str = "",
):
    """
    Filtra o JSON salvo localmente (apenas para testes).
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
# FUNÇÃO AUXILIAR: SALVAR UMA LICITAÇÃO NO BANCO
# =======================================================
def salvar_licitacao_no_banco(item: dict, db: Session) -> bool:
    """
    Converte o item do PNCP → tabela 'licitacoes'.
    Retorna True se criou novo registro, False se atualizou.
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
            orgao = Orgao(nome=orgao_nome, uf=uf, municipio=municipio)
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
            json_raw=item,
        )
        db.add(nova)
        return True

    # Atualiza existente
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
# 5) SALVAR CACHE LOCAL NO BANCO
# =======================================================
@router.post("/licitacoes/salvar_no_banco")
def salvar_cache_no_banco(db: Session = Depends(get_db)):
    """
    Lê o arquivo licitacoes_cache.json e grava todas as licitações no banco.
    Útil só em ambiente local.
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
# 6) LISTAR LICITAÇÕES DO BANCO (AGORA COM LIMITE 5000)
# =======================================================

@router.get("/licitacoes/listar_banco")
def listar_licitacoes_banco(
    id: int | None = None,
    busca: str = "",
    uf: str = "",
    modalidade: str = "",
    limite: int = 5000,
    db: Session = Depends(get_db),
):
    """
    Lista licitações já salvas no banco (versão persistente e filtrável).
    Se 'id' for informado, retorna apenas aquela licitação.
    """
    base_query = db.query(Licitacao)

    # Se for busca por ID específico, ignora os demais filtros
    if id is not None:
        lic = base_query.filter(Licitacao.id == id).first()
        if not lic:
            raise HTTPException(status_code=404, detail="Licitação não encontrada")
        dados = [lic]
        total = 1
    else:
        query = base_query

        if busca:
            query = query.filter(Licitacao.objeto.ilike(f"%{busca}%"))

        if uf:
            query = query.filter(Licitacao.uf == uf.upper())

        if modalidade:
            query = query.filter(Licitacao.modalidade.ilike(f"%{modalidade}%"))

        query = query.order_by(
            Licitacao.data_publicacao.desc(), Licitacao.id.desc()
        ).limit(limite)
        dados = query.all()
        total = len(dados)

    return {
        "total": total,
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
                "json_raw": lic.json_raw,
            }
            for lic in dados
        ],
    }


# =======================================================
# 7) COLETAR + SALVAR UMA PÁGINA NO BANCO
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
    Ideal para chamadas pontuais ou testes.
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


# =======================================================
# 8) COLETAR + SALVAR VÁRIAS PÁGINAS (MULTIPLO)
# =======================================================
@router.get("/licitacoes/coletar_e_salvar_multiplo")
def coletar_e_salvar_multiplo(
    data_inicial: str = Query(..., description="AAAAMMDD"),
    data_final: str = Query(..., description="AAAAMMDD"),
    codigo_modalidade: int = Query(6),
    paginas: int = Query(20, ge=1, le=50),
    tamanho_pagina: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    Coleta várias páginas (ex: 20) de um mesmo período e salva no banco.
    Usa a MESMA lógica do /coletar_e_salvar, mas automatizando as páginas.
    """
    total_inseridos = 0
    total_atualizados = 0
    total_paginas_coletadas = 0

    for p in range(1, paginas + 1):
        url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
        params = {
            "dataInicial": data_inicial,
            "dataFinal": data_final,
            "codigoModalidadeContratacao": codigo_modalidade,
            "pagina": p,
            "tamanhoPagina": tamanho_pagina
        }

        try:
            r = requests.get(url, params=params, timeout=180)
            r.raise_for_status()
            data = r.json()
            itens = data.get("data", []) or []

            if not itens:
                break

            for item in itens:
                criado = salvar_licitacao_no_banco(item, db)
                if criado:
                    total_inseridos += 1
                else:
                    total_atualizados += 1

            total_paginas_coletadas += 1
            time.sleep(1)  # pequena pausa entre páginas

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro ao coletar múltiplas páginas: {e}")

    db.add(ColetaHistorico(
        fonte="PNCP_MULTIPLO",
        url="interno /coletar_e_salvar_multiplo",
        quantidade=total_inseridos
    ))
    db.commit()

    return {
        "status": "OK",
        "data_inicial": data_inicial,
        "data_final": data_final,
        "paginas_processadas": total_paginas_coletadas,
        "inseridos": total_inseridos,
        "atualizados": total_atualizados
    }


# =======================================================
# 9) COLETAR PERÍODO COMPLETO (DIA POR DIA, PÁGINA POR PÁGINA)
# =======================================================
@router.get("/licitacoes/coletar_periodo_completo")
def coletar_periodo_completo(
    data_inicial: str = Query(..., description="AAAAMMDD"),
    data_final: str = Query(..., description="AAAAMMDD"),
    codigo_modalidade: int = Query(6),
    paginas_por_dia: int = Query(20, ge=1, le=50),
    tamanho_pagina: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    Coleta automaticamente um período inteiro (ex: outubro+novembro),
    dia por dia, página por página, e salva tudo no banco.
    """
    try:
        di = datetime.strptime(data_inicial, "%Y%m%d")
        df = datetime.strptime(data_final, "%Y%m%d")
    except ValueError:
        raise HTTPException(400, "Datas devem estar no formato AAAAMMDD.")

    dia_atual = di
    total_dias = 0
    total_paginas = 0
    total_inseridos = 0
    total_atualizados = 0

    while dia_atual <= df:
        data_str = dia_atual.strftime("%Y%m%d")

        for p in range(1, paginas_por_dia + 1):
            url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
            params = {
                "dataInicial": data_str,
                "dataFinal": data_str,
                "codigoModalidadeContratacao": codigo_modalidade,
                "pagina": p,
                "tamanhoPagina": tamanho_pagina
            }

            try:
                r = requests.get(url, params=params, timeout=180)
                r.raise_for_status()
                data = r.json()
                itens = data.get("data", []) or []

                if not itens:
                    break

                for item in itens:
                    criado = salvar_licitacao_no_banco(item, db)
                    if criado:
                        total_inseridos += 1
                    else:
                        total_atualizados += 1

                total_paginas += 1
                time.sleep(1)

            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Erro no dia {data_str}, página {p}: {e}")

        total_dias += 1
        dia_atual += timedelta(days=1)

    db.add(ColetaHistorico(
        fonte="PNCP_PERIODO_COMPLETO",
        url="interno /coletar_periodo_completo",
        quantidade=total_inseridos
    ))
    db.commit()

    return {
        "status": "OK",
        "periodo": f"{data_inicial} → {data_final}",
        "dias_processados": total_dias,
        "paginas_processadas": total_paginas,
        "inseridos": total_inseridos,
        "atualizados": total_atualizados
    }
# =======================================================
# 10) INTERESSES (FAVORITOS DE LICITAÇÕES)
# =======================================================

from models import LicitacaoInteresse  # já existe no seu models

# ADD FAVORITO
@router.post("/interesses/adicionar")
def adicionar_interesse(
    licitacao_id: int,
    db: Session = Depends(get_db)
):
    EDITORA_FIXA = 1  # ← até ter login real

    # já existe?
    existente = db.query(LicitacaoInteresse).filter(
        LicitacaoInteresse.editora_id == EDITORA_FIXA,
        LicitacaoInteresse.licitacao_id == licitacao_id
    ).first()

    if existente:
        return {"status": "ja_existe", "mensagem": "Licitação já está salva."}

    novo = LicitacaoInteresse(
        editora_id=EDITORA_FIXA,
        licitacao_id=licitacao_id,
        status="interessado"
    )
    db.add(novo)
    db.commit()

    return {"status": "ok", "mensagem": "Licitação adicionada aos interesses."}


# REMOVER FAVORITO
@router.delete("/interesses/remover/{licitacao_id}")
def remover_interesse(
    licitacao_id: int,
    db: Session = Depends(get_db)
):
    EDITORA_FIXA = 1

    interesse = db.query(LicitacaoInteresse).filter(
        LicitacaoInteresse.editora_id == EDITORA_FIXA,
        LicitacaoInteresse.licitacao_id == licitacao_id
    ).first()

    if not interesse:
        raise HTTPException(404, "Interesse não encontrado")

    db.delete(interesse)
    db.commit()

    return {"status": "ok", "mensagem": "Licitação removida dos interesses."}


# VERIFICAR SE ESTÁ NOS FAVORITOS
@router.get("/interesses/verificar")
def verificar_interesse(
    licitacao_id: int,
    db: Session = Depends(get_db)
):
    EDITORA_FIXA = 1

    interesse = db.query(LicitacaoInteresse).filter(
        LicitacaoInteresse.editora_id == EDITORA_FIXA,
        LicitacaoInteresse.licitacao_id == licitacao_id
    ).first()

    return {"salvo": bool(interesse)}


# LISTAR TODOS OS FAVORITOS
@router.get("/interesses/listar")
def listar_interesses(
    db: Session = Depends(get_db)
):
    EDITORA_FIXA = 1

    interesses = (
        db.query(LicitacaoInteresse)
        .filter(LicitacaoInteresse.editora_id == EDITORA_FIXA)
        .all()
    )

    lista = []
    for inter in interesses:
        lic = inter.licitacao
        if lic:
            lista.append({
                "id": lic.id,
                "orgao": lic.orgao.nome if lic.orgao else None,
                "objeto": lic.objeto,
                "municipio": lic.municipio,
                "uf": lic.uf,
                "data_publicacao": lic.data_publicacao,
                "status": inter.status,
            })

    return {"total": len(lista), "dados": lista}


# =======================================================
# 11) ACOMPANHAMENTO DE LICITAÇÕES.
# =======================================================

@router.post("/acompanhamento/iniciar")
def iniciar_acompanhamento(
    licitacao_id: int,
    db: Session = Depends(get_db)
):
    EDITORA_FIXA = 1

    # verificar se já existe
    existente = db.query(LicitacaoInteresse).filter(
        LicitacaoInteresse.editora_id == EDITORA_FIXA,
        LicitacaoInteresse.licitacao_id == licitacao_id
    ).first()

    if existente:
        return {
            "status": "ja_existe",
            "mensagem": "Acompanhamento já iniciado.",
            "acompanhamento_id": existente.id
        }

    novo = LicitacaoInteresse(
        editora_id=EDITORA_FIXA,
        licitacao_id=licitacao_id,
        status="interessado"
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)

    return {
        "status": "ok",
        "mensagem": "Acompanhamento iniciado!",
        "acompanhamento_id": novo.id
    }

@router.patch("/acompanhamento/status")
def atualizar_status(
    licitacao_id: int,
    status: str,
    db: Session = Depends(get_db)
):
    EDITORA_FIXA = 1

    acomp = db.query(LicitacaoInteresse).filter(
        LicitacaoInteresse.editora_id == EDITORA_FIXA,
        LicitacaoInteresse.licitacao_id == licitacao_id
    ).first()

    if not acomp:
        raise HTTPException(404, "Acompanhamento não encontrado.")

    acomp.status = status
    db.commit()

    return {"status": "ok", "mensagem": "Status atualizado."}


@router.post("/acompanhamento/tarefas/adicionar")
def adicionar_tarefa(
    licitacao_id: int,
    titulo: str,
    descricao: str = "",
    db: Session = Depends(get_db)
):
    EDITORA_FIXA = 1

    acomp = db.query(LicitacaoInteresse).filter(
        LicitacaoInteresse.editora_id == EDITORA_FIXA,
        LicitacaoInteresse.licitacao_id == licitacao_id
    ).first()

    if not acomp:
        raise HTTPException(404, "Acompanhamento não encontrado.")

    tarefa = AcompanhamentoTarefa(
        acompanhamento_id=acomp.id,
        titulo=titulo,
        descricao=descricao
    )

    db.add(tarefa)
    db.commit()
    db.refresh(tarefa)

    return {"status": "ok", "tarefa": {
        "id": tarefa.id,
        "titulo": tarefa.titulo,
        "descricao": tarefa.descricao,
        "concluido": tarefa.concluido
    }}


@router.patch("/acompanhamento/tarefas/concluir/{tarefa_id}")
def concluir_tarefa(
    tarefa_id: int,
    db: Session = Depends(get_db)
):
    tarefa = db.query(AcompanhamentoTarefa).filter(
        AcompanhamentoTarefa.id == tarefa_id
    ).first()

    if not tarefa:
        raise HTTPException(404, "Tarefa não encontrada.")

    tarefa.concluido = True
    db.commit()

    return {"status": "ok", "mensagem": "Tarefa concluída."}


@router.delete("/acompanhamento/tarefas/remover/{tarefa_id}")
def remover_tarefa(
    tarefa_id: int,
    db: Session = Depends(get_db)
):
    tarefa = db.query(AcompanhamentoTarefa).filter(
        AcompanhamentoTarefa.id == tarefa_id
    ).first()

    if not tarefa:
        raise HTTPException(404, "Tarefa não encontrada.")

    db.delete(tarefa)
    db.commit()

    return {"status": "ok", "mensagem": "Tarefa removida."}


@router.get("/acompanhamento/tarefas")
def listar_tarefas(
    licitacao_id: int,
    db: Session = Depends(get_db)
):
    EDITORA_FIXA = 1

    acomp = db.query(LicitacaoInteresse).filter(
        LicitacaoInteresse.editora_id == EDITORA_FIXA,
        LicitacaoInteresse.licitacao_id == licitacao_id
    ).first()

    if not acomp:
        raise HTTPException(404, "Acompanhamento não encontrado.")

    lista = []
    for t in acomp.tarefas:
        lista.append({
            "id": t.id,
            "titulo": t.titulo,
            "descricao": t.descricao,
            "concluido": t.concluido
        })

    return {"total": len(lista), "tarefas": lista}
