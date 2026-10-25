"""An in-memory Discord that implements the same `Gateway` protocol as production."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from crewbie.discord_bot.gateway import DmClosedError
from crewbie.discord_bot.messages import BoardCard


@dataclass
class FakeGateway:
    threads: dict[str, str] = field(default_factory=dict)  # thread id -> name
    members: dict[str, set[str]] = field(default_factory=dict)  # thread id -> user ids
    posts: list[tuple[str, str]] = field(default_factory=list)  # (thread id, content)
    dms: list[tuple[str, str]] = field(default_factory=list)
    cards: dict[str, BoardCard] = field(default_factory=dict)  # message id -> card
    card_history: list[tuple[str, str | None]] = field(default_factory=list)
    archived: list[str] = field(default_factory=list)
    dm_closed: set[str] = field(default_factory=set)
    failures: dict[str, int] = field(default_factory=dict)  # operation -> times to fail
    calls: list[str] = field(default_factory=list)
    _next: int = 9_000_000_000_000_000

    def _enter(self, operation: str) -> None:
        self.calls.append(operation)
        if self.failures.get(operation, 0) > 0:
            self.failures[operation] -= 1
            raise ConnectionError(f"{operation} failed")

    def _id(self) -> str:
        self._next += 1
        return str(self._next)

    async def create_private_thread(self, name: str) -> str:
        self._enter("create_thread")
        thread_id = self._id()
        self.threads[thread_id] = name
        self.members[thread_id] = set()
        return thread_id

    async def add_user(self, thread_id: str, user_id: str) -> None:
        self._enter("add_user")
        self.members[thread_id].add(user_id)

    async def remove_user(self, thread_id: str, user_id: str) -> None:
        self._enter("remove_user")
        self.members[thread_id].discard(user_id)

    async def post_message(
        self, thread_id: str, content: str, mention_user_ids: Sequence[str] = ()
    ) -> str:
        self._enter("post_message")
        self.posts.append((thread_id, content))
        return self._id()

    async def send_dm(self, user_id: str, content: str) -> None:
        self._enter("send_dm")
        if user_id in self.dm_closed:
            raise DmClosedError(user_id)
        self.dms.append((user_id, content))

    async def upsert_board_card(self, card: BoardCard, message_id: str | None) -> str:
        self._enter("upsert_board_card")
        new_id = message_id if message_id in self.cards else self._id()
        self.cards[new_id] = card
        self.card_history.append((new_id, message_id))
        return new_id

    async def delete_board_card(self, message_id: str) -> None:
        self._enter("delete_board_card")
        self.cards.pop(message_id, None)

    async def archive_thread(self, thread_id: str) -> None:
        self._enter("archive_thread")
        self.archived.append(thread_id)

    def everything_said(self) -> str:
        """Every string the bot sent anywhere, for privacy scans."""
        cards = [repr(card) for card in self.cards.values()]
        return "\n".join([c for _, c in self.posts] + [c for _, c in self.dms] + cards)
