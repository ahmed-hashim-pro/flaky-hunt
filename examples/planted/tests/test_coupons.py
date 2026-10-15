from datetime import date, timedelta

from shop.coupons import issue


def test_short_coupon_expires_today():  # fails in the last ten minutes of the day
    coupon = issue("TEN", valid_for=timedelta(minutes=10))
    assert coupon.expires.date() == date.today()


def test_coupon_code_kept():
    assert issue("ABC", timedelta(days=1)).code == "ABC"
