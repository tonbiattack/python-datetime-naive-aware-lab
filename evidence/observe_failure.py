"""不具合の観測を最小限の出力で再現する。"""

from datetime import datetime, tzinfo
import sys

sys.path.insert(0, "src")

from deadline_guard import is_expired, parse_deadline


raw_deadline = "2026-08-20T00:00:00Z"


def clock(zone: tzinfo | None = None) -> datetime:
    return datetime(2026, 8, 19, 0, 0, 0, tzinfo=zone)


deadline = parse_deadline(raw_deadline)
now = clock()

for label, value in (("deadline", deadline), ("now", now)):
    print(
        f"{label}: value={value!r}, tzinfo={value.tzinfo!r}, "
        f"utcoffset={value.utcoffset()!r}"
    )

try:
    print(f"is_expired: {is_expired(raw_deadline, clock)}")
except TypeError as error:
    print(f"is_expired raised: {type(error).__name__}: {error}")
    raise
