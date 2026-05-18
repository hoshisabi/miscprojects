"""Trait uniqueness: alive nations never share a trait, including after slot revival."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from game import Game


class TestTraitUniqueness(unittest.TestCase):

    def _alive_trait_ids(self, game):
        return [n.trait['id'] for n in game.nations if n.alive]

    def test_initial_spawn_traits_unique(self):
        for seed in (1, 42, 99):
            with self.subTest(seed=seed):
                g = Game(seed=seed)
                ids = self._alive_trait_ids(g)
                self.assertEqual(len(ids), len(set(ids)),
                                 f"Seed {seed}: duplicate traits at spawn: {ids}")

    def test_rebel_spawn_trait_differs_from_alive_nations(self):
        """spawn_rebel_nation must not assign a trait already held by a living nation."""
        g = Game(seed=42)
        nations = g.nations

        # Mark one nation dead to create a slot for the rebel to occupy
        victim = nations[-1]
        victim.alive = False
        victim.death_turn = 0
        victim.rebellion_cooldown = 0

        # Pick the largest remaining alive nation as the parent
        parent = max((n for n in nations if n.alive), key=lambda n: len(n.tiles))

        # Pad tiles so the spawn conditions pass (min_tiles=30, needs room to split)
        cx, cy = next(iter(parent.tiles))
        for dx in range(-10, 11):
            for dy in range(-10, 11):
                tx, ty = cx + dx, cy + dy
                if 0 <= tx < 100 and 0 <= ty < 100:
                    parent.tiles.add((tx, ty))

        rebel = g.spawn_rebel_nation(turn=1, parent=parent, min_tiles=30)
        self.assertIsNotNone(rebel, "spawn_rebel_nation returned None — preconditions not met")

        # The rebel's trait must not duplicate any trait held by another alive nation
        other_alive_ids = {n.trait['id'] for n in nations if n.alive and n is not rebel}
        self.assertNotIn(rebel.trait['id'], other_alive_ids,
                         f"Rebel got trait '{rebel.trait['id']}' already held by an alive nation")

    def test_rebel_trait_is_valid(self):
        """Rebel trait must be one of the known trait ids."""
        g = Game(seed=7)
        valid_ids = {t['id'] for t in g.trait_list}

        # Create a dead slot
        victim = g.nations[-1]
        victim.alive = False
        victim.death_turn = 0
        victim.rebellion_cooldown = 0

        parent = max((n for n in g.nations if n.alive), key=lambda n: len(n.tiles))

        cx, cy = next(iter(parent.tiles))
        for dx in range(-8, 9):
            for dy in range(-8, 9):
                tx, ty = cx + dx, cy + dy
                if 0 <= tx < 100 and 0 <= ty < 100:
                    parent.tiles.add((tx, ty))

        rebel = g.spawn_rebel_nation(turn=1, parent=parent, min_tiles=30)
        if rebel is not None:
            self.assertIn(rebel.trait['id'], valid_ids)


if __name__ == '__main__':
    unittest.main()
