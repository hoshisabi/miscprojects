"""
Tests for cli.py chronicle fidelity: --log-limit and honest stream rows.

Run from ancient_nations/:
    uv run python -m unittest tests.test_cli_chronicle

Or from the repo root:
    uv run python -m unittest discover -s ancient_nations/tests
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

CLI = Path(__file__).parent.parent / 'cli.py'
PYTHON = sys.executable  # the uv-managed interpreter running these tests


def run_cli(*args):
    """Run cli.py with given args; return (returncode, stdout_text)."""
    result = subprocess.run(
        [PYTHON, str(CLI)] + list(args),
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout


# ── Part A: --log-limit ───────────────────────────────────────────────────────

class TestLogLimit(unittest.TestCase):

    def test_default_log_limit(self):
        """run without --log-limit should return at most 50 log entries."""
        rc, out = run_cli('run', '--seed', '1', '--turns', '20')
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertIn('logs', data)
        self.assertLessEqual(len(data['logs']), 50)

    def test_explicit_log_limit(self):
        """--log-limit 3 should return at most 3 log entries."""
        rc, out = run_cli('run', '--seed', '1', '--turns', '5', '--log-limit', '3')
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertLessEqual(len(data['logs']), 3)

    def test_log_limit_200(self):
        """--log-limit 200 should exit 0 and return at most 200 entries."""
        rc, out = run_cli('run', '--seed', '1', '--turns', '5', '--log-limit', '200')
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertLessEqual(len(data['logs']), 200)

    def test_log_limit_clamp_to_one(self):
        """--log-limit 0 should be clamped to 1 (not crash, not return empty)."""
        rc, out = run_cli('run', '--seed', '1', '--turns', '5', '--log-limit', '0')
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertGreaterEqual(len(data['logs']), 1)

    def test_log_limit_large(self):
        """--log-limit larger than available logs returns what exists without error."""
        rc, out = run_cli('run', '--seed', '1', '--turns', '5', '--log-limit', '9999')
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertIn('logs', data)


# ── Part B: honest stream rows ────────────────────────────────────────────────

class TestStreamDeadNations(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Run a long enough sim to get at least one elimination; parse all lines."""
        rc, out = run_cli('stream', '--seed', '123', '--turns', '500')
        assert rc == 0, f'stream failed: {out[:200]}'
        cls.lines = [json.loads(line) for line in out.strip().splitlines()]

    def test_stream_produces_output(self):
        self.assertGreater(len(self.lines), 0)

    def test_every_row_has_alive_field(self):
        for line in self.lines:
            for nation in line['nations']:
                self.assertIn('alive', nation, msg=f"Missing 'alive' on {nation.get('name')} turn {line['turn']}")

    def test_dead_nations_have_zeroed_stats(self):
        """Once alive=false, territory/armies/gold must be 0."""
        for line in self.lines:
            for nation in line['nations']:
                if not nation['alive']:
                    self.assertEqual(nation['territory'], 0,
                        msg=f"{nation['name']} dead at turn {line['turn']} but territory={nation['territory']}")
                    self.assertEqual(nation['armies'], 0,
                        msg=f"{nation['name']} dead at turn {line['turn']} but armies={nation['armies']}")
                    self.assertEqual(nation['gold'], 0,
                        msg=f"{nation['name']} dead at turn {line['turn']} but gold={nation['gold']}")

    def test_dead_nations_have_death_turn(self):
        """Dead nation rows must include death_turn as an integer."""
        found_dead = False
        for line in self.lines:
            for nation in line['nations']:
                if not nation['alive']:
                    found_dead = True
                    self.assertIn('death_turn', nation,
                        msg=f"Dead nation {nation['name']} missing death_turn at turn {line['turn']}")
                    self.assertIsInstance(nation['death_turn'], int,
                        msg=f"death_turn should be int, got {type(nation['death_turn'])}")
        # Sanity: we expect at least one death in 500 turns
        self.assertTrue(found_dead, "No eliminations in 500 turns — test may need a longer run")

    def test_alive_nations_territory_nonzero(self):
        """Alive nations should generally have territory > 0."""
        for line in self.lines[:10]:  # early turns, all alive
            for nation in line['nations']:
                if nation['alive']:
                    self.assertGreater(nation['territory'], 0,
                        msg=f"Alive nation {nation['name']} has 0 territory at turn {line['turn']}")


if __name__ == '__main__':
    unittest.main()
