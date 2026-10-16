from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.c2_endpoint import router as c2_router
from app.api.safety_assessment import router as safety_router
from app.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Component 3: Patient-Context-Aware Ayurvedic Herb-Drug Interaction "
        "and Safety Prediction Using Knowledge Graphs. "
        "Serves as the safety gate between Ayurvedic recommendation and practitioner review."
    ),
    version=settings.APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(c2_router)
app.include_router(safety_router)


@app.get("/")
def root():
    return {
        "component": "AyurAI Component 3",
        "name": "Patient-Context-Aware Ayurvedic Herb-Drug Interaction and Safety Prediction",
        "student_id": "IT23308466",
        "author": "Ransika A D L",
        "status": "operational",
        "version": settings.APP_VERSION,
        "docs_url": "/docs",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "ayurai-component3-safety-api",
        "version": settings.APP_VERSION,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=True)
