from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from routes import router as api_router
from routes_editoras import router as editoras_router
from routes_licitacoes import router as licitacoes_router

# Criar todas as tabelas automaticamente (se ainda não existirem)
Base.metadata.create_all(bind=engine)

# Instancia da aplicação FastAPI
app = FastAPI(title="Radar Inteligente - MVP")

# =======================================================
# 🌐 CORS - PERMISSÕES PARA O FRONTEND (Netlify)
# =======================================================

origins = [
    "https://radarinteligente.netlify.app",  # produção
    "http://localhost:5173",                 # desenvolvimento local (Vite/React)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,            # domínios permitidos
    allow_credentials=True,
    allow_methods=["*"],              # libera GET, POST, DELETE, PATCH, etc.
    allow_headers=["*"],              # permite todos os headers
)

# =======================================================
# Rotas
# =======================================================

app.include_router(api_router)
app.include_router(editoras_router)
app.include_router(licitacoes_router)

# =======================================================
# Rota raiz (teste)
# =======================================================

@app.get("/")
def root():
    return {"message": "Radar Inteligente API Online"}
