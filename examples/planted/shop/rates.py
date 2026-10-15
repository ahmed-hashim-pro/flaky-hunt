import urllib.request


def fetch_index() -> int:
    """Stands in for any call to a live service: here, PyPI's index page for pip."""
    with urllib.request.urlopen("https://pypi.org/simple/pip/", timeout=10) as r:
        return r.status
