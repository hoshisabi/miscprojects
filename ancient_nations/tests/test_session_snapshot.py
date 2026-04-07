"""
Ticket A — GameSession.snapshot / turn_snapshot parity.

Verifies that session methods delegate correctly to snapshot.py with no drift.

Run from ancient_nations/:
    uv run python -m unittest tests.test_session_snapshot
"""

import sys
import unittest
from pathlib import Path

# Ensure ancient_nations/ is on the path when run from repo root.
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import GameSession
import snapshot as snap


class TestSessionSnapshotParity(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.session = GameSession(seed=1)
        cls.session.run_turns(5)

    def test_snapshot_equals_game_summary_log_limit_10(self):
        """session.snapshot(log_limit=10) must equal snapshot.game_summary(game, log_limit=10)."""
        result   = self.session.snapshot(log_limit=10)
        expected = snap.game_summary(self.session.game, log_limit=10)
        self.assertEqual(result, expected)

    def test_turn_snapshot_equals_turn_summary(self):
        """session.turn_snapshot() must equal snapshot.turn_summary(game)."""
        result   = self.session.turn_snapshot()
        expected = snap.turn_summary(self.session.game)
        self.assertEqual(result, expected)

    def test_snapshot_log_limit_not_fifty(self):
        """log_limit != 50 exercises truncation path; result must still match."""
        log_limit = 3
        result   = self.session.snapshot(log_limit=log_limit)
        expected = snap.game_summary(self.session.game, log_limit=log_limit)
        self.assertEqual(result, expected)
        self.assertLessEqual(len(result['logs']), log_limit)

    def test_snapshot_default_log_limit(self):
        """Default (log_limit=50) path must also match — catches a regression if default drifts."""
        result   = self.session.snapshot()
        expected = snap.game_summary(self.session.game, log_limit=50)
        self.assertEqual(result, expected)

    def test_snapshot_returns_plain_dict(self):
        """snapshot() must return a plain dict, not a subclass."""
        result = self.session.snapshot(log_limit=10)
        self.assertIsInstance(result, dict)
        self.assertEqual(type(result), dict)

    def test_turn_snapshot_returns_plain_dict(self):
        result = self.session.turn_snapshot()
        self.assertIsInstance(result, dict)
        self.assertEqual(type(result), dict)


if __name__ == '__main__':
    unittest.main()
