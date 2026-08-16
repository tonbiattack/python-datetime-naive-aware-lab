"""ISO 8601期限を判定する最小再現コード。"""

from collections.abc import Callable
from datetime import datetime, timezone, tzinfo

Clock = Callable[[tzinfo | None], datetime]


def parse_deadline(raw_deadline: str) -> datetime:
    """`Z` 付きのISO 8601文字列をdatetimeへ解析する。"""
    return datetime.fromisoformat(raw_deadline)


def is_expired(raw_deadline: str, clock: Clock = datetime.now) -> bool:
    """UTC期限がUTCの現在時刻以前ならTrueを返す。"""
    deadline = parse_deadline(raw_deadline)
    now = clock(timezone.utc)
    return now >= deadline
