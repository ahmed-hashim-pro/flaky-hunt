def render(tags: set[str]) -> str:
    return ", ".join(tags)  # bug: set order depends on PYTHONHASHSEED
