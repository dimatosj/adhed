"""Time helpers.

`datetime.utcnow()` is deprecated in Python 3.12+. Use `now_utc()`
as its drop-in replacement.

Returns a naive UTC datetime to match the existing tz-naive DB
columns. When the schema is migrated to `TIMESTAMP WITH TIME ZONE`
(planned follow-up), drop the `.replace(tzinfo=None)` here and let
the tz-aware value flow through.
"""
from datetime import datetime, timezone


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
