from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ExchangeRateResponse(BaseModel):
    currency: str
    rate: Decimal
    source: str
    retrieved_at: datetime
