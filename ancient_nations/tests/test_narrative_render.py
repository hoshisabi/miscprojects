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


class TestTerritoryLookup(unittest.TestCase):
    """territory_log is sampled, so lookups must handle turns between samples."""

    LOG = [
        {'turn': 10, 'territory': {'Aegia': 100, 'Borum': 50}},
        {'turn': 20, 'territory': {'Aegia': 200, 'Borum': 60}},
        {'turn': 30, 'territory': {'Aegia': 300, 'Borum': 70}},
    ]

    def _state(self):
        return state([nation('Aegia', 'Militarist', territory=999),
                      nation('Borum', 'Builder', territory=80)],
                     turn=40, territory_log=self.LOG)

    def test_exact_sample_is_used(self):
        self.assertEqual(narrative._territory_at(self._state(), 20)['Aegia'], 200)

    def test_between_samples_falls_back_to_the_nearest_earlier_one(self):
        self.assertEqual(narrative._territory_at(self._state(), 27)['Aegia'], 200)

    def test_final_turn_comes_from_live_rows_not_the_log(self):
        self.assertEqual(narrative._territory_at(self._state(), 40)['Aegia'], 999)

    def test_before_the_first_sample_is_unknown(self):
        self.assertIsNone(narrative._territory_at(self._state(), 5))

    def test_missing_log_is_unknown_rather_than_an_error(self):
        st = state([nation('Aegia', 'Militarist')], turn=40)
        self.assertIsNone(narrative._territory_at(st, 20))

    def test_a_renamed_slot_is_described_by_the_name_it_had_then(self):
        """A revived slot is renamed, so each sample carries the names in use at
        that turn. Looking up an early era must not use the later name."""
        log = [{'turn': 10, 'territory': {'Aegia': 500, 'Borum': 10}},
               {'turn': 30, 'territory': {'Cirra': 700, 'Borum': 10}}]
        st = state([nation('Cirra', 'Zealot', territory=700),
                    nation('Borum', 'Builder', territory=10)],
                   turn=40, territory_log=log)
        self.assertEqual(narrative._dominant_at(st, 10), ('Aegia', 500))
        self.assertEqual(narrative._dominant_at(st, 30), ('Cirra', 700))


class TestEraBattleCount(unittest.TestCase):
    """The era header is inclusive (Turns 1–100), so the body must count the same way."""

    def test_turn_count_matches_the_inclusive_header(self):
        out = narrative.render(state(
            [nation('Aegia', 'Militarist'), nation('Borum', 'Builder')],
            battles=[{'turn': 10, 'attacker': 'Aegia', 'defender': 'Borum', 'winner': 'Aegia'},
                     {'turn': 11, 'attacker': 'Aegia', 'defender': 'Borum', 'winner': 'Aegia'}]))
        self.assertIn('(Turns 1–100)', out)
        self.assertIn('2 battles were fought across 100 turns', out)

    def test_one_battle_is_singular(self):
        out = narrative.render(state(
            [nation('Aegia', 'Militarist'), nation('Borum', 'Builder')],
            battles=[{'turn': 10, 'attacker': 'Aegia', 'defender': 'Borum', 'winner': 'Aegia'}]))
        self.assertIn('1 battle was fought across 100 turns', out)
        self.assertNotIn('1 battles', out)


class TestRenderSpan(unittest.TestCase):
    """Ticket F: a turn window reads as a chapter, not a filtered dump."""

    LOG = [{'turn': t, 'territory': {'Aegia': 100 + t, 'Borum': 50, 'Cirra': 40}}
           for t in range(10, 200, 10)]

    def _state(self, battles=(), events=(), nations=None, log=None):
        nations = nations or [nation('Aegia', 'Militarist', territory=400),
                              nation('Borum', 'Builder', territory=60),
                              nation('Cirra', 'Zealot', territory=30)]
        return state(nations, battles=battles, events=events, turn=200,
                     territory_log=self.LOG if log is None else log)

    def test_only_the_window_is_narrated(self):
        st = self._state(
            battles=[{'turn': 35, 'attacker': 'Aegia', 'defender': 'Borum', 'winner': 'Aegia'},
                     {'turn': 150, 'attacker': 'Borum', 'defender': 'Cirra', 'winner': 'Cirra'}],
            events=[event('drought', turn=40, food_lost=10, nations_affected=1),
                    event('flood', turn=120, tiles_flooded=4)])
        out = narrative.render_span(st, 30, 80)
        self.assertIn('(Turns 30–80)', out)
        self.assertIn('1 battle was fought across 51 turns', out)
        self.assertIn('Drought', out)
        self.assertNotIn('Floods', out)
        self.assertNotIn('Cirra held the upper hand', out)

    def test_no_founding_block_or_final_standing(self):
        out = narrative.render_span(self._state(), 30, 80)
        self.assertNotIn('rose from the wilderness', out)
        self.assertNotIn('FINAL STANDING', out)
        self.assertIn('A chapter: turns 30–80 of 200.', out)

    def test_whole_game_window_is_the_full_chronicle(self):
        st = self._state()
        self.assertEqual(narrative.render_span(st, 1, 200), narrative.render(st))

    def test_names_the_land_leader_at_the_end_of_a_calm_window(self):
        """No battles, so the conflict sentence can't carry it."""
        out = narrative.render_span(self._state(), 30, 80)
        self.assertIn('By turn 80, Aegia held the most land: 180 tiles.', out)

    def test_leader_between_samples_uses_the_nearest_earlier_one(self):
        out = narrative.render_span(self._state(), 30, 85)
        self.assertIn('By turn 85, Aegia held the most land: 180 tiles.', out)

    def test_silent_when_nobody_leads(self):
        log = [{'turn': 80, 'territory': {'Aegia': 50, 'Borum': 50, 'Cirra': 40}}]
        out = narrative.render_span(self._state(log=log), 30, 80)
        self.assertNotIn('held the most land', out)
        self.assertNotIn('dominant force', out)

    def test_leader_is_named_once_when_several_fronts_already_name_it(self):
        st = self._state(battles=[
            {'turn': 40, 'attacker': 'Aegia', 'defender': 'Borum', 'winner': 'Aegia'},
            {'turn': 41, 'attacker': 'Borum', 'defender': 'Cirra', 'winner': 'Borum'}])
        out = narrative.render_span(st, 30, 80)
        self.assertIn('Aegia proved the dominant force, holding 180 tiles by turn 80', out)
        self.assertNotIn('held the most land', out)

    def test_names_deaths_inside_the_window_only(self):
        st = self._state(nations=[
            nation('Aegia', 'Militarist', territory=400),
            nation('Borum', 'Builder', territory=0, alive=False, death_turn=60,
                   absorbed_by='Aegia', towns=[], capital=None),
            nation('Cirra', 'Zealot', territory=0, alive=False, death_turn=150,
                   towns=[], capital=None)])
        out = narrative.render_span(st, 30, 80)
        self.assertIn('Borum fell in turn 60, absorbed by Aegia.', out)
        self.assertNotIn('Cirra fell', out)

    def test_era_name_agrees_with_the_full_chronicle(self):
        """Turn 30 sits in the first era of a 200-turn chronicle."""
        out = narrative.render_span(self._state(), 30, 80)
        self.assertIn('The Age of Founding (Turns 30–80)', out)
        out = narrative.render_span(self._state(), 120, 150)
        self.assertIn('The Quiet Age (Turns 120–150)', out)

    def test_window_past_the_game_is_refused(self):
        with self.assertRaises(ValueError):
            narrative.render_span(self._state(), 30, 250)
        with self.assertRaises(ValueError):
            narrative.render_span(self._state(), 80, 30)


if __name__ == '__main__':
    unittest.main()


class TestPopulationIsReadable(unittest.TestCase):
    """ISSUES #8: raw counts reach tens of millions and stop meaning anything."""

    def test_scales(self):
        self.assertEqual(narrative.approx_pop(812), '812')
        self.assertEqual(narrative.approx_pop(127_400), '127k')
        self.assertEqual(narrative.approx_pop(40_230_000), '40.2 million')

    def test_plague_deaths_use_the_same_scale(self):
        out = narrative.render(state(
            [nation('Aegia', 'Militarist'), nation('Borum', 'Builder')],
            events=[event('plague', pop_lost=2_500_000, armies_weakened=3)]))
        self.assertIn('killing 2.5 million', out)
        self.assertNotIn('2500000', out)
