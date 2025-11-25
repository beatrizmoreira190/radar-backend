from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Notificacao  # já existe no models

router = APIRouter(prefix="/notificacoes", tags=["Notificações"])

EDITORA_FIXA = 1  # enquanto temos login de demonstração


# ==========================
# 1) LISTAR NOTIFICAÇÕES
# ==========================
@router.get("/listar")
def listar_notificacoes(
    apenas_nao_lidas: bool = False,
    db: Session = Depends(get_db),
):
    query = (
        db.query(Notificacao)
        .filter(Notificacao.editora_id == EDITORA_FIXA)
        .order_by(Notificacao.criado_em.desc())
    )

    if apenas_nao_lidas:
        query = query.filter(Notificacao.lida.is_(False))

    notificacoes = query.all()

    dados = []
    for n in notificacoes:
        dados.append(
            {
                "id": n.id,
                "mensagem": n.mensagem,
                "lida": n.lida,
                "criado_em": n.criado_em.isoformat() if n.criado_em else None,
                "licitacao_id": n.licitacao_id,
                "livro_id": n.livro_id,
            }
        )

    return {"total": len(dados), "dados": dados}


# ==========================
# 2) CRIAR NOTIFICAÇÃO
# (uso interno / testes)
# ==========================
@router.post("/criar")
def criar_notificacao(
    mensagem: str,
    licitacao_id: int | None = None,
    livro_id: int | None = None,
    db: Session = Depends(get_db),
):
    notif = Notificacao(
        editora_id=EDITORA_FIXA,
        mensagem=mensagem,
        licitacao_id=licitacao_id,
        livro_id=livro_id,
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)

    return {
        "status": "ok",
        "id": notif.id,
        "mensagem": "Notificação criada.",
    }


# ==========================
# 3) MARCAR COMO LIDA
# ==========================
@router.patch("/marcar_lida/{notif_id}")
def marcar_lida(
    notif_id: int,
    db: Session = Depends(get_db),
):
    notif = (
        db.query(Notificacao)
        .filter(
            Notificacao.id == notif_id,
            Notificacao.editora_id == EDITORA_FIXA,
        )
        .first()
    )

    if not notif:
        raise HTTPException(status_code=404, detail="Notificação não encontrada.")

    notif.lida = True
    db.commit()

    return {"status": "ok", "mensagem": "Notificação marcada como lida."}


# ==========================
# 4) REMOVER NOTIFICAÇÃO
# ==========================
@router.delete("/remover/{notif_id}")
def remover_notificacao(
    notif_id: int,
    db: Session = Depends(get_db),
):
    notif = (
        db.query(Notificacao)
        .filter(
            Notificacao.id == notif_id,
            Notificacao.editora_id == EDITORA_FIXA,
        )
        .first()
    )

    if not notif:
        raise HTTPException(status_code=404, detail="Notificação não encontrada.")

    db.delete(notif)
    db.commit()

    return {"status": "ok", "mensagem": "Notificação removida."}
