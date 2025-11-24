from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from routes import router as api_router
from routes_editoras import router as editoras_router
from routes_licitacoes import router as licitacoes_router
from routes_dashboard import router as dashboard_router


# Instancia a aplicação FastAPI
app = FastAPI(title="Radar Inteligente - MVP")

# 🌐 CORS - deve ficar IMEDIATAMENTE após o app ser criado
origins = [
    "https://radarinteligente.netlify.app",
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Criar todas as tabelas
Base.metadata.create_all(bind=engine)

# Rotas
app.include_router(api_router)
app.include_router(editoras_router)
app.include_router(licitacoes_router)
app.include_router(dashboard_router)

@app.get("/")
def root():
    return {"message": "Radar Inteligente API Online"}
