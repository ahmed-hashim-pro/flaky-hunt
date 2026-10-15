from . import settings


def checkout_summary(items: dict[str, float]) -> str:
    total = sum(items.values())
    text = f"Total: {total:.2f} {settings.CURRENCY}"
    if settings.DEBUG:
        text += f" [debug: {len(items)} items, raw={items!r}]"
    return text


def add(items: dict[str, float], name: str, price: float) -> dict[str, float]:
    return {**items, name: price}
