"""naive/awareな日時混在を防ぐ振る舞いテスト。"""

from datetime import datetime, timezone, tzinfo
import sys
import unittest

sys.path.insert(0, "src")

from deadline_guard import is_expired


class DeadlineGuardTest(unittest.TestCase):
    def test_future_utc_deadline_is_not_expired(self) -> None:
        """元の失敗ケース: 未来のUTC期限は期限切れではない。"""
        def fixed_clock(zone: tzinfo | None = None) -> datetime:
            return datetime(2026, 8, 19, 0, 0, 0, tzinfo=zone)

        self.assertFalse(
            is_expired("2026-08-20T00:00:00Z", fixed_clock),
            "未来のUTC期限は期限切れではないはずである",
        )

    def test_past_utc_deadline_is_expired(self) -> None:
        """対照ケース: 過去のUTC期限は期限切れになる。"""
        def fixed_clock(zone: tzinfo | None = None) -> datetime:
            return datetime(2026, 8, 21, 0, 0, 0, tzinfo=zone)

        self.assertTrue(is_expired("2026-08-20T00:00:00Z", fixed_clock))

    def test_clock_receives_utc_timezone(self) -> None:
        """回帰防止: 現在時刻の生成時にUTCを明示する。"""
        received_zones: list[tzinfo | None] = []

        def recording_clock(zone: tzinfo | None = None) -> datetime:
            received_zones.append(zone)
            return datetime(2026, 8, 19, 0, 0, 0, tzinfo=zone)

        is_expired("2026-08-20T00:00:00Z", recording_clock)

        self.assertEqual(received_zones, [timezone.utc])


if __name__ == "__main__":
    unittest.main()
