import threading
import time

from crewbie.services.locks import RoomLocks


def test_one_room_is_held_by_one_thread_at_a_time() -> None:
    locks = RoomLocks()
    inside = 0
    overlaps = 0
    guard = threading.Lock()

    def work() -> None:
        nonlocal inside, overlaps
        with locks.hold(["r1"]):
            with guard:
                inside += 1
                overlaps += inside > 1
            time.sleep(0.01)
            with guard:
                inside -= 1

    threads = [threading.Thread(target=work) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    assert overlaps == 0


def test_holding_rooms_in_opposite_orders_cannot_deadlock() -> None:
    locks = RoomLocks()
    finished: list[str] = []

    def take(order: list[str], name: str) -> None:
        for _ in range(50):
            with locks.hold(order):
                pass
        finished.append(name)

    first = threading.Thread(target=take, args=(["a", "b"], "first"))
    second = threading.Thread(target=take, args=(["b", "a", "a"], "second"))
    first.start()
    second.start()
    first.join(timeout=5)
    second.join(timeout=5)
    assert sorted(finished) == ["first", "second"]


def test_different_rooms_do_not_block_each_other() -> None:
    locks = RoomLocks()
    with locks.hold(["a"]), locks.hold(["b"]):
        pass
