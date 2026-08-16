"""naive/awareな日時混在を再現する振る舞いテスト。"""

from datetime import datetime, tzinfo
import sys
import unittest

sys.path.insert(0, "src")

from deadline_guard import is_expired


class DeadlineGuardTest(unittest.TestCase):
    def test_future_utc_deadline_is_not_expired(self) -> None:
        """利用者はUTC期限と現在時刻を比較できると期待している。"""
        def fixed_clock(zone: tzinfo | None = None) -> datetime:
            return datetime(2026, 8, 19, 0, 0, 0, tzinfo=zone)

        self.assertFalse(
            is_expired("2026-08-20T00:00:00Z", fixed_clock),
            "未来のUTC期限は期限切れではないはずである",
        )


if __name__ == "__main__":
    unittest.main()
