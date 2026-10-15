from shop import settings


def test_enable_debug_mode():  # changes a global and never puts it back
    settings.DEBUG = True
    assert settings.DEBUG


def test_currency_default():
    assert settings.CURRENCY == "EUR"
