from collections.abc import Callable
from datetime import timedelta

from crewbie.persistence.outbox import MAX_RETRIES, OutboxState, backoff_seconds
from crewbie.persistence.unit_of_work import UnitOfWork
from tests.unit.domain.helpers import at

Factory = Callable[[], UnitOfWork]


def test_nfr_rel_01_backoff_schedule_is_1_2_4_8_16() -> None:
    assert [backoff_seconds(n) for n in range(1, 6)] == [1, 2, 4, 8, 16]


def test_fr_bot_01_enqueue_is_idempotent_by_dedupe_key(uow_factory: Factory) -> None:
    with uow_factory() as uow:
        assert uow.outbox.enqueue("j1", "create_thread", {"room_id": "r"}, "thread:r", at(0))
        assert not uow.outbox.enqueue("j2", "create_thread", {"room_id": "r"}, "thread:r", at(0))
        uow.commit()
        assert [j.id for j in uow.outbox.due(at(0))] == ["j1"]
        assert uow.outbox.backlog() == 1


def test_nfr_rel_02_pending_jobs_survive_restart(uow_factory: Factory) -> None:
    with uow_factory() as uow:
        uow.outbox.enqueue("j1", "post_message", {"text": "hi"}, "k1", at(0))
        uow.commit()
    with uow_factory() as uow:
        due = uow.outbox.due(at(0))
        assert [(j.kind, j.payload) for j in due] == [("post_message", {"text": "hi"})]


def test_nfr_rel_01_failures_back_off_then_give_up_after_five_retries(uow_factory: Factory) -> None:
    with uow_factory() as uow:
        uow.outbox.enqueue("j1", "dm_user", {}, "k1", at(0))
        now = at(0)
        waits = []
        for _ in range(MAX_RETRIES):
            assert uow.outbox.mark_failed_attempt("j1", "boom", now) is OutboxState.PENDING
            job = uow.outbox.due(now + timedelta(days=1))[0]
            waits.append(int((job.next_attempt_at - now).total_seconds()))
            assert uow.outbox.due(job.next_attempt_at - timedelta(milliseconds=1)) == []
            now = job.next_attempt_at
        assert waits == [1, 2, 4, 8, 16]
        assert uow.outbox.mark_failed_attempt("j1", "x" * 900, now) is OutboxState.FAILED
        assert uow.outbox.due(now + timedelta(days=1)) == []
        assert uow.outbox.backlog() == 0


def test_mark_done_removes_job_from_due_and_backlog(uow_factory: Factory) -> None:
    with uow_factory() as uow:
        uow.outbox.enqueue("j1", "dm_user", {}, "k1", at(0))
        uow.outbox.enqueue("j2", "dm_user", {}, "k2", at(5))
        uow.outbox.mark_done("j1")
        assert [j.id for j in uow.outbox.due(at(10))] == ["j2"]
        assert uow.outbox.due(at(4)) == []
        assert uow.outbox.backlog() == 1
