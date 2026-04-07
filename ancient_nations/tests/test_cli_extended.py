"""
Ticket B — CLI determinism smoke (twin run).
Ticket C — Bad CLI input errors.
Ticket D — --no-events effect on events in snapshot.

Run from ancient_nations/:
    uv run python -m unittest tests.test_cli_extended
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

CLI = Path(__file__).parent.parent / 'cli.py'
PYTHON = sys.executable


def run_cli(*args):
    """Run cli.py with given args; return (returncode, stdout_text, stderr_text)."""
    result = subprocess.run(
        [PYTHON, str(CLI)] + list(args),
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


# ── Ticket B: determinism ─────────────────────────────────────────────────────

class TestDeterminism(unittest.TestCase):

    def test_twin_run_same_seed_same_output(self):
        """Same seed and turn count must produce byte-for-byte identical stdout."""
        rc1, out1, _ = run_cli('run', '--seed', '1', '--turns', '15')
        rc2, out2, _ = run_cli('run', '--seed', '1', '--turns', '15')
        self.assertEqual(rc1, 0, 'First run failed')
        self.assertEqual(rc2, 0, 'Second run failed')
        self.assertEqual(out1, out2, 'Runs with the same seed produced different output')

    def test_different_seeds_differ(self):
        """Sanity check: different seeds should not be identical (guards test setup)."""
        rc1, out1, _ = run_cli('run', '--seed', '1', '--turns', '15')
        rc2, out2, _ = run_cli('run', '--seed', '2', '--turns', '15')
        self.assertEqual(rc1, 0)
        self.assertEqual(rc2, 0)
        self.assertNotEqual(out1, out2)


# ── Ticket C: bad CLI input errors ───────────────────────────────────────────

class TestBadInput(unittest.TestCase):

    def test_tile_out_of_bounds_exits_nonzero(self):
        """query --tile with out-of-bounds coords must exit non-zero."""
        rc, out, _ = run_cli('query', '--seed', '1', '--turns', '0', '--tile', '99999,0')
        self.assertNotEqual(rc, 0, 'Expected non-zero exit for out-of-bounds tile')

    def test_tile_out_of_bounds_has_error_key(self):
        """query --tile out of bounds must return JSON with an 'error' key."""
        _, out, _ = run_cli('query', '--seed', '1', '--turns', '0', '--tile', '99999,0')
        data = json.loads(out)
        self.assertIn('error', data)
        self.assertIsInstance(data['error'], str)
        self.assertGreater(len(data['error']), 0)

    def test_region_out_of_bounds_exits_nonzero(self):
        """query --region with out-of-bounds coords must exit non-zero."""
        rc, out, _ = run_cli('query', '--seed', '1', '--turns', '0', '--region', '99,99')
        self.assertNotEqual(rc, 0, 'Expected non-zero exit for out-of-bounds region')

    def test_region_out_of_bounds_has_error_key(self):
        """query --region out of bounds must return JSON with an 'error' key."""
        _, out, _ = run_cli('query', '--seed', '1', '--turns', '0', '--region', '99,99')
        data = json.loads(out)
        self.assertIn('error', data)
        self.assertIsInstance(data['error'], str)

    def test_nation_not_found_exits_nonzero(self):
        """query --nation with a prefix that matches nothing must exit non-zero."""
        rc, out, _ = run_cli('query', '--seed', '1', '--turns', '0',
                             '--nation', 'ZZZZZZZZZZZZZZZ')
        self.assertNotEqual(rc, 0, 'Expected non-zero exit for unknown nation')

    def test_nation_not_found_has_error_key(self):
        _, out, _ = run_cli('query', '--seed', '1', '--turns', '0',
                            '--nation', 'ZZZZZZZZZZZZZZZ')
        data = json.loads(out)
        self.assertIn('error', data)


# ── Ticket D: --no-events suppresses world events ────────────────────────────
#
# Seed verification (run locally before committing):
#   seed=2, turns=40, with events:    events_total = N (varies, but >= 1 in practice)
#   seed=2, turns=40, --no-events:    events_total = 0
#
# If seed 2 is ever flaky for the control run, bump turns to 80 first.

class TestNoEvents(unittest.TestCase):

    def test_no_events_flag_suppresses_all_events(self):
        """--no-events must produce events_total == 0 and an empty events list."""
        rc, out, _ = run_cli('run', '--no-events', '--seed', '2', '--turns', '40')
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertEqual(data['events_total'], 0,
            f'Expected 0 events with --no-events, got {data["events_total"]}')
        self.assertEqual(data['events'], [],
            'Expected empty events list with --no-events')

    def test_without_no_events_flag_fires_events(self):
        """Control run (same seed, no flag) should produce at least one world event.

        Seed 2, 40 turns — verified locally to produce events reliably.
        If this becomes flaky, increase --turns before widening the seed pool.
        """
        rc, out, _ = run_cli('run', '--seed', '2', '--turns', '40')
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertGreaterEqual(data['events_total'], 1,
            'Control run (seed 2, 40 turns) produced no events — consider increasing --turns')


if __name__ == '__main__':
    unittest.main()
