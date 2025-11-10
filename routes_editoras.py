from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Editora, Livro
from pydantic import BaseModel

router = APIRouter()

# Schemas (validação de entrada)
class EditoraSchema(BaseModel):
    nome: str
    email: str
    senha_hash: str
    tags_interesse: list

class LivroSchema(BaseModel):
    titulo: str
    autor: str
    isbn: str
    faixa_etaria: str
    tema: str
    descricao: str
    editora_id: int

# --- ROTAS DE EDITORA ---
@router.post("/editoras")
def create_editora(editora: EditoraSchema, db: Session = Depends(get_db)):
    nova = Editora(**editora.dict())
    db.add(nova)
    db.commit()
    db.refresh(nova)
    return {"message": f"Editora '{nova.nome}' cadastrada com sucesso."}

@router.get("/editoras")
def listar_editoras(db: Session = Depends(get_db)):
    editoras = db.query(Editora).all()
    return editoras

# --- ROTAS DE LIVRO ---
@router.post("/livros")
def create_livro(livro: LivroSchema, db: Session = Depends(get_db)):
    novo = Livro(**livro.dict())
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return {"message": f"Livro '{novo.titulo}' cadastrado com sucesso."}

@router.get("/livros/{editora_id}")
def listar_livros(editora_id: int, db: Session = Depends(get_db)):
    livros = db.query(Livro).filter(Livro.editora_id == editora_id).all()
    return livros
