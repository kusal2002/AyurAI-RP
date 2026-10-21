"""Component 4 API — security & governance service for AyurAI.

Run from anywhere:  python component4/api/main.py   (listens on port 8004)
Interactive docs:   http://127.0.0.1:8004/docs
"""

import uvicorn
from fastapi import FastAPI

from database import Base, engine
from routers import audit_routes, auth_routes, decision_routes, fakl_routes, federation_routes

# Create the tables if they do not exist yet (fine for a prototype;
# a production system would use migrations instead)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AyurAI Component 4 — Privacy, Security & Governance",
    version="0.1.0",
)
app.include_router(auth_routes.router)
app.include_router(decision_routes.router)
app.include_router(audit_routes.router)
app.include_router(federation_routes.router)
app.include_router(fakl_routes.router)


@app.get("/health")
def health():
    # Same shape as the Component 2 / 3 health endpoints used by the dashboard
    return {"status": "healthy", "service": "component4"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8004)
