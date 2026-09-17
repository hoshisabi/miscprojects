"""
Prose tests that never run the simulation.

narrative.render() is documented as a pure function over a game_summary dict, so
prose can be tested by handing it synthetic state. That is the cheap path: the
sim-backed suites each cost a full run, and Vellum flagged CI time as the reason
not to keep adding them. Anything about *wording* belongs here; anything about
whether the sim produces the right facts belongs in test_prose_fidelity.

Run from ancient_nations/:
    uv run python -m unittest tests.test_narrative_render -v
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import narrative  # noqa: E402


def nation(name, trait, territory=100, population=1000, alive=True, **kw):
    """A snapshot nation row with sane defaults; override what the test cares about."""
    row = {
        'name': name, 'trait': trait, 'alive': alive,
        'territory': territory, 'population': population,
        'towns': [{'name': f'{name}ium'}], 'capital': f'{name}ium',
        'wars_with': [], 'allied_with': [],
        'founding_turn': 0, 'founding_capital': f'{name}ium', 'founding_towns': 1,
        'death_turn': None, 'absorbed_by': None,
    }
    row.update(kw)
    return row


def state(nations, events=(), battles=(), turn=100, territory_log=None):
    return {
        'turn': turn, 'seed': 42, 'map_size': 100,
        'nations': list(nations),
        'events': list(events), 'battles': list(battles),
        'resource_values': {'Food': 1.0, 'Wood': 1.0, 'Metal': 1.0, 'Gold': 1.0},
        'territory_log': territory_log if territory_log is not None else [],
        'logs': [],
    }


def event(etype, turn=50, **effects):
    return {'type': etype, 'turn': turn, 'location': [1, 2], 'radius': 1,
            'magnitude': 5, 'description': 'x', 'effects': effects}


class TestArticleHelper(unittest.TestCase):
    """_article is the single place the a/an choice is made."""

    def test_vowel_led_words_take_an(self):
        for word in ('Expansionist', 'expansionist', 'Aggressive', 'Isolationist', 'Opportunist'):
            self.assertEqual(narrative._article(word), 'an', word)

    def test_consonant_led_words_take_a(self):
        for word in ('Militarist', 'Zealot', 'Builder', 'Diplomat', 'Merchant'):
            self.assertEqual(narrative._article(word), 'a', word)

    def test_handles_empty_and_none_without_raising(self):
        self.assertEqual(narrative._article(''), 'a')
        self.assertEqual(narrative._article(None), 'a')


class TestArticleIsWiredIntoEveryTemplate(unittest.TestCase):
    """The helper existing is not the point; every template has to call it.

    Each of these three sentences built its own article at some point, and the
    rebellion and assassination ones were still emitting "a Expansionist" after
    the founding line was fixed.
    """

    def test_founding_line(self):
        out = narrative.render(state([nation('Aegia', 'Expansionist'),
                                      nation('Borum', 'Militarist')]))
        self.assertIn('an expansionist people', out)
        self.assertIn('a militarist people', out)

    def test_rebellion_line(self):
        out = narrative.render(state(
            [nation('Aegia', 'Militarist'), nation('Borum', 'Builder')],
            events=[event('rebellion', parent='Aegia', rebel='Borum',
                          tiles_split=200, trait='Expansionist')]))
        self.assertIn('declaring themselves an Expansionist state', out)

    def test_assassination_line(self):
        out = narrative.render(state(
            [nation('Aegia', 'Militarist'), nation('Borum', 'Builder')],
            events=[event('assassination', nation='Aegia',
                          new_trait='Expansionist', trait_changed=True)]))
        self.assertIn('ushering in an Expansionist era', out)

    def test_no_stranded_article_anywhere_in_a_vowel_heavy_chronicle(self):
        out = narrative.render(state(
            [nation('Aegia', 'Expansionist'), nation('Borum', 'Isolationist')],
            events=[event('rebellion', parent='Aegia', rebel='Borum',
                          tiles_split=200, trait='Expansionist'),
                    event('assassination', nation='Aegia',
                          new_trait='Opportunist', trait_changed=True)]))
        self.assertNotRegex(out, r'\ba [AEIOUaeiou][a-z]*\b')


class TestDominantForceSentence(unittest.TestCase):
    """Rules Vellum specified: alive, most territory, strictly ahead, else silent."""

    TWO_FRONTS = [
        {'turn': 10, 'attacker': 'Aegia', 'defender': 'Borum', 'winner': 'Aegia'},
        {'turn': 11, 'attacker': 'Aegia', 'defender': 'Borum', 'winner': 'Aegia'},
        {'turn': 12, 'attacker': 'Borum', 'defender': 'Cirra', 'winner': 'Borum'},
    ]

    def test_names_the_territory_leader_not_the_battle_winner(self):
        out = narrative.render(state(
            [nation('Aegia', 'Militarist', territory=10),
             nation('Borum', 'Builder', territory=900),
             nation('Cirra', 'Zealot', territory=20)],
            battles=self.TWO_FRONTS))
        self.assertIn('Borum proved the dominant force', out)
        self.assertNotIn('Aegia proved the dominant force', out)

    def test_silent_when_the_leader_is_tied(self):
        out = narrative.render(state(
            [nation('Aegia', 'Militarist', territory=100),
             nation('Borum', 'Builder', territory=100),
             nation('Cirra', 'Zealot', territory=20)],
            battles=self.TWO_FRONTS))
        self.assertNotIn('proved the dominant force', out)

    def test_a_corpse_is_never_the_dominant_force(self):
        """A dead nation's territory is zeroed, so it cannot lead."""
        out = narrative.render(state(
            [nation('Aegia', 'Militarist', territory=0, population=0,
                    alive=False, death_turn=40, towns=[], capital=None),
             nation('Borum', 'Builder', territory=50),
             nation('Cirra', 'Zealot', territory=20)],
            battles=self.TWO_FRONTS))
        self.assertNotIn('Aegia proved the dominant force', out)
        self.assertIn('Borum proved the dominant force', out)


if __name__ == '__main__':
    unittest.main()
