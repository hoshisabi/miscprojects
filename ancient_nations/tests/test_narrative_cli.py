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


if __name__ == '__main__':
    unittest.main()
