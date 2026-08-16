"""ISO 8601期限を判定する最小再現コード（意図的に不具合を含む）。"""

from collections.abc import Callable
from datetime import datetime

Clock = Callable[[], datetime]


def parse_deadline(raw_deadline: str) -> datetime:
    """`Z` 付きのISO 8601文字列をdatetimeへ解析する。"""
    return datetime.fromisoformat(raw_deadline)


def is_expired(raw_deadline: str, clock: Clock = datetime.now) -> bool:
    """期限が現在時刻以前ならTrueを返す。"""
    deadline = parse_deadline(raw_deadline)
    now = clock()
    return now >= deadline
