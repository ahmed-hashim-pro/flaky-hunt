from shop.tags import render


def test_render_tags():  # expects one set order; PYTHONHASHSEED picks another half the time
    assert render({"sale", "new"}) == "sale, new"


def test_render_one_tag():
    assert render({"eco"}) == "eco"
