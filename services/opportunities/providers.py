"""Small injected provider boundary; never retrieves authenticated pages."""
import json
from copy import deepcopy
from pathlib import Path
from typing import Protocol

from .models import OpportunityError


class Provider(Protocol):
    name: str

    def load(self) -> list[dict]: ...


class MockProvider:
    name = "mock"

    def __init__(self, records=(), unavailable=False):
        self.records = deepcopy(list(records))
        self.unavailable = unavailable

    def load(self):
        if self.unavailable:
            raise OpportunityError("SOURCE_UNAVAILABLE", "Mock source inaccessible")
        return deepcopy(self.records)


class FixtureProvider:
    name = "demo_fixture"

    def __init__(self, path=None):
        self.path = Path(path) if path else Path(__file__).resolve().parents[2] / "docs/implementation/fixtures/opportunities.json"

    def load(self):
        try:
            records = json.loads(self.path.read_text())["opportunities"]
            if not isinstance(records, list) or any(r.get("synthetic") is not True for r in records):
                raise ValueError("Fixtures must be explicitly synthetic")
            return records
        except (OSError, ValueError, KeyError, AttributeError) as exc:
            raise OpportunityError("SOURCE_UNAVAILABLE", "Invalid or inaccessible fixture") from exc


class AuthorizedImportProvider:
    """Normalize manually verified/authorized structured exports, not arbitrary HTML.

    A caller must explicitly attest permission. Denied/redirected/challenged exports
    are rejected as a whole; records behind them are never used.
    """
    name = "authorized_structured_import"

    def __init__(self, document, *, permitted=False):
        self.document = deepcopy(document)
        self.permitted = permitted

    def load(self):
        d = self.document
        if not self.permitted or not isinstance(d, dict) or d.get("access") != "public_or_authorized":
            raise OpportunityError("SOURCE_UNAVAILABLE", "Source permission/access unverified")
        if d.get("http_status", 200) != 200 or any(d.get(k) for k in ("login_redirect", "captcha", "redirect_url")):
            raise OpportunityError("SOURCE_UNAVAILABLE", "Source inaccessible; no traversal attempted")
        if not isinstance(d.get("opportunities"), list):
            raise OpportunityError("SOURCE_UNAVAILABLE", "Structured opportunities missing")
        return deepcopy(d["opportunities"])


class ActivityFixtureProvider(FixtureProvider):
    """Broader synthetic activities without replacing the legacy food fixtures."""
    def __init__(self):
        super().__init__(Path(__file__).with_name("fixtures") / "activities.json")
