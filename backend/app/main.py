from fastapi import FastAPI

app = FastAPI(title="AI Engineering Assistant")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
