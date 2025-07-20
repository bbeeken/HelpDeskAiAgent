from pydantic import BaseModel, EmailStr, ConfigDict
from datetime import datetime


class OnCallShiftBase(BaseModel):
    user_email: EmailStr
    start_time: datetime
    end_time: datetime


class OnCallShiftOut(OnCallShiftBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
