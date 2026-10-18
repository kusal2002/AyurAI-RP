from fastapi import FastAPI

from app.api.neo4j_health import router as neo4j_health_router
from app.api.c1 import router as c1_router
from app.api.c1_c2 import router as c1_c2_router
from app.api.c2 import router as c2_router


app = FastAPI(
    title="AyurAI Component 2 API",
    description=(
        "Ayurvedic Knowledge Graph, Reasoning "
        "and Recommendation Engine"
    ),
    version="0.1.0",
)

app.include_router(neo4j_health_router)
app.include_router(c1_router)
app.include_router(c1_c2_router)
app.include_router(c2_router)


@app.get("/")
def root():
    return {
        "component": "AyurAI Component 2",
        "status": "running",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
    }
