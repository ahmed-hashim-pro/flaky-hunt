from shop.cart import add, checkout_summary


def test_checkout_hides_debug_details():  # fails after test_enable_debug_mode
    assert checkout_summary({"tea": 3.5, "cake": 2.0}) == "Total: 5.50 EUR"


def test_add_item():
    assert add({}, "tea", 3.5) == {"tea": 3.5}
