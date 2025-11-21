from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Editora, Livro
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter()


# === SCHEMAS ===
class EditoraSchema(BaseModel):
    nome: str
    email: str
    senha_hash: str
    tags_interesse: List[str] = []

    class Config:
        orm_mode = True


class LivroSchema(BaseModel):
    titulo: str
    autor: Optional[str] = None
    isbn: Optional[str] = None
    faixa_etaria: Optional[str] = None
    tema: Optional[str] = None
    descricao: Optional[str] = None
    editora_id: int

    class Config:
        orm_mode = True


# --- ROTAS DE EDITORA ---
@router.post("/editoras")
def create_editora(editora: EditoraSchema, db: Session = Depends(get_db)):
    nova = Editora(**editora.dict())
    db.add(nova)
    db.commit()
    db.refresh(nova)
    return {"message": f"Editora '{nova.nome}' cadastrada com sucesso.", "id": nova.id}


# --- ROTAS DE LIVRO ---
@router.post("/livros")
def create_livro(livro: LivroSchema, db: Session = Depends(get_db)):
    novo = Livro(**livro.dict())
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return {"message": f"Livro '{novo.titulo}' cadastrado com sucesso.", "id": novo.id}


@router.get("/livros/{editora_id}")
def listar_livros(editora_id: int, db: Session = Depends(get_db)):
    livros = db.query(Livro).filter(Livro.editora_id == editora_id).all()
    return livros
