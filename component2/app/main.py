from fastapi import FastAPI

from app.api.c1 import router as c1_router


app = FastAPI(
    title="AyurAI Component 2 API",
    description=(
        "Ayurvedic Knowledge Graph, Reasoning "
        "and Recommendation Engine"
    ),
    version="0.1.0",
)

app.include_router(c1_router)


@app.get("/")
def root():
    return {
        "component": "AyurAI Component 2",
        "status": "running"
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }