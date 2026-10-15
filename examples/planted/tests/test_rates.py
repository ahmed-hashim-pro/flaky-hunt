from shop.rates import fetch_index


def test_price_index_reachable():  # quietly needs the internet
    assert fetch_index() == 200
