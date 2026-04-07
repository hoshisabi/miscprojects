"""
Ticket E — Schema stability for stream NDJSON.

Every line emitted by `cli.py stream` must be valid JSON with a stable key set
per line type so downstream tools don't break silently.

Schema decisions (documented here so reviewers can push back):
  - Top-level keys: exactly {turn, nations, battles_this_turn, events_this_turn}
  - Nation (alive): exactly {name, trait, trait_id, slot_revivals, territory, armies, gold, alive}
  - Nation (dead):  same + {death_turn, absorbed_by} — MISSING on alive rows, not null.
    Consumers must use nation.get('death_turn') or check alive first.
    Rationale: missing vs null is a meaningful distinction for schema-aware tools.
  - battles_this_turn and events_this_turn are always lists (empty or non-empty).
  - No schema_version field added yet — if the schema changes, add one then.

Run from ancient_nations/:
    uv run python -m unittest tests.test_stream_schema
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

CLI = Path(__file__).parent.parent / 'cli.py'
PYTHON = sys.executable


def run_cli(*args):
    result = subprocess.run(
        [PYTHON, str(CLI)] + list(args),
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


# Keys that must always be present on every stream line.
TOP_KEYS = frozenset({'turn', 'nations', 'battles_this_turn', 'events_this_turn'})

# Keys that must be present on every nation row (alive or dead).
NATION_BASE_KEYS = frozenset({
    'name', 'trait', 'trait_id', 'slot_revivals',
    'territory', 'armies', 'gold', 'alive',
})

# Additional keys that appear only on dead nation rows (not null — absent on alive rows).
NATION_DEAD_EXTRA = frozenset({'death_turn', 'absorbed_by'})

NATION_ALIVE_KEYS = NATION_BASE_KEYS
NATION_DEAD_KEYS  = NATION_BASE_KEYS | NATION_DEAD_EXTRA


class TestStreamSchema(unittest.TestCase):
    """
    Two fixtures:
      alive_lines  — seed=1, 25 turns, --no-events; all nations alive, no variance.
      mixed_lines  — seed=123, 500 turns; includes dead nations and battles.

    Seed 123, 500 turns matches test_cli_chronicle; consistent choice avoids
    maintaining two separate "long enough" seeds.
    """

    @classmethod
    def setUpClass(cls):
        rc1, out1, _ = run_cli('stream', '--seed', '1', '--turns', '25', '--no-events')
        assert rc1 == 0, f'stream (alive fixture) exited {rc1}'
        cls.alive_lines = [json.loads(line) for line in out1.strip().splitlines()]

        rc2, out2, _ = run_cli('stream', '--seed', '123', '--turns', '500')
        assert rc2 == 0, f'stream (mixed fixture) exited {rc2}'
        cls.mixed_lines = [json.loads(line) for line in out2.strip().splitlines()]

    # ── top-level keys ────────────────────────────────────────────────────────

    def test_top_level_keys_alive_fixture(self):
        """Every line in the short alive-only run has exactly the expected top-level keys."""
        for line in self.alive_lines:
            self.assertEqual(
                set(line.keys()), TOP_KEYS,
                msg=f'Turn {line.get("turn")}: top-level key mismatch',
            )

    def test_top_level_keys_mixed_fixture(self):
        """Every line in the long mixed run also has exactly the expected top-level keys."""
        for line in self.mixed_lines:
            self.assertEqual(
                set(line.keys()), TOP_KEYS,
                msg=f'Turn {line.get("turn")}: top-level key mismatch',
            )

    # ── alive nation keys ─────────────────────────────────────────────────────

    def test_alive_nation_keys_exact(self):
        """Alive nation rows must have exactly the base key set — no extras, no missing."""
        for line in self.alive_lines + self.mixed_lines:
            for nation in line['nations']:
                if nation['alive']:
                    self.assertEqual(
                        set(nation.keys()), NATION_ALIVE_KEYS,
                        msg=f'Alive nation {nation.get("name")} at turn {line["turn"]}: key mismatch',
                    )

    def test_dead_nation_rows_absent_on_alive(self):
        """death_turn and absorbed_by must be absent (not null) on alive rows."""
        for line in self.alive_lines:
            for nation in line['nations']:
                if nation['alive']:
                    self.assertNotIn('death_turn',  nation,
                        msg=f'{nation["name"]} alive but has death_turn at turn {line["turn"]}')
                    self.assertNotIn('absorbed_by', nation,
                        msg=f'{nation["name"]} alive but has absorbed_by at turn {line["turn"]}')

    # ── dead nation keys ──────────────────────────────────────────────────────

    def test_dead_nation_keys_exact(self):
        """Dead nation rows must have base keys + {death_turn, absorbed_by} — no more, no less."""
        found_dead = False
        for line in self.mixed_lines:
            for nation in line['nations']:
                if not nation['alive']:
                    found_dead = True
                    self.assertEqual(
                        set(nation.keys()), NATION_DEAD_KEYS,
                        msg=f'Dead nation {nation.get("name")} at turn {line["turn"]}: key mismatch',
                    )
        self.assertTrue(found_dead,
            'No dead nations in 500-turn mixed run — increase --turns or change seed')

    def test_dead_nation_death_turn_is_int(self):
        for line in self.mixed_lines:
            for nation in line['nations']:
                if not nation['alive']:
                    self.assertIsInstance(nation['death_turn'], int,
                        msg=f'{nation["name"]} death_turn should be int at turn {line["turn"]}')

    # ── structural types ──────────────────────────────────────────────────────

    def test_battles_this_turn_is_always_list(self):
        for line in self.alive_lines + self.mixed_lines:
            self.assertIsInstance(line['battles_this_turn'], list,
                msg=f'Turn {line["turn"]}: battles_this_turn is not a list')

    def test_events_this_turn_is_always_list(self):
        for line in self.alive_lines + self.mixed_lines:
            self.assertIsInstance(line['events_this_turn'], list,
                msg=f'Turn {line["turn"]}: events_this_turn is not a list')

    def test_turn_is_int_and_monotone(self):
        """turn field must be a positive int and increment by 1 each line."""
        for lines in (self.alive_lines, self.mixed_lines):
            for i, line in enumerate(lines):
                self.assertIsInstance(line['turn'], int)
                self.assertEqual(line['turn'], i + 1,
                    msg=f'Expected turn {i+1}, got {line["turn"]}')


if __name__ == '__main__':
    unittest.main()
