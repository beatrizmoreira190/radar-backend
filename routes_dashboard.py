# routes_dashboard.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta

from database import get_db
from models import Licitacao, LicitacaoInteresse

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# ============================
# 1) RESUMO GERAL
# ============================
@router.get("/resumo")
def dashboard_resumo(db: Session = Depends(get_db)):
    agora = datetime.utcnow()
    dia_24h = agora - timedelta(days=1)
    dia_7d = agora - timedelta(days=7)

    # Total geral: conta direto no banco (leve)
    total_licitacoes = db.query(func.count(Licitacao.id)).scalar()

    # Para não depender do tipo da coluna data_publicacao (string x datetime),
    # vamos fazer igual você fazia antes, mas NUM SUBCONJUNTO do banco, não em tudo.

    # Pegamos, por exemplo, as 10.000 licitações mais recentes.
    # Se quiser deixar mais baixo (5.000), também funciona.
    limite_amostra = 10000

    candidatos = (
        db.query(Licitacao)
        .order_by(desc(Licitacao.id))   # ou desc(Licitacao.data_publicacao) se tiver índice
        .limit(limite_amostra)
        .all()
    )

    def parse_data_publicacao(lic):
        raw = lic.json_raw or {}

        dt = raw.get("dataPublicacaoPncp") or lic.data_publicacao
        if not dt:
            return None

        # dt pode ser string ou datetime
        try:
            if isinstance(dt, str):
                return datetime.fromisoformat(dt.replace("Z", ""))
            return dt
        except Exception:
            return None

    total_24h = 0
    total_7dias = 0

    for lic in candidatos:
        dt = parse_data_publicacao(lic)
        if not dt:
            continue

        if dt >= dia_24h:
            total_24h += 1
        if dt >= dia_7d:
            total_7dias += 1

    # ===== Status dos acompanhamentos (agora por GROUP BY) =====
    status_agregado = {
        "interessado": 0,
        "estudando_editais": 0,
        "documentacao_pronta": 0,
        "proposta_enviada": 0,
        "aguardando_resultado": 0,
        "encerrado": 0,
    }

    status_rows = (
        db.query(LicitacaoInteresse.status, func.count(LicitacaoInteresse.id))
        .group_by(LicitacaoInteresse.status)
        .all()
    )

    for status, qtd in status_rows:
        if status in status_agregado:
            status_agregado[status] = qtd

    acompanhamentos_total = db.query(func.count(LicitacaoInteresse.id)).scalar()

    return {
        "total_licitacoes": total_licitacoes,
        "novas_24h": total_24h,
        "novas_7dias": total_7dias,
        "acompanhamentos": acompanhamentos_total,
        "status_acompanhamentos": status_agregado,
    }


# ============================
# 2) LICITAÇÕES POR UF
# ============================
@router.get("/estatisticas_uf")
def estatisticas_uf(db: Session = Depends(get_db)):
    # Versão leve: agrupa direto pela coluna uf no banco.
    # Obs.: isso NÃO usa o json_raw pra corrigir UF, mas para fins de estatística
    # de dashboard é mais seguro do que dar .all() em tudo.
    rows = (
        db.query(Licitacao.uf, func.count(Licitacao.id))
        .filter(Licitacao.uf != None)
        .filter(Licitacao.uf != "—")
        .group_by(Licitacao.uf)
        .all()
    )

    lista = [
        {"uf": uf, "total": total}
        for uf, total in rows
        if uf
    ]

    lista.sort(key=lambda x: x["total"], reverse=True)

    return {"total_estados": len(lista), "dados": lista}


# ============================
# 3) ACOMPANHAMENTOS POR STATUS
# ============================
@router.get("/status_acompanhamentos")
def status_acompanhamentos(db: Session = Depends(get_db)):
    # Mesmo que o anterior, mas devolvendo direto o dicionário.
    rows = (
        db.query(LicitacaoInteresse.status, func.count(LicitacaoInteresse.id))
        .group_by(LicitacaoInteresse.status)
        .all()
    )

    contagem = {status: qtd for status, qtd in rows}

    return contagem


# ============================
# 4) PRÓXIMOS PRAZOS (abertura + encerramento)
# ============================
@router.get("/proximos_prazos")
def proximos_prazos(db: Session = Depends(get_db)):
    hoje = datetime.utcnow()

    # Pra evitar dar .all() numa tabela enorme, a ideia é:
    # - pegar um conjunto razoável de licitações mais recentes (por data_publicacao),
    #   por exemplo as últimas 1000
    # - em cima desse subconjunto, aplicar a lógica de data_abertura / json_raw
    # Isso é mais que suficiente pra achar os próximos 10 prazos pro dashboard.

    candidatos = (
        db.query(Licitacao)
        .order_by(desc(Licitacao.data_publicacao))
        .limit(1000)
        .all()
    )

    proximas = []

    for lic in candidatos:
        # tenta data de abertura (ISO string)
        if lic.data_abertura:
            try:
                dt = datetime.fromisoformat(lic.data_abertura.replace("Z", ""))
                if dt > hoje:
                    proximas.append(
                        {
                            "id": lic.id,
                            "objeto": lic.objeto,
                            "data": dt,
                            "tipo": "abertura",
                        }
                    )
            except Exception:
                pass

        # tenta encerramento no json_raw
        raw = lic.json_raw or {}
        enc = raw.get("dataEncerramentoProposta")
        if enc:
            try:
                dt2 = datetime.fromisoformat(enc.replace("Z", ""))
                if dt2 > hoje:
                    proximas.append(
                        {
                            "id": lic.id,
                            "objeto": lic.objeto,
                            "data": dt2,
                            "tipo": "encerramento",
                        }
                    )
            except Exception:
                pass

    # ordena por data mais próxima e corta os 10 primeiros
    proximas.sort(key=lambda x: x["data"])

    return {
        "proximos_prazos": [
            {
                "id": item["id"],
                "objeto": item["objeto"],
                "tipo": item["tipo"],
                "data": item["data"].isoformat(),
            }
            for item in proximas[:10]
        ]
    }


# ============================
# 5) OPORTUNIDADES RECENTES
# ============================
@router.get("/oportunidades_recentes")
def oportunidades_recentes(db: Session = Depends(get_db)):
    # Mesma ideia: não vamos varrer a tabela inteira.
    # Pegamos as últimas N licitações e, dentro delas, calculamos a "data real"
    # usando json_raw + data_publicacao.

    def get_data_pub(lic):
        raw = lic.json_raw or {}
        dt = raw.get("dataPublicacaoPncp") or lic.data_publicacao
        if not dt:
            return None
        try:
            # dt pode ser string ou datetime; tratamos os dois casos
            if isinstance(dt, str):
                return datetime.fromisoformat(dt.replace("Z", ""))
            return dt
        except Exception:
            return None

    # Subconjunto: últimas 1000 por data_publicacao
    candidatos = (
        db.query(Licitacao)
        .order_by(desc(Licitacao.data_publicacao))
        .limit(1000)
        .all()
    )

    lista = []
    for lic in candidatos:
        dt = get_data_pub(lic)
        if dt:
            lista.append((lic, dt))

    # Ordena pela data real de publicação
    lista.sort(key=lambda x: x[1], reverse=True)

    # Top 10
    lista = lista[:10]

    return {
        "total": len(lista),
        "dados": [
            {
                "id": lic.id,
                "objeto": lic.objeto,
                "orgao": lic.orgao.nome if lic.orgao else None,
                "data_publicacao": dt.isoformat(),
            }
            for lic, dt in lista
        ],
    }
