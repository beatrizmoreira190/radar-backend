from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, Text, Numeric
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

    livros = relationship("Livro", back_populates="editora", cascade="all, delete-orphan")
    interesses = relationship("LicitacaoInteresse", back_populates="editora", cascade="all, delete-orphan")
    notificacoes = relationship("Notificacao", back_populates="editora", cascade="all, delete-orphan")


class Livro(Base):
    __tablename__ = "livros"
    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String, nullable=False)
    autor = Column(String)
    isbn = Column(String)
    faixa_etaria = Column(String)
    tema = Column(String)
    descricao = Column(Text)
    editora_id = Column(Integer, ForeignKey("editoras.id"))

    editora = relationship("Editora", back_populates="livros")
    notificacoes = relationship("Notificacao", back_populates="livro", cascade="all, delete-orphan")


class Orgao(Base):
    __tablename__ = "orgaos"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(Text, nullable=False)
    esfera = Column(String(50), nullable=True)  # municipal, estadual, federal
    uf = Column(String(2), nullable=True)
    municipio = Column(String(255), nullable=True)

    licitacoes = relationship("Licitacao", back_populates="orgao")


class Licitacao(Base):
    __tablename__ = "licitacoes"
    id = Column(Integer, primary_key=True, index=True)
    # numeroControlePNCP – ID estável da contratação no PNCP
    id_externo = Column(String(255), unique=True, index=True)
    numero = Column(String(255), nullable=True)  # numeroCompra
    objeto = Column(Text, nullable=True)
    modalidade = Column(String(255), nullable=True)  # vamos guardar como string (ex: "6")
    orgao_id = Column(Integer, ForeignKey("orgaos.id"), nullable=True)
    uf = Column(String(2), nullable=True)
    municipio = Column(String(255), nullable=True)
    # datas ficam como texto para não depender do formato exato de retorno
    data_publicacao = Column(String, nullable=True)
    data_abertura = Column(String, nullable=True)
    url_externa = Column(Text, nullable=True)
    json_raw = Column(JSON, nullable=True)
    criado_em = Column(DateTime, default=datetime.utcnow)

    orgao = relationship("Orgao", back_populates="licitacoes")
    itens = relationship("LicitacaoItem", back_populates="licitacao", cascade="all, delete-orphan")
    anexos = relationship("LicitacaoAnexo", back_populates="licitacao", cascade="all, delete-orphan")
    interesses = relationship("LicitacaoInteresse", back_populates="licitacao", cascade="all, delete-orphan")
    notificacoes = relationship("Notificacao", back_populates="licitacao", cascade="all, delete-orphan")


class LicitacaoItem(Base):
    __tablename__ = "licitacao_itens"
    id = Column(Integer, primary_key=True, index=True)
    licitacao_id = Column(Integer, ForeignKey("licitacoes.id", ondelete="CASCADE"))
    numero_item = Column(Integer, nullable=True)
    descricao = Column(Text, nullable=True)
    unidade = Column(String(50), nullable=True)
    quantidade = Column(Numeric, nullable=True)
    valor_estimado = Column(Numeric, nullable=True)
    json_raw = Column(JSON, nullable=True)

    licitacao = relationship("Licitacao", back_populates="itens")


class LicitacaoAnexo(Base):
    __tablename__ = "licitacao_anexos"
    id = Column(Integer, primary_key=True, index=True)
    licitacao_id = Column(Integer, ForeignKey("licitacoes.id", ondelete="CASCADE"))
    nome_arquivo = Column(Text, nullable=True)
    url = Column(Text, nullable=True)
    tipo = Column(String(50), nullable=True)
    json_raw = Column(JSON, nullable=True)

    licitacao = relationship("Licitacao", back_populates="anexos")


class LicitacaoInteresse(Base):
    __tablename__ = "licitacoes_interesse"
    id = Column(Integer, primary_key=True, index=True)
    editora_id = Column(Integer, ForeignKey("editoras.id"))
    licitacao_id = Column(Integer, ForeignKey("licitacoes.id"))
    # interessado, proposta_enviada, aguardando_resultado, encerrado
    status = Column(String(50), default="interessado")
    criado_em = Column(DateTime, default=datetime.utcnow)

    editora = relationship("Editora", back_populates="interesses")
    licitacao = relationship("Licitacao", back_populates="interesses")
    tarefas = relationship("AcompanhamentoTarefa", back_populates="acompanhamento", cascade="all, delete-orphan")


class AcompanhamentoTarefa(Base):
    __tablename__ = "acompanhamento_tarefas"
    id = Column(Integer, primary_key=True, index=True)
    acompanhamento_id = Column(Integer, ForeignKey("licitacoes_interesse.id", ondelete="CASCADE"))
    titulo = Column(Text, nullable=False)
    descricao = Column(Text, nullable=True)
    concluido = Column(Boolean, default=False)
    criado_em = Column(DateTime, default=datetime.utcnow)

    acompanhamento = relationship("LicitacaoInteresse", back_populates="tarefas")


class Notificacao(Base):
    __tablename__ = "notificacoes"
    id = Column(Integer, primary_key=True, index=True)
    editora_id = Column(Integer, ForeignKey("editoras.id"))
    licitacao_id = Column(Integer, ForeignKey("licitacoes.id"), nullable=True)
    livro_id = Column(Integer, ForeignKey("livros.id"), nullable=True)
    mensagem = Column(Text, nullable=False)
    lida = Column(Boolean, default=False)
    criado_em = Column(DateTime, default=datetime.utcnow)

    editora = relationship("Editora", back_populates="notificacoes")
    licitacao = relationship("Licitacao", back_populates="notificacoes")
    livro = relationship("Livro", back_populates="notificacoes")


class ColetaHistorico(Base):
    __tablename__ = "coletas_historico"
    id = Column(Integer, primary_key=True, index=True)
    fonte = Column(String(255), nullable=False)
    url = Column(Text, nullable=False)
    quantidade = Column(Integer, nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow)
