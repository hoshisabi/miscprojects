"""
renderer.py – Full ASCII renderer.

Views:
  WORLD  – zoomed-out 10x10 outer-grid overview
  REGION – zoomed-in 10x10 inner tiles for one outer cell
  LOG    – full scrollable log
  CHARTS – ASCII line charts of nation stats
  BATTLES – battle history list
"""
import sys
import os
import math
from constants import *

try:
    import colorama
    colorama.init()
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False

# -- ANSI helpers --------------------------------------------------------------
CLR   = '\033[2J\033[H'   # clear + home
HOME  = '\033[H'
HIDE  = '\033[?25l'       # hide cursor
SHOW  = '\033[?25h'

def move(row, col):
    return f'\033[{row+1};{col+1}H'

NEUTRAL_COLOR = '\033[37m'        # grey for neutral land

# -----------------------------------------------------------------------------
VIEW_WORLD   = 'world'
VIEW_REGION  = 'region'
VIEW_LOG     = 'log'
VIEW_CHARTS  = 'charts'
VIEW_BATTLES = 'battles'


class Renderer:
    def __init__(self, session):
        """`session` is a GameSession (owns .game and playback flags)."""
        self.session = session

    @property
    def game(self):
        return self.session.game
        self.view      = VIEW_WORLD
        self.cursor    = (5, 5)      # outer-grid cursor (ox, oy)
        self.scroll    = 0           # log scroll offset
        self.chart_res = RES_GOLD    # which resource to chart
        # Terminal size
        self.W = WINDOW_WIDTH
        self.H = WINDOW_HEIGHT
        # Screen buffer: list of strings (one per row)
        self._buf         = []
        self._frame       = 0
        self._force_clear = True   # full clear on first frame and after view changes

    # -- public entry ------------------------------------------------------
    def render(self):
        self._frame += 1
        self._buf = []
        if self.view == VIEW_WORLD:
            self._render_world()
        elif self.view == VIEW_REGION:
            self._render_region()
        elif self.view == VIEW_LOG:
            self._render_log()
        elif self.view == VIEW_CHARTS:
            self._render_charts()
        elif self.view == VIEW_BATTLES:
            self._render_battles()
        self._flush()

    # -- screen buffer ops -------------------------------------------------
    def _emit(self, line):
        self._buf.append(line)

    def clear(self):
        """Force a full terminal clear on the next render."""
        self._force_clear = True

    def _flush(self):
        if self._force_clear:
            output = '\033[2J\033[H'   # erase entire screen + home
            self._force_clear = False
        else:
            output = HOME
        for line in self._buf:
            output += line + RESET + '\n'
        sys.stdout.write(output)
        sys.stdout.flush()

    def _pad(self, s, width):
        """Pad/truncate a raw string (without ANSI codes) to exact width."""
        visible = self._visible_len(s)
        if visible < width:
            return s + ' ' * (width - visible)
        # Truncate (complex due to ANSI codes — just truncate raw chars)
        return s[:width + (len(s)-visible)]

    def _visible_len(self, s):
        """Length ignoring ANSI escape sequences."""
        import re
        return len(re.sub(r'\033\[[0-9;]*m', '', s))

    def _hline(self, char='-', width=None):
        return char * (width or self.W)

    # -- Frame borders (plain ASCII) ----------------------------------------
    def _crt_frame_top(self, title=''):
        w     = self.W
        inner = w - 2
        title_str = f'[ {title} ]'
        pad_l = (inner - len(title_str)) // 2
        pad_r = inner - len(title_str) - pad_l
        return f'\033[90m+{"-"*pad_l}\033[97m{title_str}\033[90m{"-"*pad_r}+\033[0m'

    def _crt_frame_bot(self, hint=''):
        w     = self.W
        inner = w - 2
        hint_str = f'[ {hint} ]' if hint else ''
        pad_l = (inner - len(hint_str)) // 2
        pad_r = inner - len(hint_str) - pad_l
        return f'\033[90m+{"-"*pad_l}\033[97m{hint_str}\033[90m{"-"*pad_r}+\033[0m'

    def _crt_row(self, content):
        inner  = self.W - 2
        padded = self._pad(content, inner)
        return f'\033[90m|\033[0m{padded}\033[90m|\033[0m'

    # -- WORLD VIEW --------------------------------------------------------
    def _render_world(self):
        g = self.game
        w = self.world = g.world
        turn_str = f'ANCIENT NATIONS  Turn {g.turn:>5d}'
        s = self.session
        pause_str = '  [PAUSED]' if s.paused else f'  speed:{s.speed:.1f}s'
        self._emit(self._crt_frame_top(turn_str + pause_str))

        MAP_W = OUTER_SIZE * 4   # 4 chars per outer cell (wide display)
        MAP_H = OUTER_SIZE * 2   # 2 rows per outer cell
        PANEL_W = self.W - MAP_W - 4

        # Build map lines and side panel simultaneously
        map_lines = self._build_world_map(MAP_W, MAP_H)
        panel_lines = self._build_nation_panel(PANEL_W, MAP_H)

        # Merge side by side
        for i in range(max(len(map_lines), len(panel_lines))):
            ml = map_lines[i]  if i < len(map_lines)  else ' '*MAP_W
            pl = panel_lines[i] if i < len(panel_lines) else ' '*PANEL_W
            combined = f'\033[90m|\033[0m{ml} \033[90m|\033[0m{pl}\033[90m|\033[0m'
            self._emit(combined)

        # Log strip below map
        log_lines = self._build_log_strip(self.W-2, 8)
        self._emit(self._crt_row(f'\033[90m{"-"*(self.W-2)}\033[0m'))
        for ll in log_lines:
            self._emit(self._crt_row(ll))

        keys = '[Space]Pause  [+/-]Speed  [Z]Zoom  [L]Log  [C]Charts  [B]Battles  [R]Refresh  [Q]Quit  [<>^v]Move'
        self._emit(self._crt_frame_bot(keys))

    def _build_world_map(self, target_w, target_h):
        """
        Render outer 10×10 grid. Each outer cell = 4 chars wide × 2 rows tall.
        Row 0: top-left dominant char × 2, top-right × 2
        Row 1: bot-left dominant char × 2, bot-right × 2
        """
        w = self.game.world
        lines = []
        cx, cy = self.cursor

        for oy in range(OUTER_SIZE):
            row0 = ''
            row1 = ''
            for ox in range(OUTER_SIZE):
                # Sample 4 representative inner tiles: corners
                tl = self._outer_cell_char(w, ox, oy, 2, 2)
                tr = self._outer_cell_char(w, ox, oy, 7, 2)
                bl = self._outer_cell_char(w, ox, oy, 2, 7)
                br = self._outer_cell_char(w, ox, oy, 7, 7)

                # Cursor highlight
                if ox == cx and oy == cy:
                    hl = '\033[7m'
                    row0 += hl + tl + tr + RESET
                    row1 += hl + bl + br + RESET
                else:
                    row0 += tl + tr
                    row1 += bl + br

            lines.append(row0)
            lines.append(row1)

        return lines

    def _outer_cell_char(self, world, ox, oy, ix, iy):
        """Get display char for a single inner tile within an outer cell."""
        x = ox * INNER_SIZE + ix
        y = oy * INNER_SIZE + iy
        if not world.in_bounds(x, y):
            return ' '
        t = world.t(x, y)
        return t.display_char(show_owner=True)

    def _build_nation_panel(self, width, height):
        lines = []
        header = f'\033[97m{BOLD}{"NATIONS":^{width}}{RESET}'
        lines.append(header)
        lines.append('\033[90m' + '-'*width + RESET)

        for n in self.game.nations:
            if not n.alive:
                lines.append(f'\033[90m  {n.letter} {n.name:12s} [GONE]{RESET}')
                continue
            col    = n.color
            terr   = len(n.tiles)
            armies = n.total_armies()
            gold   = int(n.res[RES_GOLD])

            wars   = [self.game.nations[i].letter for i in range(len(self.game.nations))
                      if i != n.idx and n.at_war_with(i)]
            allys  = [self.game.nations[i].letter for i in range(len(self.game.nations))
                      if i != n.idx and n.allied_with(i)]

            dip_parts = []
            if wars:  dip_parts.append('\033[91mW:' + ','.join(wars) + RESET)
            if allys: dip_parts.append('\033[92mA:' + ','.join(allys) + RESET)
            if not dip_parts: dip_parts.append('\033[90m~\033[0m')
            dip_str = ' '.join(dip_parts)

            trait_name = n.trait['name'] if n.trait else '?'
            line = (f'{col}{BOLD}{n.letter}{RESET} {col}{n.name:<11s}{RESET} '
                    f'T:{terr:3d} M:{armies:2d} G:{gold:4d} '
                    f'\033[90m[{trait_name[:4]}]\033[0m {dip_str}')
            lines.append(self._pad(line, width))

        # Resource values legend
        lines.append('')
        lines.append('\033[90m-- Resource Values --\033[0m')
        rv = self.game.world.resource_values
        for r in range(NUM_RESOURCES):
            bar_len = min(int(rv[r]*5), 15)
            bar = '#'*bar_len
            lines.append(f'  \033[97m{RESOURCE_NAMES[r]:<6s}\033[0m '
                         f'\033[93m{bar:<15s}\033[0m x{rv[r]:.1f}')

        # Pad to height
        while len(lines) < height:
            lines.append('')

        return lines

    def _build_log_strip(self, width, n_lines):
        logs = self.game.recent_logs(n_lines)
        lines = []
        for (turn, msg, nidx) in logs:
            col = NATION_COLORS[nidx] if 0 <= nidx < len(NATION_COLORS) else '\033[37m'
            prefix = f'\033[90mT{turn:>5d}\033[0m '
            entry  = prefix + col + msg + RESET
            lines.append(self._pad(entry, width))
        return lines[-n_lines:]

    # -- REGION VIEW -------------------------------------------------------
    def _render_region(self):
        cx, cy = self.cursor
        title  = f'REGION ({cx},{cy})  [Z] back to world'
        self._emit(self._crt_frame_top(title))

        w      = self.game.world
        TILE_W = 3   # chars per tile
        MAP_W  = INNER_SIZE * TILE_W
        PAD    = self.W - MAP_W - 3

        legend = ['  LEGEND:',
                  f'  {TERRAIN_COLORS[TERRAIN_OCEAN]}~{RESET} Ocean',
                  f'  {TERRAIN_COLORS[TERRAIN_MOUNTAIN]}^{RESET} Mountain',
                  f'  {TERRAIN_COLORS[TERRAIN_RIVER]}~{RESET} River',
                  f'  {TERRAIN_COLORS[TERRAIN_FOREST]}T{RESET} Forest',
                  f'  {TERRAIN_COLORS[TERRAIN_PLAIN]}.{RESET} Plain',
                  f'  {TERRAIN_COLORS[TERRAIN_DESERT]}_{RESET} Desert',
                  '  f Farm  m Mine',
                  '  # Castle  t Town',
                  '  T Big Town  @ City',
                  '  A Army  + Road',
                  '',
                  '  Resources:',
                  f'  \033[93mG\033[0m Gold  \033[32mF\033[0m Food',
                  f'  \033[37mM\033[0m Metal \033[32mW\033[0m Wood',
                  ]

        for iy in range(INNER_SIZE):
            row = ''
            for ix in range(INNER_SIZE):
                x = cx * INNER_SIZE + ix
                y = cy * INNER_SIZE + iy
                if not w.in_bounds(x, y):
                    row += '   '
                    continue
                t = w.t(x, y)
                ch = t.display_char(show_owner=True)
                # deposit indicator
                max_dep = max(t.deposits.values())
                if max_dep > 0:
                    dep_r = max(t.deposits, key=t.deposits.get)
                    dep_col = ['\033[32m','\033[32m','\033[37m','\033[93m'][dep_r]
                    ind = dep_col + RESOURCE_SYMBOLS[dep_r] + RESET
                else:
                    ind = ' '
                row += ch + ind + ' '

            leg = legend[iy] if iy < len(legend) else ''
            full_line = '\033[90m|\033[0m' + row + self._pad(leg, PAD) + '\033[90m|\033[0m'
            self._emit(full_line)

        # Tile detail under cursor (show center tile info)
        mid_x = cx*INNER_SIZE + INNER_SIZE//2
        mid_y = cy*INNER_SIZE + INNER_SIZE//2
        detail = self.game.tile_info(mid_x, mid_y)
        self._emit(self._crt_row('\033[90m' + '-'*(self.W-2) + '\033[0m'))
        for d in detail:
            self._emit(self._crt_row('\033[97m  ' + d + RESET))

        # Fill remaining rows
        content_rows = INNER_SIZE + 1 + len(detail)
        remaining    = self.H - content_rows - 4
        for _ in range(max(0, remaining)):
            self._emit(self._crt_row(''))

        self._emit(self._crt_frame_bot('[Z]World  [<>^v]Navigate  [Q]Quit'))

    # -- LOG VIEW ----------------------------------------------------------
    def _render_log(self):
        self._emit(self._crt_frame_top('GAME LOG'))
        visible = self.H - 4
        logs = self.game.logs
        total = len(logs)
        scroll = max(0, min(self.scroll, total - visible))
        self.scroll = scroll
        shown = logs[scroll:scroll+visible]
        for (turn, msg, nidx) in shown:
            col = NATION_COLORS[nidx] if 0<=nidx<len(NATION_COLORS) else '\033[37m'
            prefix = f'\033[90mT{turn:>5d}\033[0m '
            line   = prefix + col + msg + RESET
            self._emit(self._crt_row(self._pad(line, self.W-2)))
        for _ in range(visible - len(shown)):
            self._emit(self._crt_row(''))
        self._emit(self._crt_frame_bot(
            f'[^v]Scroll ({scroll+1}-{scroll+len(shown)}/{total})  [L]Close'))

    # -- CHARTS VIEW -------------------------------------------------------
    def _render_charts(self):
        self._emit(self._crt_frame_top('CHARTS'))
        available = self.H - 5          # rows between top+bottom frames
        chart_h   = max(5, (available - 2) // 4)  # 4 charts stacked
        chart_w   = self.W - 4

        metrics = [
            ('territory',    'Territory'),
            ('population',   'Population'),
            ('army_strength','Mil.Strength'),
            ('gold',         'Gold'),
        ]

        rows_used = 0
        for key, label in metrics:
            if rows_used >= available - 2:
                break
            lines = self._ascii_chart(key, label, chart_w, chart_h)
            for l in lines[:chart_h+2]:
                self._emit(self._crt_row(l))
                rows_used += 1

        # Colour legend
        leg = '  ' + '  '.join(
            f'{n.color}{BOLD}{n.letter}{RESET}:{n.name[:6]}'
            for n in self.game.nations if n.alive)
        self._emit(self._crt_row(leg))
        rows_used += 1

        # Pad remaining
        for _ in range(max(0, available - rows_used)):
            self._emit(self._crt_row(''))

        self._emit(self._crt_frame_bot('[C]Close'))

    def _ascii_chart(self, key, label, width, height):
        nations  = [n for n in self.game.nations if n.alive]
        # Gather series
        series   = [(n, n.history.get(key, [])) for n in nations]
        if not any(s for _,s in series):
            return [f'  {label}: no data']

        all_vals = [v for _,s in series for v in s]
        if not all_vals:
            return [f'  {label}: no data']

        max_v    = max(all_vals) or 1
        min_v    = min(all_vals)
        rng      = max_v - min_v or 1

        plot_w   = width - 8
        plot_h   = height - 2
        if plot_w < 4 or plot_h < 2:
            return [f'  {label}: terminal too small']

        canvas   = [[' ']*plot_w for _ in range(plot_h)]

        for n, s in series:
            if not s: continue
            col   = n.color
            # Resample to plot_w points
            pts   = []
            for i in range(plot_w):
                idx = int(i / plot_w * len(s))
                pts.append(s[min(idx, len(s)-1)])
            for i, v in enumerate(pts):
                row = int((1 - (v - min_v) / rng) * (plot_h-1))
                row = max(0, min(plot_h-1, row))
                canvas[row][i] = (col, n.letter)

        lines = [f'  \033[97m{label}\033[0m  max:{int(max_v)}']
        for row in canvas:
            line = '  \033[90m|\033[0m'
            for cell in row:
                if isinstance(cell, tuple):
                    col, ch = cell
                    line += col + ch + RESET
                else:
                    line += cell
            lines.append(line)
        lines.append('  \033[90m+' + '-'*plot_w + '\033[0m')
        return lines

    # -- BATTLES VIEW ------------------------------------------------------
    def _render_battles(self):
        self._emit(self._crt_frame_top(
            f'BATTLE LOG  ({len(self.game.battles)} battles)'))
        header = (f'  {"Turn":>5s}  {"Attacker":12s}  {"Defender":12s}  '
                  f'{"Winner":12s}  {"Losses A/D":10s}  Notes')
        self._emit(self._crt_row('\033[97m' + header + RESET))
        self._emit(self._crt_row('\033[90m' + '-'*(self.W-2) + RESET))

        visible  = self.H - 7
        battles  = self.game.battles[-visible:]
        for b in reversed(battles):
            an   = self.game.nations[b.atk_nation]
            dn   = self.game.nations[b.def_nation] if b.def_nation>=0 else None
            wn   = self.game.nations[b.winner] if b.winner>=0 else None
            acol = an.color
            dcol = dn.color if dn else '\033[37m'
            wcol = wn.color if wn else '\033[37m'
            dn_s = dn.name if dn else 'Neutral'
            wn_s = wn.name if wn else 'Neutral'
            line = (f'  T{b.turn:>5d}  '
                    f'{acol}{an.name:12s}{RESET}  '
                    f'{dcol}{dn_s:12s}{RESET}  '
                    f'{wcol}{wn_s:12s}{RESET}  '
                    f'{b.atk_losses:4d}/{b.def_losses:<4d}   '
                    f'\033[90m{b.notes}\033[0m')
            self._emit(self._crt_row(line))

        remaining = visible - len(battles)
        for _ in range(max(0, remaining)):
            self._emit(self._crt_row(''))

        self._emit(self._crt_frame_bot('[B]Close  [^v]Scroll'))
