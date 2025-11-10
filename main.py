from fastapi import FastAPI
from database import engine, Base
from routes import router as api_router
from routes_editoras import router as editoras_router  # Importa as novas rotas

# Cria todas as tabelas no banco automaticamente
Base.metadata.create_all(bind=engine)

# Instancia a aplicação FastAPI
app = FastAPI(title="Radar Inteligente - MVP")

# Inclui os módulos de rotas
app.include_router(api_router)
app.include_router(editoras_router)

# Endpoint raiz (teste de status da API)
@app.get("/")
def root():
    return {"message": "Radar Inteligente API Online"}
