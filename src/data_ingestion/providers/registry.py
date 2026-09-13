from .factory import get_market_data_provider


def get_provider(name: str):
    """Compatibility name for Phase 1 callers."""
    return get_market_data_provider(name)
