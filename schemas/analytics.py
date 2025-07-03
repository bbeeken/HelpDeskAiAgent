from pydantic import BaseModel
from typing import Optional

class StatusCount(BaseModel):
    status_id: Optional[int]
    status_label: Optional[str]
    count: int

class SiteOpenCount(BaseModel):
    site_id: Optional[int]
    site_label: Optional[str]
    count: int
