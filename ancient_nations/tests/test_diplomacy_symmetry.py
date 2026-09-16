"""
Bilateral diplomacy invariants (the April review item, from the dead-nation angle).

For every pair (a, b): a.status_with(b) == b.status_with(a).
For every dead nation: its diplomacy maps are empty and no living nation still
holds a war, alliance, timer, or cooldown keyed on it.

Run from ancient_nations/:
    uv run python -m unittest tests.test_diplomacy_symmetry -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine import GameSession  # noqa: E402

DIPLOMACY_MAPS = ('diplomacy', 'peace_timer', 'war_cooldown', 'alliance_cd', 'alliance_age')


def _check(testcase, game):
    nations = game.nations
    for a in nations:
        for b in nations:
            if a.idx == b.idx:
                continue
            testcase.assertEqual(a.status_with(b.idx), b.status_with(a.idx),
                                 f"t{game.turn}: {a.name}->{b.name} != {b.name}->{a.name}")
    dead = [n for n in nations if not n.alive]
    for d in dead:
        for m in DIPLOMACY_MAPS:
            testcase.assertEqual(getattr(d, m), {}, f"t{game.turn}: dead {d.name} still has {m}")
        for o in nations:
            if o is d:
                continue
            for m in DIPLOMACY_MAPS:
                testcase.assertNotIn(d.idx, getattr(o, m),
                                     f"t{game.turn}: {o.name}.{m} still keyed on dead {d.name}")


class TestDiplomacySymmetry(unittest.TestCase):

    def test_symmetry_holds_every_turn_on_rowan_seed(self):
        """Seed -521411348, 100 turns: eliminations without absorption. Checked after every turn."""
        s = GameSession(seed=-521411348)
        for _ in range(100):
            s.step()
            _check(self, s.game)
        self.assertTrue(any(not n.alive for n in s.game.nations), 'fixture must exercise a death')

    def test_symmetry_holds_after_long_run_with_revivals(self):
        """Seed 123 / 500 turns is the suite's canonical mixed run (absorptions + rebellions)."""
        s = GameSession(seed=123)
        for _ in range(500):
            s.step()
            if s.game.turn % 25 == 0:
                _check(self, s.game)
        _check(self, s.game)


if __name__ == '__main__':
    unittest.main()
