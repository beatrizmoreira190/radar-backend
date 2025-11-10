from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Editora(Base):
    __tablename__ = "editoras"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    senha_hash = Column(String, nullable=False)
    tags_interesse = Column(JSON)
    data_cadastro = Column(DateTime, default=datetime.utcnow)

class Livro(Base):
    __tablename__ = "livros"
    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String, nullable=False)
    autor = Column(String)
    isbn = Column(String)
    faixa_etaria = Column(String)
    tema = Column(String)
    descricao = Column(String)
    editora_id = Column(Integer, ForeignKey("editoras.id"))
