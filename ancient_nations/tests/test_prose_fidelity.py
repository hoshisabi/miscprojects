"""
Prose fidelity on seed -521411348 (Rowan's seed, 100 turns).

Vellum specified the intended sentences on 2026-09-16 (Vellum/VELLUM_TO_VESPER.md).
These tests assert those *rules* against the JSON snapshot of the same run, so
they hold on whatever world the seed produces after a sim change, rather than
freezing one world's constants. The six founding lines are hard-coded because
spawn happens before turn 1 and is unaffected by turn logic.

Note (2026-09-16): clearing dead-nation diplomacy changed this seed's history
after t43 — the old world had Solos "allied" to dead Leria and Eldia/Zorara "at
war" with her, which gated real decisions. Rowan's saved JSON is the pre-fix world.

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

    FOUNDING_LINES = [
        "Leria, a militarist people, founded around Roma with 1 town.",
        "Eldia, an expansionist people, founded around Thebaia with 1 town.",
        "Zorara, a zealot people, founded around Perseon with 1 town.",
        "Nerara, a diplomat people, founded around Abydica with 1 town.",
        "Solos, a merchant people, founded around Uticaax with 1 town.",
        "Canius, a builder people, founded around Borysopolis with 1 town.",
    ]

    def test_founding_lines_match_founding_facts(self):
        for line in self.FOUNDING_LINES:
            self.assertIn(line, self.narrative)

    def test_no_nation_founded_in_unknown_land(self):
        self.assertNotIn('unknown land', self.narrative)
        self.assertNotIn('with 0 towns', self.narrative)

    def test_survivor_not_credited_with_final_town_count_at_founding(self):
        eldia = next(n for n in self.state['nations'] if n['name'] == 'Eldia')
        self.assertGreater(len(eldia['towns']), 1, 'fixture assumes Eldia grew past one town')
        self.assertNotIn(f"founded around Thebaia with {len(eldia['towns'])} towns", self.narrative)

    def test_snapshot_carries_founding_facts(self):
        for n in self.state['nations']:
            self.assertEqual(n['founding_towns'], 1, n['name'])
            self.assertEqual(n['founding_turn'], 0, n['name'])
            self.assertIsInstance(n['founding_capital'], str, n['name'])

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
    """Seed 1 / 100 turns has a plague that killed (t16) and disasters that touched
    nothing (t28, t72), so both branches of `is_notable` are exercised by `summary`."""

    @classmethod
    def setUpClass(cls):
        rc, out, err = run_cli('run', '--seed', '1', '--turns', '100')
        assert rc == 0, err
        cls.events = json.loads(out)['events']
        rc, cls.summary, err = run_cli('summary', '--seed', '1', '--turns', '100')
        assert rc == 0, err

    def test_summary_keeps_disasters_with_effect_and_drops_the_rest(self):
        disasters = [e for e in self.events if e['type'] in ('plague', 'drought', 'earthquake')]
        kept    = [e for e in disasters if is_notable(e)]
        dropped = [e for e in disasters if not is_notable(e)]
        self.assertTrue(kept, 'fixture needs a disaster that mattered; pick another seed')
        self.assertTrue(dropped, 'fixture needs a disaster with zero effect; pick another seed')
        for e in kept:
            self.assertIn(f"t{e['turn']:>4}: ", self.summary)
        for e in dropped:
            self.assertNotIn(f"t{e['turn']:>4}: ", self.summary)

    def test_political_events_are_notable_by_type_regardless_of_effects(self):
        self.assertTrue(is_notable({'type': 'assassination', 'effects': {}}))
        self.assertTrue(is_notable({'type': 'rebellion', 'effects': {'tiles_split': 0}}))
        self.assertFalse(is_notable({'type': 'plague', 'effects': {'pop_lost': 0, 'armies_weakened': 0}}))
        self.assertFalse(is_notable({'type': 'migration', 'effects': {'pop_gained': 500}}))


if __name__ == '__main__':
    unittest.main()
