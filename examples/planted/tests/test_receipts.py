from datetime import datetime

from shop.receipts import receipt_epoch


def test_receipt_epoch():  # only right when the machine's zone is UTC
    assert receipt_epoch(datetime(2024, 1, 1, 9, 0)) == 1704099600
