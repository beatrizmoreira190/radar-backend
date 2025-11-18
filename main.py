from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routes import router as api_router
from routes_editoras import router as editoras_router
from routes_licitacoes import router as licitacoes_router  # Importa as rotas de licitações

# Cria todas as tabelas no banco automaticamente
Base.metadata.create_all(bind=engine)

# Instancia a aplicação FastAPI
app = FastAPI(title="Radar Inteligente - MVP")

# 🌐 CORS CORRETAMENTE CONFIGURADO
origins = [
    "https://radarinteligente.netlify.app",  # frontend em produção
    "http://localhost:5173",                  # ambiente local (Vite)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclui os módulos de rotas
app.include_router(api_router)
app.include_router(editoras_router)
app.include_router(licitacoes_router)

# Endpoint raiz (teste de status da API)
@app.get("/")
def root():
    return {"message": "Radar Inteligente API Online"}
