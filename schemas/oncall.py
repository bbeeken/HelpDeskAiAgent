from pydantic import BaseModel, EmailStr
from datetime import datetime


class OnCallShiftBase(BaseModel):
    user_email: EmailStr
    start_time: datetime
    end_time: datetime


class OnCallShiftOut(OnCallShiftBase):
    id: int

    class Config:
        orm_mode = True
