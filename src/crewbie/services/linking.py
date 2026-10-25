"""Discord linking (FR-LNK-*)."""

import secrets
from datetime import timedelta

from crewbie.domain.errors import LinkCodeInvalid, LinkConflict, NotFound
from crewbie.persistence.unit_of_work import UnitOfWork
from crewbie.services.context import ServiceContext
from crewbie.services.views import InstallView, LinkCodeView

# No 0, O, 1 or I (FR-LNK-01).
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 6


def issue_code(ctx: ServiceContext, uow: UnitOfWork, install_id: str) -> LinkCodeView:
    """Create a fresh code inside the caller's transaction; older unused codes stop working."""
    expires_at = ctx.clock() + timedelta(minutes=ctx.config.link_code_ttl_minutes)
    uow.links.delete_unused_codes(install_id)
    code = _unused_code(uow)
    uow.links.add_code(code, install_id, expires_at)
    return LinkCodeView(
        code=code,
        expires_at=expires_at,
        invite_url=ctx.config.invite_url or None,
        command=f"/crew link code:{code}",
    )


def create_link_code(ctx: ServiceContext, install_id: str) -> LinkCodeView:
    with ctx.uow_factory() as uow:
        if uow.installs.get(install_id) is None:
            raise NotFound("Install not found.")
        view = issue_code(ctx, uow, install_id)
        uow.commit()
    return view


def _unused_code(uow: UnitOfWork) -> str:
    for _ in range(10):
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if uow.links.get_code(code) is None:
            return code
    raise RuntimeError("could not allocate a link code")


def complete(
    ctx: ServiceContext,
    code: str,
    discord_user_id: str,
    username: str,
    *,
    replace: bool = False,
) -> InstallView:
    """Called by the bot for `/crew link`. Reveals nothing about the install on failure."""
    now = ctx.clock()
    with ctx.uow_factory() as uow:
        row = uow.links.get_code(code.strip().upper())
        if row is None:
            raise LinkCodeInvalid("That code is not valid.", {"reason": "unknown"})
        if row.used_at is not None:
            raise LinkCodeInvalid("That code was already used.", {"reason": "used"})
        if row.expires_at <= now:
            raise LinkCodeInvalid("That code has expired.", {"reason": "expired"})
        other_for_user = uow.links.get_by_discord_user(discord_user_id)
        if (
            other_for_user is not None
            and other_for_user.install_id != row.install_id
            and not replace
        ):
            raise LinkConflict(
                "This Discord account is linked to another install.",
                {"reason": "discord_user_linked"},
            )
        own = uow.links.get_by_install(row.install_id)
        if own is not None and own.discord_user_id != discord_user_id and not replace:
            raise LinkConflict(
                "This install is linked to another Discord account.", {"reason": "install_linked"}
            )
        uow.links.replace_link(row.install_id, discord_user_id, username)
        uow.links.mark_code_used(row.code, now)
        install_id = row.install_id
        uow.commit()
    return InstallView(install_id, True, username)
