"""
Tests for `cli.py run --format narrative` (ISSUES.md narrative Phase 1).

Run from ancient_nations/:
    uv run python -m unittest tests.test_narrative_cli -v
"""

import re
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
        encoding='utf-8',   # cli.py writes UTF-8; Windows would decode as cp1252
    )
    return result.returncode, result.stdout, result.stderr


class TestNarrativeRun(unittest.TestCase):

    def test_narrative_exits_zero_and_nonempty(self):
        rc, out, err = run_cli('run', '--seed', '1', '--turns', '25', '--format', 'narrative')
        self.assertEqual(rc, 0, msg=out + err)
        self.assertEqual(err, '')
        self.assertGreater(len(out.strip()), 200)
        self.assertTrue(out.startswith('ANCIENT NATIONS'), msg=out[:80])
        self.assertIn('Seed 1', out)
        self.assertIn('FINAL STANDING', out)

    def test_narrative_is_not_json(self):
        _, out, _ = run_cli('run', '--seed', '2', '--turns', '10', '--format', 'narrative')
        stripped = out.lstrip()
        self.assertFalse(stripped.startswith('{'), msg='narrative should not be JSON object')

    def test_narrative_twin_run_deterministic(self):
        a1, o1, _ = run_cli('run', '--seed', '7', '--turns', '18', '--format', 'narrative')
        a2, o2, _ = run_cli('run', '--seed', '7', '--turns', '18', '--format', 'narrative')
        self.assertEqual(a1, 0)
        self.assertEqual(a2, 0)
        self.assertEqual(o1, o2)

    def test_trait_article_an_before_vowel_sound(self):
        """Grammar: traits like Expansionist need 'an', not 'a'."""
        _, out, _ = run_cli('run', '--seed', '1', '--turns', '40', '--format', 'narrative')
        self.assertNotRegex(
            out,
            re.compile(r'\ba [aeiou][a-z]* people', re.IGNORECASE),
            msg='Trait line should use "an" before vowel-led trait names',
        )


class TestNarrativeQuery(unittest.TestCase):
    """Ticket F: `query --from T --to U --format narrative`."""

    def test_window_renders_a_chapter(self):
        rc, out, err = run_cli('query', '--seed', '1', '--turns', '30',
                               '--from', '11', '--to', '20', '--format', 'narrative')
        self.assertEqual(rc, 0, msg=out + err)
        self.assertEqual(err, '')
        self.assertIn('A chapter: turns 11–20 of 30.', out)
        self.assertIn('(Turns 11–20)', out)
        self.assertNotIn('FINAL STANDING', out)
        self.assertFalse(out.lstrip().startswith('{'))

    # The errors below exit before the sim runs, so they cost no turns.

    def test_needs_a_window(self):
        rc, out, _ = run_cli('query', '--seed', '1', '--turns', '5000', '--format', 'narrative')
        self.assertNotEqual(rc, 0)
        self.assertIn('needs --from and/or --to', out)

    def test_to_past_turns_is_an_error(self):
        rc, out, _ = run_cli('query', '--seed', '1', '--turns', '50', '--to', '60',
                             '--format', 'narrative')
        self.assertNotEqual(rc, 0)
        self.assertIn('--to 60 is after --turns 50', out)

    def test_from_past_turns_is_an_error(self):
        rc, out, _ = run_cli('query', '--seed', '1', '--turns', '50', '--from', '60',
                             '--format', 'narrative')
        self.assertNotEqual(rc, 0)
        self.assertIn('is empty', out)

    def test_selector_with_narrative_is_an_error(self):
        rc, out, _ = run_cli('query', '--seed', '1', '--turns', '5000', '--events',
                             '--from', '10', '--format', 'narrative')
        self.assertNotEqual(rc, 0)
        self.assertIn('only applies to the default query', out)


if __name__ == '__main__':
    unittest.main()
