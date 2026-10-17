from fastapi import APIRouter

from app.models.c1_input import C1Input


router = APIRouter(
    prefix="/api/v1/c1",
    tags=["Component 1 Integration"]
)


@router.post("/screening-result")
def receive_screening_result(data: C1Input):
    return {
        "status": "accepted",
        "message": "Component 1 screening result received",
        "data": data
    }