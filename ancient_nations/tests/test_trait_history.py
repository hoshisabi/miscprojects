"""Assassination-driven trait changes persist on Nation.trait_history and nation_dict."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from game import Game
import snapshot as snap


class TestTraitHistory(unittest.TestCase):

    def test_assassination_trait_change_appends_history(self):
        g = Game(seed=11, num_nations=4)
        es = g.events
        target = g.nations[0]
        old_trait = dict(target.trait)

        def fake_choice(seq):
            # Deterministic: first alternative trait in list order
            return seq[0]

        with patch('events.random.random', side_effect=[0.0, 0.0]), patch(
                'events.random.choice', fake_choice):
            es._assassination(turn=99, cx=1, cy=1, mag=1)

        self.assertTrue(target.trait_history)
        entry = target.trait_history[-1]
        self.assertEqual(entry['turn'], 99)
        self.assertEqual(entry['from_trait'], old_trait['name'])
        self.assertEqual(entry['from_trait_id'], old_trait['id'])
        self.assertEqual(entry['to_trait'], target.trait['name'])
        self.assertEqual(entry['to_trait_id'], target.trait['id'])
        self.assertNotEqual(entry['from_trait_id'], entry['to_trait_id'])

        nd = snap.nation_dict(target)
        self.assertEqual(nd['trait_history'], target.trait_history)

    def test_assassination_no_change_leaves_history_empty(self):
        g = Game(seed=13, num_nations=3)
        es = g.events
        target = g.nations[0]

        with patch('events.random.random', side_effect=[0.0, 0.99]):
            es._assassination(turn=3, cx=0, cy=0, mag=1)

        self.assertEqual(target.trait_history, [])
        nd = snap.nation_dict(target)
        self.assertEqual(nd['trait_history'], [])


if __name__ == '__main__':
    unittest.main()
