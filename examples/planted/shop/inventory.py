class Inventory:
    def __init__(self, stock: int):
        self.stock = stock

    def reserve(self) -> bool:
        current = self.stock  # read ...
        if current <= 0:
            return False
        self.stock = self._after_reserving(current)  # ... then write: another thread
        return True  # can get in between

    def _after_reserving(self, stock: int) -> int:
        return stock - 1
