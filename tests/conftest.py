from datetime import datetime, timezone


def ts(dt: datetime) -> int:
    """Helper: datetime → timestamp em ms."""
    return int(dt.timestamp() * 1000)