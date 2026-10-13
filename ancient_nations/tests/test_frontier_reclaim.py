"""Frontier reclaim Phase 1 — raider incursions (default off in balance.json5)."""
import unittest
from unittest.mock import patch

import game as game_mod
from game import Game
from entities import Army
import constants


class TestFrontierReclaimSynthetic(unittest.TestCase):
    def _living_tile(self, g):
        for n in g.nations:
            if n.alive and n.tiles:
                return next(iter(n.tiles))
        self.fail('no living nation tile')

    def test_neutral_vacancy_increments_when_disabled(self):
        g = Game(seed=99, num_nations=4)
        x, y = 50, 50
        t = g.world.t(x, y)
        t.owner = -1
        t.neutral_vacant_turns = 0
        with patch.object(constants, 'FRONTIER_RECLAIM_ENABLED', False):
            g._tick_neutral_vacancy()
        self.assertEqual(t.neutral_vacant_turns, 1)

    def test_spawn_when_enabled_on_eligible_tile(self):
        g = Game(seed=101, num_nations=4)
        nx, ny = self._living_tile(g)
        tx, ty = nx + 1, ny
        if tx >= constants.MAP_SIZE:
            tx, ty = nx - 1, ny
        tile = g.world.t(tx, ty)
        tile.owner = -1
        tile.neutral_vacant_turns = constants.FRONTIER_NEUTRAL_TURNS
        with patch.object(game_mod, 'FRONTIER_SPAWN_CHANCE', 1.0), \
             patch.object(game_mod, 'FRONTIER_MAX_RAIDERS', 12):
            g._tick_frontier_spawns(10)
        self.assertTrue(any(a.frontier_raider for a in tile.armies))

    def test_no_spawn_when_disabled(self):
        g = Game(seed=102, num_nations=4)
        nx, ny = self._living_tile(g)
        tx, ty = nx + 1, ny
        if tx >= constants.MAP_SIZE:
            tx, ty = nx - 1, ny
        tile = g.world.t(tx, ty)
        tile.owner = -1
        tile.neutral_vacant_turns = constants.FRONTIER_NEUTRAL_TURNS
        with patch.object(game_mod, 'FRONTIER_RECLAIM_ENABLED', False), \
             patch.object(game_mod, 'FRONTIER_SPAWN_CHANCE', 1.0):
            g._tick_frontier_system(10)
        self.assertFalse(tile.armies)

    def test_ttl_disbands_raider(self):
        g = Game(seed=103, num_nations=4)
        tile = g.world.t(40, 40)
        tile.owner = -1
        army = Army(40, 40, -1, level=2)
        army.frontier_raider = True
        army.spawn_turn = 1
        tile.armies.append(army)
        ttl = constants.FRONTIER_RAIDER_MAX_TTL
        g._tick_frontier_raider_ttl(1 + ttl)
        self.assertFalse(tile.armies)


class TestFrontierReclaimSimBacked(unittest.TestCase):
    def test_spawn_possible_on_long_run_with_forced_rates(self):
        """Search seeds for one run where bleed + high spawn chance produces a raider."""
        found = False
        for seed in range(1, 25):
            g = Game(seed=seed, num_nations=6)
            with patch.object(game_mod, 'FRONTIER_RECLAIM_ENABLED', True), \
                 patch.object(game_mod, 'FRONTIER_SPAWN_CHANCE', 0.05), \
                 patch.object(game_mod, 'FRONTIER_NEUTRAL_TURNS', 10):
                for _ in range(400):
                    g.process_turn()
            if g._frontier_raider_count() > 0:
                found = True
                break
            msgs = ' '.join(m for _t, m, _n in g.logs)
            if 'Frontier raiders emerge' in msgs:
                found = True
                break
        self.assertTrue(found, 'expected at least one frontier spawn in seed search 1-24')


if __name__ == '__main__':
    unittest.main()
