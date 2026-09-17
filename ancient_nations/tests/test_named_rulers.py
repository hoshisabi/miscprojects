"""
Named rulers — the name is the stable handle a chronicle can refer to.

Wren asked for "Romanus's leader Caldarius was killed at turn 578" instead of
"Romanus's leader was killed". Rowan supplied the reason it matters: epithets
come off leader_aggression, which is rolled independently of trait, so a runaway
Expansionist can be ruled by "the Pacifist". An epithet that contradicts the map
is a bad primary key. A name is a good one.

Where a test needs a run that contains a particular kind of event, it *searches*
seeds deterministically from 1 rather than pinning one. Pinned property-seeds do
not survive mechanic changes — this suite has lost two to exactly that.

Run from ancient_nations/:
    uv run python -m unittest tests.test_named_rulers -v
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import narrative  # noqa: E402
from engine import GameSession  # noqa: E402


def run(seed, turns):
    s = GameSession(seed=seed)
    s.run_turns(turns)
    return s.game


def find_game_with(predicate, turns=150, max_seeds=8):
    """First game from seed 1 upward satisfying predicate. Deterministic."""
    for seed in range(1, max_seeds + 1):
        g = run(seed, turns)
        if predicate(g):
            return g
    raise AssertionError(
        f'no game in seeds 1..{max_seeds} over {turns} turns matched; '
        'widen the search or check the mechanic still fires')


class TestRulerNames(unittest.TestCase):

    def test_every_nation_starts_with_a_ruler(self):
        g = run(7, 0)
        for n in g.nations:
            self.assertTrue(n.leader_name, n.name)
            self.assertIsInstance(n.leader_name, str)

    def test_rulers_are_distinct_from_each_other(self):
        g = run(7, 0)
        names = [n.leader_name for n in g.nations]
        self.assertEqual(len(names), len(set(names)))

    def test_no_ruler_is_a_namesake_of_any_nation(self):
        """Shared registry with nation names: "Eldia's ruler Eldia" must be impossible."""
        g = run(7, 200)
        nation_names = {n.name for n in g.nations}
        for n in g.nations:
            self.assertNotIn(n.leader_name, nation_names, f'{n.name} ruled by its own namesake')

    def test_a_name_is_never_reused_across_a_long_run(self):
        """Successions and revivals draw from the same registry, so a chronicle
        never has two different people answering to one name."""
        g = find_game_with(lambda g: any(n.slot_revivals for n in g.nations),
                           turns=500, max_seeds=4)
        seen = g._namegen._used_names
        self.assertEqual(len(seen), len(set(seen)))
        for n in g.nations:
            self.assertIn(n.leader_name, seen)

    def test_title_is_name_plus_epithet(self):
        g = run(7, 0)
        n = g.nations[0]
        self.assertEqual(n.leader_title(), f'{n.leader_name} {n.leader_epithet()}')


class TestSuccession(unittest.TestCase):

    def test_new_leader_installs_a_new_name(self):
        g = run(7, 0)
        n = g.nations[0]
        before = n.leader_name
        n.new_leader()
        self.assertNotEqual(n.leader_name, before)

    def test_crisis_succession_also_renames(self):
        g = run(7, 0)
        n = g.nations[0]
        before = n.leader_name
        n.new_leader(crisis=True)
        self.assertNotEqual(n.leader_name, before)

    def test_a_revived_slot_gets_its_own_ruler(self):
        """A rebel state is a new polity; it must not inherit the dead slot's ruler.

        Driven directly rather than waiting for a civil war to fire and survive:
        spawn_rebel_nation returns None unless a dead slot exists, so the slot is
        freed by hand, the way test_trait_uniqueness does it.
        """
        g = run(7, 60)
        victim = g.nations[0]
        victim.alive = False
        g._clear_diplomacy(victim)
        stale_ruler = victim.leader_name

        parent = max((n for n in g.nations if n.alive), key=lambda n: len(n.tiles))
        rebel = g.spawn_rebel_nation(61, parent)

        self.assertIsNotNone(rebel, 'parent had too little territory to fracture')
        self.assertIs(rebel, victim, 'the freed slot should have been reused')
        self.assertTrue(rebel.leader_name)
        self.assertNotEqual(rebel.leader_name, stale_ruler)


class TestAssassinationNamesTheRuler(unittest.TestCase):
    """Wren's actual ask."""

    @classmethod
    def setUpClass(cls):
        cls.game = find_game_with(
            lambda g: any(e.type == 'assassination' for e in g.events_history))
        cls.events = [e for e in cls.game.events_history if e.type == 'assassination']

    def test_effects_carry_both_rulers(self):
        for e in self.events:
            self.assertIn('ruler_killed', e.effects)
            self.assertIn('ruler_successor', e.effects)
            self.assertTrue(e.effects['ruler_killed'])
            self.assertNotEqual(e.effects['ruler_killed'], e.effects['ruler_successor'])

    def test_description_names_the_dead_ruler_not_only_the_epithet(self):
        for e in self.events:
            self.assertIn(e.effects['ruler_killed'], e.description)
            self.assertNotIn("'s leader the ", e.description)


class TestRulerInProse(unittest.TestCase):
    """Rendering, tested on synthetic state so it costs nothing."""

    from tests.test_narrative_render import event, nation, state  # noqa: E402
    event, nation, state = staticmethod(event), staticmethod(nation), staticmethod(state)

    def test_assassination_line_names_the_ruler(self):
        out = narrative.render(self.state(
            [self.nation('Aegia', 'Militarist'), self.nation('Borum', 'Builder')],
            events=[self.event('assassination', nation='Aegia', ruler_killed='Caldarius',
                               ruler_successor='Tarar', new_trait='Expansionist',
                               trait_changed=True)]))
        self.assertIn('ended the reign of Caldarius of Aegia', out)

    def test_falls_back_when_an_older_event_has_no_ruler_name(self):
        """Chronicles rendered from pre-2026-09-17 JSON must still render."""
        out = narrative.render(self.state(
            [self.nation('Aegia', 'Militarist'), self.nation('Borum', 'Builder')],
            events=[self.event('assassination', nation='Aegia', trait_changed=False)]))
        self.assertIn("ended the reign of Aegia's leader", out)


if __name__ == '__main__':
    unittest.main()
