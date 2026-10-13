"""Trade Step A: running costs behind balance.json5 switches (DECISIONS 2026-10-11).

Pins the rules (what each sink removes, and that the master switch restores the
food-only economy), not the tuned rates: every rate is patched here.
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from constants import RES_FOOD, RES_WOOD, RES_METAL, RES_GOLD
from game import Game
import nation as nation_mod


RATES = dict(
    RUNNING_COSTS_ENABLED=True,
    ARMY_UPKEEP_FOOD=2,
    ARMY_UPKEEP_METAL=3,
    ARMY_UPKEEP_GOLD=5,
    FOOD_SPOIL_RATE=0.1,
    FOOD_SPOIL_THRESHOLD=100,
    WOOD_ROT_RATE=0.2,
    WOOD_ROT_THRESHOLD=50,
    WOOD_UPKEEP_ROAD=1,
    WOOD_UPKEEP_CASTLE=10,
    WOOD_UPKEEP_TOWN=100,
    GOLD_ADMIN_PER_TOWN=7,
)


def _patched(**overrides):
    values = dict(RATES, **overrides)
    return [patch.object(nation_mod, k, v) for k, v in values.items()]


class RunningCostsTest(unittest.TestCase):

    def setUp(self):
        self.game = Game(seed=1, num_nations=3)
        self.n = self.game.nations[0]
        self.patches = _patched()
        for p in self.patches:
            p.start()
        # No armies, no towns: each test adds exactly what it exercises.
        army_patch = patch.object(type(self.n), 'total_armies', return_value=0)
        army_patch.start()
        self.patches.append(army_patch)
        self.n.towns = []
        self.n.tiles = set()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()

    def _stock(self, food=0, wood=0, metal=0, gold=0):
        self.n.res[RES_FOOD] = food
        self.n.res[RES_WOOD] = wood
        self.n.res[RES_METAL] = metal
        self.n.res[RES_GOLD] = gold

    def test_spoil_and_rot_take_share_above_threshold(self):
        self._stock(food=1100, wood=550)
        self.n.pay_upkeep(self.game.world)
        self.assertAlmostEqual(self.n.res[RES_FOOD], 1100 - 0.1 * (1100 - 100))
        self.assertAlmostEqual(self.n.res[RES_WOOD], 550 - 0.2 * (550 - 50))

    def test_nothing_spoils_below_threshold(self):
        self._stock(food=100, wood=50)
        self.n.pay_upkeep(self.game.world)
        self.assertEqual(self.n.res[RES_FOOD], 100)
        self.assertEqual(self.n.res[RES_WOOD], 50)

    def test_spoil_and_rot_do_not_touch_metal_or_gold(self):
        self._stock(metal=10_000, gold=10_000)
        self.n.pay_upkeep(self.game.world)
        self.assertEqual(self.n.res[RES_METAL], 10_000)
        self.assertEqual(self.n.res[RES_GOLD], 10_000)

    def test_army_upkeep_charges_all_three_goods_when_enabled(self):
        self._stock(food=40, metal=40, gold=40)
        with patch.object(type(self.n), 'total_armies', return_value=4):
            self.n.pay_upkeep(self.game.world)
        self.assertEqual(self.n.res[RES_FOOD], 40 - 2 * 4)
        self.assertEqual(self.n.res[RES_METAL], 40 - 3 * 4)
        self.assertEqual(self.n.res[RES_GOLD], 40 - 5 * 4)

    def test_town_costs_wood_and_gold(self):
        self.n.towns = [object(), object()]
        self._stock(wood=50, gold=100)
        self.n.pay_upkeep(self.game.world)
        self.assertEqual(self.n.res[RES_WOOD], 0)      # 50 - 2 * 100, clamped
        self.assertEqual(self.n.res[RES_GOLD], 100 - 2 * 7)

    def test_roads_and_castles_cost_wood_on_owned_tiles_only(self):
        w = self.game.world
        road, castle, plain = w.t(1, 1), w.t(2, 1), w.t(3, 1)
        road.road, road.entity = True, None
        castle.road, castle.entity = False, 'castle'
        plain.road, plain.entity = False, None
        other_road = w.t(4, 1)
        other_road.road = True
        self.n.tiles = {(1, 1), (2, 1), (3, 1)}
        self._stock(wood=50)                           # at threshold: no rot
        self.n.pay_upkeep(w)
        self.assertEqual(self.n.res[RES_WOOD], 50 - 1 - 10)

    def test_stock_never_goes_negative(self):
        self.n.towns = [object()]
        self._stock(wood=1, gold=1)
        with patch.object(type(self.n), 'total_armies', return_value=9):
            self.n.pay_upkeep(self.game.world)
        for r in (RES_FOOD, RES_WOOD, RES_METAL, RES_GOLD):
            self.assertGreaterEqual(self.n.res[r], 0)

    def test_master_switch_off_leaves_only_food_army_upkeep(self):
        for p in _patched(RUNNING_COSTS_ENABLED=False):
            p.start()
            self.patches.append(p)
        self.n.towns = [object()]
        self._stock(food=1100, wood=550, metal=40, gold=40)
        with patch.object(type(self.n), 'total_armies', return_value=4):
            self.n.pay_upkeep(self.game.world)
        self.assertEqual(self.n.res[RES_FOOD], 1100 - 2 * 4)
        self.assertEqual(self.n.res[RES_WOOD], 550)
        self.assertEqual(self.n.res[RES_METAL], 40)
        self.assertEqual(self.n.res[RES_GOLD], 40)

    def test_zero_rate_turns_one_sink_off(self):
        for p in _patched(FOOD_SPOIL_RATE=0):
            p.start()
            self.patches.append(p)
        self._stock(food=1100, wood=550)
        self.n.pay_upkeep(self.game.world)
        self.assertEqual(self.n.res[RES_FOOD], 1100)
        self.assertLess(self.n.res[RES_WOOD], 550)


if __name__ == '__main__':
    unittest.main()
