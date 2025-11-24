# routes_dashboard.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from database import get_db
from models import Licitacao, LicitacaoInteresse

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# ============================
# 1) RESUMO GERAL
# ============================
@router.get("/resumo")
def dashboard_resumo(db: Session = Depends(get_db)):

    total_licitacoes = db.query(Licitacao).count()

    # últimas 24h
    ontem = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    total_24h = db.query(Licitacao).filter(
        Licitacao.criado_em >= ontem
    ).count()

    # últimos 7 dias
    semana = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    total_7dias = db.query(Licitacao).filter(
        Licitacao.criado_em >= semana
    ).count()

    acompanhamentos = db.query(LicitacaoInteresse).count()

    # contagem por status
    status_agregado = {
        "interessado": 0,
        "estudando_editais": 0,
        "documentacao_pronta": 0,
        "proposta_enviada": 0,
        "aguardando_resultado": 0,
        "encerrado": 0,
    }

    status_rows = db.query(LicitacaoInteresse.status).all()

    for (status,) in status_rows:
        if status in status_agregado:
            status_agregado[status] += 1

    return {
        "total_licitacoes": total_licitacoes,
        "novas_24h": total_24h,
        "novas_7dias": total_7dias,
        "acompanhamentos": acompanhamentos,
        "status_acompanhamentos": status_agregado
    }


# ============================
# 2) LICITAÇÕES POR UF
# ============================
@router.get("/estatisticas_uf")
def estatisticas_uf(db: Session = Depends(get_db)):
    licitacoes = db.query(Licitacao).all()
    contagem = {}

    for lic in licitacoes:
        raw = lic.json_raw or {}

        # Pega UF da mesma forma que o frontend faz
        uf = (
            raw.get("unidadeOrgao", {}).get("ufSigla")
            or raw.get("orgaoEntidade", {}).get("uf")
            or lic.uf
        )

        if not uf or uf == "—":
            continue

        contagem[uf] = contagem.get(uf, 0) + 1

    lista = [{"uf": uf, "total": total} for uf, total in contagem.items()]
    lista.sort(key=lambda x: x["total"], reverse=True)

    return {"total_estados": len(lista), "dados": lista}



# ============================
# 3) ACOMPANHAMENTOS POR STATUS
# ============================
@router.get("/status_acompanhamentos")
def status_acompanhamentos(db: Session = Depends(get_db)):
    
    status_rows = db.query(LicitacaoInteresse.status).all()
    contagem = {}

    for (status,) in status_rows:
        contagem[status] = contagem.get(status, 0) + 1

    return contagem


# ============================
# 4) PRÓXIMOS PRAZOS (abertura + encerramento)
# ============================
@router.get("/proximos_prazos")
def proximos_prazos(db: Session = Depends(get_db)):

    licitacoes = db.query(Licitacao).all()
    hoje = datetime.utcnow()

    proximas = []

    for lic in licitacoes:
        # tenta data de abertura
        if lic.data_abertura:
            try:
                dt = datetime.fromisoformat(lic.data_abertura.replace("Z", ""))
                if dt > hoje:
                    proximas.append({
                        "id": lic.id,
                        "objeto": lic.objeto,
                        "data": dt,
                        "tipo": "abertura"
                    })
            except:
                pass

        # tenta encerramento
        raw = lic.json_raw or {}
        if raw.get("dataEncerramentoProposta"):
            try:
                dt2 = datetime.fromisoformat(
                    raw["dataEncerramentoProposta"].replace("Z", "")
                )
                if dt2 > hoje:
                    proximas.append({
                        "id": lic.id,
                        "objeto": lic.objeto,
                        "data": dt2,
                        "tipo": "encerramento"
                    })
            except:
                pass

    # ordena por data mais próxima
    proximas.sort(key=lambda x: x["data"])

    return {"proximos_prazos": proximas[:10]}


# ============================
# 5) OPORTUNIDADES RECENTES
# ============================
@router.get("/oportunidades_recentes")
def oportunidades_recentes(db: Session = Depends(get_db)):
    lic = (
        db.query(Licitacao)
        .order_by(Licitacao.criado_em.desc())
        .limit(10)
        .all()
    )

    return {
        "total": len(lic),
        "dados": [
            {
                "id": l.id,
                "objeto": l.objeto,
                "orgao": l.orgao.nome if l.orgao else None,
                "data_publicacao": l.data_publicacao,
                "criado_em": l.criado_em
            }
            for l in lic
        ]
    }
