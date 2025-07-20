from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.schemas.oncall import OnCallShiftOut
from src.core.services.user_services import UserManager

from .deps import get_db

# ─── Auth / User Router ─────────────────────────────────────────────────────---

auth_router = APIRouter(prefix="/oncall", tags=["oncall"])


@auth_router.get(
    "",
    response_model=Optional[OnCallShiftOut],
    operation_id="get_oncall_shift",
)
async def get_oncall_shift(db: AsyncSession = Depends(get_db)) -> Optional[OnCallShiftOut]:
    shift = await UserManager().get_current_oncall(db)
    return OnCallShiftOut.model_validate(shift) if shift else None


__all__ = ["auth_router"]
