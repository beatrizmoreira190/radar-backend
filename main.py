from fastapi import FastAPI
from database import engine, Base
from routes import router as api_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Radar Inteligente - MVP")
app.include_router(api_router)

@app.get("/")
def root():
    return {"message": "Radar Inteligente API Online"}
