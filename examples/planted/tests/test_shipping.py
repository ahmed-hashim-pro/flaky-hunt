import random

from shop.shipping import cost


def test_bulk_discount():  # unseeded random input: fails when it draws 10
    parcels = random.randint(1, 10)
    expected = 4.50 * parcels * (0.9 if parcels >= 5 else 1)
    assert cost(parcels) == round(expected, 2)


def test_single_parcel():
    assert cost(1) == 4.50
