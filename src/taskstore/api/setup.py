from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.api.deps import get_db
from taskstore.schemas.setup import SetupRequest, SetupResponse
from taskstore.services import setup_service

router = APIRouter(tags=["setup"])


@router.post("/api/v1/setup", response_model=SetupResponse, status_code=201)
async def setup_endpoint(
    data: SetupRequest,
    db: AsyncSession = Depends(get_db),
):
    return await setup_service.run_setup(db, data)
