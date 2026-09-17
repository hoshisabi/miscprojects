"""
Prose fidelity on seed -521411348 (Rowan's seed, 100 turns).

Vellum specified the intended sentences on 2026-09-16 (Vellum/VELLUM_TO_VESPER.md).
These tests assert those *rules* against the JSON snapshot of the same run, so
they hold on whatever world the seed produces after a sim change, rather than
freezing one world's constants. Nothing here hard-codes a nation name, a ruler,
or a turn number.

That was learned twice. On 2026-09-16 clearing dead-nation diplomacy changed
this seed's history after t43. On 2026-09-17 naming rulers changed it again from
turn 0, because generating a ruler name consumes randomness during spawn, so
every nation after the first got a different name. The six founding sentences
had been hard-coded on the reasoning that spawn precedes turn 1 and no turn
logic could move it — true, and beside the point, since the change was to spawn
itself. They are derived from the snapshot now.

New mechanics change results by definition, so a test that pins a world is a
test that fails on the next feature. Pin rules; derive facts.

Run from ancient_nations/:
    uv run python -m unittest tests.test_prose_fidelity -v
"""

import json
import re
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from events import is_notable  # noqa: E402

CLI = ROOT / 'cli.py'
PYTHON = sys.executable

SEED  = '-521411348'
TURNS = '100'


def run_cli(*args):
    result = subprocess.run([PYTHON, str(CLI)] + list(args), capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


class TestProseFidelity(unittest.TestCase):
    """One narrative run, one summary run, one JSON run, one notable stream - shared."""

    @classmethod
    def setUpClass(cls):
        rc, cls.narrative, err = run_cli('run', '--seed', SEED, '--turns', TURNS, '--format', 'narrative')
        assert rc == 0, err
        rc, cls.summary, err = run_cli('summary', '--seed', SEED, '--turns', TURNS)
        assert rc == 0, err
        rc, out, err = run_cli('run', '--seed', SEED, '--turns', TURNS)
        assert rc == 0, err
        cls.state = json.loads(out)
        rc, out, err = run_cli('stream', '--seed', SEED, '--turns', TURNS, '--notable')
        assert rc == 0, err
        cls.notable_lines = [json.loads(line) for line in out.splitlines() if line.strip()]

        nations = cls.state['nations']
        cls.dead  = {n['name']: n['death_turn'] for n in nations if not n['alive']}
        cls.alive = [n for n in nations if n['alive']]
        cls.events = cls.state['events']
        assert cls.dead, 'fixture must include at least one death; pick another seed'

    # -- 1. Founding paragraph -------------------------------------------------

    def test_founding_lines_match_founding_facts(self):
        """Every nation's founding sentence must match its own founding facts."""
        for n in self.state['nations']:
            trait = (n['trait'] or '').lower()
            article = 'an' if trait[:1] in 'aeiou' else 'a'
            towns = n['founding_towns']
            when = f" in turn {n['founding_turn']}" if n['founding_turn'] else ""
            expected = (f"{n['name']}, {article} {trait} people, founded{when} "
                        f"around {n['founding_capital']} with "
                        f"{towns} town{'' if towns == 1 else 's'}.")
            self.assertIn(expected, self.narrative)

    def test_no_nation_founded_in_unknown_land(self):
        self.assertNotIn('unknown land', self.narrative)
        self.assertNotIn('with 0 towns', self.narrative)

    def test_survivor_not_credited_with_final_town_count_at_founding(self):
        """The original bug: the founding line read towns off the final snapshot."""
        grown = [n for n in self.state['nations'] if len(n['towns']) > n['founding_towns']]
        self.assertTrue(grown, 'fixture needs a nation that built towns after founding')
        for n in grown:
            self.assertNotIn(
                f"founded around {n['founding_capital']} with {len(n['towns'])} towns",
                self.narrative)

    def test_snapshot_carries_founding_facts(self):
        for n in self.state['nations']:
            self.assertEqual(n['founding_towns'], 1, n['name'])
            self.assertEqual(n['founding_turn'], 0, n['name'])
            self.assertIsInstance(n['founding_capital'], str, n['name'])

    def test_territory_log_is_sampled_not_per_turn(self):
        """Sampled every 10 turns; per-turn cost ~23% of the payload to answer a
        dozen questions. Era boundaries are multiples of 50, so every boundary
        still lands on a sample and the era sentences stay exact."""
        log = self.state['territory_log']
        turns = self.state['turn']
        self.assertEqual([row['turn'] for row in log],
                         list(range(10, turns + 1, 10)))
        for row in log:
            self.assertEqual(set(row), {'turn', 'territory'})
            self.assertEqual(set(row['territory']),
                             {n['name'] for n in self.state['nations']})

    # -- 2. Era "dominant force" -----------------------------------------------

    def _territory_leader(self):
        ranked = sorted(self.alive, key=lambda n: -n['territory'])
        self.assertGreater(ranked[0]['territory'], ranked[1]['territory'], 'fixture needs a clear leader')
        return ranked[0]['name']

    def test_dominant_force_is_the_territorial_leader_alive_at_era_end(self):
        m = re.search(r'Across all fronts, (\w+) proved the dominant force', self.narrative)
        self.assertIsNotNone(m, 'expected a dominant-force sentence for turns 1-100')
        self.assertEqual(m.group(1), self._territory_leader())

    def test_dominant_force_never_names_a_corpse(self):
        for name in self.dead:
            self.assertNotIn(f'{name} proved the dominant force', self.narrative)

    def test_battle_record_credits_the_battle_winner_not_the_territory_leader(self):
        wins = Counter(b['winner'] for b in self.state['battles'])
        top, top_w = wins.most_common(1)[0]
        self.assertIn(f'{top} won the most battles: {top_w}.', self.narrative)

    # -- 3. Death clears diplomacy on both sides -------------------------------

    def test_final_standing_has_no_wars_with_the_dead(self):
        standing = self.narrative[self.narrative.index('FINAL STANDING'):]
        for line in standing.splitlines():
            if 'at war with' in line:
                after = line.split('at war with', 1)[1]
                for name in self.dead:
                    self.assertNotIn(name, after, line)

    def test_json_wars_with_excludes_dead_nations(self):
        dead = set(self.dead)
        for n in self.state['nations']:
            if n['alive']:
                self.assertFalse(set(n['wars_with']) & dead, f"{n['name']} at war with dead: {n['wars_with']}")
                self.assertFalse(set(n['allied_with']) & dead, f"{n['name']} allied with dead: {n['allied_with']}")
            else:
                self.assertEqual(n['wars_with'], [], n['name'])
                self.assertEqual(n['allied_with'], [], n['name'])

    # -- 4. Notable means it mattered ------------------------------------------

    def test_stream_notable_emits_exactly_the_turns_that_mattered(self):
        expected = sorted({e['turn'] for e in self.events if is_notable(e)} | set(self.dead.values()))
        self.assertEqual([line['turn'] for line in self.notable_lines], expected)
        self.assertLess(len(expected), 100)

    def test_stream_notable_keeps_schema(self):
        for line in self.notable_lines:
            self.assertEqual(set(line), {'turn', 'nations', 'battles_this_turn', 'events_this_turn'})

    # -- 5. Grammar ------------------------------------------------------------

    def test_drought_line_pluralises(self):
        self.assertNotIn('nation(s)', self.narrative)
        for text in (self.summary, self.narrative):
            self.assertNotRegex(text, r'\b1 nations\b')
        for e in self.events:
            if e['type'] == 'drought':
                n = e['effects']['nations_affected']
                self.assertIn(f"{n} nation{'' if n == 1 else 's'} lost", e['description'])


class TestNotableFilter(unittest.TestCase):
    """is_notable's branches, without needing a seed that happens to show both.

    This used to run a second simulation on seed 1, chosen because it produced a
    plague that killed and two disasters that touched nothing. Naming rulers
    changed seed 1 too and the zero-effect disasters vanished. Property-selected
    seeds do not survive mechanic changes, so the predicate is tested directly
    and the integration side only asserts that `summary` agrees with it.
    """

    def test_political_events_are_notable_by_type_regardless_of_effects(self):
        self.assertTrue(is_notable({'type': 'assassination', 'effects': {}}))
        self.assertTrue(is_notable({'type': 'rebellion', 'effects': {'tiles_split': 0}}))

    def test_disasters_need_a_non_zero_effect(self):
        self.assertTrue(is_notable({'type': 'plague', 'effects': {'pop_lost': 71, 'armies_weakened': 3}}))
        self.assertTrue(is_notable({'type': 'drought', 'effects': {'food_lost': 40, 'nations_affected': 1}}))
        self.assertFalse(is_notable({'type': 'plague', 'effects': {'pop_lost': 0, 'armies_weakened': 0}}))
        self.assertFalse(is_notable({'type': 'drought', 'effects': {'food_lost': 0, 'nations_affected': 0}}))
        self.assertFalse(is_notable({'type': 'earthquake', 'effects': {}}))

    def test_quiet_event_types_are_never_notable(self):
        for t in ('migration', 'gold_rush', 'flood', 'forest_fire', 'volcanic_ash', 'rich_vein'):
            self.assertFalse(is_notable({'type': t, 'effects': {'tiles': 500}}), t)

    def test_booleans_do_not_count_as_a_non_zero_effect(self):
        self.assertFalse(is_notable({'type': 'plague', 'effects': {'contained': True}}))


if __name__ == '__main__':
    unittest.main()
