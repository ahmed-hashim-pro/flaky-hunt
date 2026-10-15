import threading

from shop.inventory import Inventory


def test_parallel_reservations_use_all_stock():  # a race: lost updates
    inv = Inventory(stock=40_000)

    def worker():
        for _ in range(10_000):
            inv.reserve()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert inv.stock == 0


def test_reserve_stops_at_zero():
    inv = Inventory(stock=1)
    assert inv.reserve() and not inv.reserve()
