"""
main.py – Entry point and input handling for Ancient Nations.

Controls:
  Space        Pause / unpause
  +  /  -      Speed up / slow down turns
  Arrow keys   Move cursor (world/region view)
  Z            Toggle zoom (world ↔ region)
  L            Log view
  C            Charts view
  B            Battles view
  Q  /  Esc    Quit
"""

import sys
import os
import time

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

# Colorama for Windows ANSI support
try:
    import colorama
    colorama.init()
except ImportError:
    pass

# ── Platform input ────────────────────────────────────────────────────────────
if sys.platform == 'win32':
    import msvcrt
    def _kbhit():
        return msvcrt.kbhit()
    def _getch():
        ch = msvcrt.getwch()
        if ch in ('\x00', '\xe0'):   # special key prefix
            ch2 = msvcrt.getwch()
            return {
                'H': 'UP', 'P': 'DOWN', 'K': 'LEFT', 'M': 'RIGHT',
            }.get(ch2, None)
        return ch
else:
    import tty, termios, select
    def _kbhit():
        return select.select([sys.stdin], [], [], 0)[0] != []
    def _getch():
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                if _kbhit():
                    more = sys.stdin.read(2)
                    seq = ch + more
                    return {'\x1b[A':'UP','\x1b[B':'DOWN',
                            '\x1b[C':'RIGHT','\x1b[D':'LEFT'}.get(seq, seq)
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ─────────────────────────────────────────────────────────────────────────────
from constants import *
from engine import GameSession
from renderer import (Renderer, VIEW_WORLD, VIEW_REGION,
                      VIEW_LOG, VIEW_CHARTS, VIEW_BATTLES)


class App:
    SPEED_STEPS = [2.0, 1.0, 0.5, 0.25, 0.1]

    def __init__(self):
        seed = None
        if len(sys.argv) > 1:
            try:
                seed = int(sys.argv[1])
            except ValueError:
                pass

        print('\033[2J\033[H')
        print('\033[97m\033[1m')
        print('  ╔══════════════════════════════════════╗')
        print('  ║       A N C I E N T   N A T I O N S  ║')
        print('  ║       Generating world ...           ║')
        print('  ╚══════════════════════════════════════╝')
        print('\033[0m')
        sys.stdout.flush()

        self.session   = GameSession(seed=seed)
        self.renderer  = Renderer(self.session)
        self.running   = True
        self.speed_idx = 2   # index into SPEED_STEPS
        self.session.speed = self.SPEED_STEPS[self.speed_idx]

    def run(self):
        sys.stdout.write('\033[?25l')   # hide cursor
        sys.stdout.flush()
        try:
            self._loop()
        finally:
            sys.stdout.write('\033[?25h\033[0m\n')
            sys.stdout.flush()
            print('Thanks for watching Ancient Nations!')

    def _loop(self):
        last_turn = time.time()

        while self.running:
            now = time.time()

            # Process input (drain all pending keys)
            while _kbhit():
                ch = _getch()
                self._handle_key(ch)
                if not self.running:
                    break

            # Advance game turn
            s = self.session
            if not s.paused and (now - last_turn >= s.speed):
                s.step()
                last_turn = now

            # Render frame
            self.renderer.render()
            time.sleep(0.03)

    def _handle_key(self, ch):
        if ch is None:
            return
        r       = self.renderer
        g       = self.session.game
        cx, cy  = r.cursor

        if ch in ('q', 'Q', '\x1b'):
            self.running = False

        elif ch in ('r', 'R'):
            r.clear()

        elif ch == ' ':
            self.session.paused = not self.session.paused

        elif ch == '+':
            self.speed_idx        = max(0, self.speed_idx - 1)
            self.session.speed   = self.SPEED_STEPS[self.speed_idx]

        elif ch == '-':
            self.speed_idx        = min(len(self.SPEED_STEPS) - 1, self.speed_idx + 1)
            self.session.speed   = self.SPEED_STEPS[self.speed_idx]

        elif ch in ('z', 'Z'):
            if r.view == VIEW_WORLD:
                r.view = VIEW_REGION
            elif r.view == VIEW_REGION:
                r.view = VIEW_WORLD
            r.clear()

        elif ch in ('l', 'L'):
            if r.view != VIEW_LOG:
                r.view   = VIEW_LOG
                r.scroll = max(0, len(g.logs) - (r.H - 4))
            else:
                r.view = VIEW_WORLD
            r.clear()

        elif ch in ('c', 'C'):
            r.view = VIEW_CHARTS if r.view != VIEW_CHARTS else VIEW_WORLD
            r.clear()

        elif ch in ('b', 'B'):
            r.view = VIEW_BATTLES if r.view != VIEW_BATTLES else VIEW_WORLD
            r.clear()

        elif ch == 'UP':
            if r.view in (VIEW_LOG, VIEW_BATTLES):
                r.scroll = max(0, r.scroll - 1)
            else:
                r.cursor = (cx, max(0, cy - 1))

        elif ch == 'DOWN':
            if r.view in (VIEW_LOG, VIEW_BATTLES):
                r.scroll += 1
            else:
                r.cursor = (cx, min(OUTER_SIZE - 1, cy + 1))

        elif ch == 'LEFT':
            r.cursor = (max(0, cx - 1), cy)

        elif ch == 'RIGHT':
            r.cursor = (min(OUTER_SIZE - 1, cx + 1), cy)


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    App().run()
