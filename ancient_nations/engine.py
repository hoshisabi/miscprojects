"""
engine.py – Session boundary between simulation and clients.

The Game instance holds authoritative world/nation state and turn law.
Headless CLI and interactive TUI attach here: they must not construct Game
directly if they intend to share the same architectural path.

Playback flags (paused, speed) live on the session — they are not part of
simulation state and are not serialized into turn processing.
"""

from __future__ import annotations

from typing import Any

from constants import NUM_NATIONS, TURN_DELAY
from game import Game
from snapshot import game_summary, turn_summary


class GameSession:
    """Owns one live Game plus optional interactive driver state."""

    def __init__(self, seed=None, num_nations: int = NUM_NATIONS):
        self.game = Game(seed=seed, num_nations=num_nations)
        self.paused = True
        self.speed = TURN_DELAY

    def step(self) -> None:
        """Advance one simulation turn (mutates self.game)."""
        self.game.process_turn()

    def run_turns(self, n: int) -> None:
        for _ in range(n):
            self.step()

    def disable_random_events(self) -> None:
        """Match CLI --no-events: suppress world event firings."""
        for k in self.game.events._cooldowns:
            self.game.events._cooldowns[k] = 999999

    def snapshot(self, log_limit: int = 50) -> dict[str, Any]:
        """JSON-serializable summary of current simulation state (see snapshot.game_summary)."""
        return game_summary(self.game, log_limit=log_limit)

    def turn_snapshot(self) -> dict[str, Any]:
        """Lightweight per-turn dict for streaming (see snapshot.turn_summary)."""
        return turn_summary(self.game)
