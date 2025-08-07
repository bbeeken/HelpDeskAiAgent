from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.schemas.oncall import OnCallShiftOut
from src.core.services.user_services import UserManager

from .deps import get_db

# ─── Auth / User Router ─────────────────────────────────────────────────────---

auth_router = APIRouter(prefix="/oncall", tags=["oncall"])


@auth_router.get(
    "",
    response_model=OnCallShiftOut,
    operation_id="get_oncall_shift",
)
async def get_oncall_shift(db: AsyncSession = Depends(get_db)) -> OnCallShiftOut:
    shift = await UserManager().get_current_oncall(db)
    if not shift:
        raise HTTPException(status_code=404, detail="On-call shift not found")
    return OnCallShiftOut.model_validate(shift)


__all__ = ["auth_router"]
