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

    licitacoes = db.query(Licitacao).all()

    agora = datetime.utcnow()
    dia_24h = agora - timedelta(days=1)
    dia_7d = agora - timedelta(days=7)

    total_24h = 0
    total_7dias = 0

    # ===== Função auxiliar para pegar a data real de publicação =====
    def parse_data_publicacao(lic):
        raw = lic.json_raw or {}

        dt = (
            raw.get("dataPublicacaoPncp")
            or lic.data_publicacao
        )

        if not dt:
            return None

        # Normaliza ISO
        try:
            return datetime.fromisoformat(dt.replace("Z", ""))
        except:
            return None

    # ===== Conta corretamente =====
    for lic in licitacoes:
        dt = parse_data_publicacao(lic)
        if not dt:
            continue

        if dt >= dia_24h:
            total_24h += 1
        if dt >= dia_7d:
            total_7dias += 1

    total_licitacoes = len(licitacoes)

    # ===== Status dos acompanhamentos (já estava ok) =====
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
        "acompanhamentos": db.query(LicitacaoInteresse).count(),
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

    def get_data_pub(lic):
        raw = lic.json_raw or {}
        dt = raw.get("dataPublicacaoPncp") or lic.data_publicacao
        if not dt:
            return None
        try:
            return datetime.fromisoformat(dt.replace("Z", ""))
        except:
            return None

    licitacoes = db.query(Licitacao).all()

    # Cria lista [(licitação, data_publicação)]
    lista = []
    for lic in licitacoes:
        dt = get_data_pub(lic)
        if dt:
            lista.append((lic, dt))

    # Ordena pela data REAL de publicação
    lista.sort(key=lambda x: x[1], reverse=True)

    # Retorna apenas os 10 mais recentes
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
        ]
    }
