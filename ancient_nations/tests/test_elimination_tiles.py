"""
ISSUES #2 — a nation eliminated for having no towns and no armies releases its land.

Surrender and union hand every tile to the winner. The third death path,
`_check_eliminations`, has no winner, so the remaining tiles go neutral. Before
this, the world grid kept the dead slot as owner; neglect skips dead nations, so
the land stayed frozen, and a revived rebel slot inherited it as ghost tiles
missing from its own `tiles` set.

Run from ancient_nations/:
    uv run python -m unittest tests.test_elimination_tiles
"""

import unittest

from engine import GameSession


def owned_in_grid(game, idx):
    return {(t.x, t.y) for row in game.world.tiles for t in row if t.owner == idx}


class TestEliminationReleasesTiles(unittest.TestCase):

    def setUp(self):
        self.game = GameSession(seed=1).game
        self.victim = max(self.game.nations, key=lambda n: len(n.tiles))
        self.held = set(self.victim.tiles)
        self.assertTrue(self.held, 'victim should start with land')
        # Strip what keeps it alive, leave the land.
        for town in self.victim.towns:
            self.game.world.t(town.x, town.y).town = None
        self.victim.towns = []
        for army in self.victim.armies:
            tile = self.game.world.t(army.x, army.y)
            if army in tile.armies: tile.armies.remove(army)
            if tile.army is army:   tile.army = tile.armies[0] if tile.armies else None
        self.victim.armies = []
        self.game._check_eliminations(self.game.turn)

    def test_dead(self):
        self.assertFalse(self.victim.alive)

    def test_nation_holds_no_tiles(self):
        self.assertEqual(self.victim.tiles, set())

    def test_grid_has_no_tiles_owned_by_dead_slot(self):
        self.assertEqual(owned_in_grid(self.game, self.victim.idx), set())

    def test_released_tiles_are_neutral(self):
        for x, y in self.held:
            self.assertEqual(self.game.world.t(x, y).owner, -1)


if __name__ == '__main__':
    unittest.main()
