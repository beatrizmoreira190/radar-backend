from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import Editora
from pydantic import BaseModel
import requests

router = APIRouter()

class EditoraSchema(BaseModel):
    nome: str
    email: str
    senha_hash: str
    tags_interesse: list

@router.post("/editoras")
def create_editora(editora: EditoraSchema, db: Session = Depends(get_db)):
    new = Editora(**editora.dict())
    db.add(new)
    db.commit()
    db.refresh(new)
    return {"message": f"Editora '{new.nome}' cadastrada com sucesso"}

@router.get("/licitacoes")
def get_licitacoes():
    url = "https://pncp.gov.br/api/search"
    params = {"termo": "livro", "pagina": 1}
    r = requests.get(url, params=params)
    return r.json()
