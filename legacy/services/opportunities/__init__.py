"""Crewbie A2; default callables use visibly synthetic fixtures, never network."""
from .catalog import OpportunityCatalog, get_opportunity, list_opportunities
from .models import OpportunityError, normalize
from .providers import AuthorizedImportProvider, FixtureProvider, MockProvider, Provider
from .providers import ActivityFixtureProvider
from .discovery import DiscoveryService, IdeaProvider

__all__ = ["OpportunityCatalog", "get_opportunity", "list_opportunities", "OpportunityError",
           "normalize", "AuthorizedImportProvider", "FixtureProvider", "MockProvider", "Provider",
           "DiscoveryService", "IdeaProvider", "ActivityFixtureProvider"]
