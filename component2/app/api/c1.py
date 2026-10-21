
from fastapi import APIRouter

from app.models.c1_screening_payload import C1ScreeningPayload


router = APIRouter(
    prefix="/api/v1/c1",
    tags=["Component 1 Integration"],
)


@router.post("/screening-result")
def receive_screening_result(data: C1ScreeningPayload):
    return {
        "status": "accepted",
        "message": "Component 1 screening result received",
        "screening_id": data.screening_id,
        "data": data.model_dump(mode="json"),
    }
