"""Install registration, authentication and deletion (FR-INS-*, NFR-PRV-03)."""

import hashlib
import hmac
import re

from crewbie.domain.errors import NotFound, Unauthorized, ValidationFailed
from crewbie.domain.intent import LIVE_STATES, IntentState
from crewbie.services import rooms
from crewbie.services.context import ServiceContext
from crewbie.services.views import InstallView

_TOKEN_FORMAT = re.compile(r"^[A-Za-z0-9_\-]{32,128}$")


def hash_token(token: str) -> str:
    """Only this hash is ever stored (FR-INS-01, NFR-SEC-01)."""
    return hashlib.sha256(token.encode()).hexdigest()


def register(ctx: ServiceContext, token: str) -> InstallView:
    """Create the install for this token, or return the existing one (FR-INS-03)."""
    if not _TOKEN_FORMAT.match(token):
        raise ValidationFailed({"authorization": "token must be 32 to 128 URL-safe characters"})
    token_hash = hash_token(token)
    with ctx.uow_factory() as uow:
        existing = uow.installs.get_by_token_hash(token_hash)
        if existing is not None:
            link = uow.links.get_by_install(existing.id)
            return InstallView(
                existing.id, link is not None, link.discord_username if link else None
            )
        install = uow.installs.add(ctx.new_id("in"), token_hash, "cubbie")
        uow.commit()
        return InstallView(install.id, False, created=True)


def authenticate(ctx: ServiceContext, token: str) -> str:
    """Return the install id for a bearer token, comparing hashes in constant time."""
    token_hash = hash_token(token)
    with ctx.uow_factory() as uow:
        install = uow.installs.get_by_token_hash(token_hash)
        if install is None or not install.token_hash:
            raise Unauthorized("Missing or unknown token.")
        if not hmac.compare_digest(install.token_hash, token_hash):
            raise Unauthorized("Missing or unknown token.")
        return install.id


def get_me(ctx: ServiceContext, install_id: str) -> InstallView:
    with ctx.uow_factory() as uow:
        if uow.installs.get(install_id) is None:
            raise NotFound("Install not found.")
        link = uow.links.get_by_install(install_id)
        return InstallView(install_id, link is not None, link.discord_username if link else None)


def delete_me(ctx: ServiceContext, install_id: str) -> None:
    """Leave every room, then delete the install and everything that hangs off it."""
    with ctx.uow_factory() as uow:
        for intent in uow.intents.list_for_install(install_id, LIVE_STATES):
            if intent.state == IntentState.JOINED.value:
                rooms.leave(ctx, uow, intent)
        uow.installs.delete(install_id)
        uow.commit()


def ensure_discord_install(ctx: ServiceContext, discord_user_id: str, username: str) -> InstallView:
    """Discord-only students get a tokenless install on first board interaction (FR-LNK-05)."""
    with ctx.uow_factory() as uow:
        link = uow.links.get_by_discord_user(discord_user_id)
        if link is not None:
            return InstallView(link.install_id, True, link.discord_username)
        install = uow.installs.add(ctx.new_id("in"), None, "discord")
        uow.links.replace_link(install.id, discord_user_id, username)
        uow.commit()
        return InstallView(install.id, True, username, created=True)
