from fastapi import APIRouter, Response

router = APIRouter(tags=["health"])


@router.get("/health", status_code=204)
def health_check() -> Response:
    return Response(status_code=204)
