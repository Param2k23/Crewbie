"""Authentication boundary for composition; this provider is DEMO ONLY."""
from typing import Protocol
from .service import ParticipantService, PrivacyError, Owner


class IdentityProvider(Protocol):
    def authenticate(self, credential: str) -> str: ...


class DemoIdentityProvider:
    """Explicit synthetic credentials. Never use this mapping for live students."""
    def __init__(self, credentials):
        self._credentials = dict(credentials)

    def authenticate(self, credential: str) -> str:
        if not isinstance(credential, str) or credential not in self._credentials:
            raise PrivacyError("AUTHORIZATION_FAILED")
        return self._credentials[credential]


class OwnerGateway:
    """Integrator provides a real IdentityProvider in production."""
    def __init__(self, service: ParticipantService, identities: IdentityProvider):
        self._service, self._identities = service, identities

    def authenticate(self, credential: str) -> Owner:
        return self._service.owner(self._identities.authenticate(credential))
