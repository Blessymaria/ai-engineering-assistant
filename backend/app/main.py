from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(title="AI Engineering Assistant")
app.include_router(router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
