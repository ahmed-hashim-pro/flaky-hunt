from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class Coupon:
    code: str
    expires: datetime


def issue(code: str, valid_for: timedelta) -> Coupon:
    return Coupon(code, datetime.now() + valid_for)
