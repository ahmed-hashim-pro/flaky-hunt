from shop.cache import init_cache


def test_init_cache_creates_price_file():  # leaks a directory into TMPDIR
    d = init_cache()
    assert (d / "prices.json").read_text() == "{}"
