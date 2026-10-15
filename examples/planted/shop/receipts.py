from datetime import datetime


def receipt_epoch(when: datetime) -> int:
    """Seconds since the epoch for a receipt. `when` is meant to be UTC."""
    return int(when.timestamp())  # bug: a naive datetime is read as *local* time
