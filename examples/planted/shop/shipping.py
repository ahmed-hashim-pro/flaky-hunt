def cost(parcels: int) -> float:
    """Shipping for 1-10 parcels: 4.50 each, 10% off from five parcels."""
    price = 4.50 * parcels
    if 5 <= parcels < 10:  # bug: ten parcels get no discount
        price *= 0.9
    return round(price, 2)
