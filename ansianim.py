#!/usr/bin/env python3
"""
Animated Ocean Sunset Scene with ANSI Colors
Press Ctrl+C to exit
"""
import time
import sys
import random

class Colors:
    """ANSI color codes"""
    RESET       = '\033[0m'
    HIDE_CURSOR = '\033[?25l'
    SHOW_CURSOR = '\033[?25h'
    HOME        = '\033[H'
    CLEAR       = '\033[2J'

    # Sunset colors
    DEEP_ORANGE  = '\033[38;5;202m'
    ORANGE       = '\033[38;5;208m'
    YELLOW       = '\033[38;5;220m'
    LIGHT_YELLOW = '\033[38;5;228m'
    PINK         = '\033[38;5;205m'
    PURPLE       = '\033[38;5;93m'
    DEEP_PURPLE  = '\033[38;5;54m'

    # Ocean colors
    DARK_BLUE  = '\033[38;5;18m'
    BLUE       = '\033[38;5;21m'
    LIGHT_BLUE = '\033[38;5;33m'
    CYAN       = '\033[38;5;51m'

    # Sun
    BRIGHT_YELLOW = '\033[38;5;226m'
    SUN_ORANGE    = '\033[38;5;214m'

    # Misc
    BLACK    = '\033[38;5;232m'
    GRAY     = '\033[38;5;240m'
    WHITE    = '\033[38;5;255m'
    DIM_GRAY = '\033[38;5;236m'


# Fixed star positions so they don't shuffle each frame
random.seed(42)
_STARS = [(random.randint(0, 68), random.randint(0, 1)) for _ in range(18)]


def draw_sky(frame):
    """Deep purple sky with twinkling stars"""
    rows = [list(' ' * 70), list(' ' * 70)]
    for sx, sr in _STARS:
        # Each star has its own twinkle phase
        phase = (sx * 7 + sr * 13 + frame) % 10
        if phase == 0:
            char = Colors.WHITE + '✦' + Colors.RESET
        elif phase < 3:
            char = Colors.DIM_GRAY + '·' + Colors.RESET
        else:
            char = ' '
        rows[sr][sx] = char

    sky_colors = [Colors.DEEP_PURPLE, Colors.PURPLE]
    return [sky_colors[r] + ''.join(rows[r]) + Colors.RESET for r in range(2)]


def draw_sun(frame):
    """Sun with animated rays"""
    return [
        "                                   " + Colors.LIGHT_YELLOW + "*  *" + Colors.RESET,
        "                              " + Colors.YELLOW + "*" + Colors.RESET +
            "    " + Colors.BRIGHT_YELLOW + "____" + Colors.RESET + "    " + Colors.YELLOW + "*" + Colors.RESET,
        "                                  " + Colors.SUN_ORANGE + "/" + Colors.BRIGHT_YELLOW + "      \\" + Colors.RESET,
        "                     " + Colors.YELLOW + "*" + Colors.RESET +
            "           " + Colors.SUN_ORANGE + "|  " + Colors.BRIGHT_YELLOW + "◉" + Colors.SUN_ORANGE + "  |" + Colors.RESET,
        "                                  " + Colors.SUN_ORANGE + "\\" + Colors.BRIGHT_YELLOW + "______/" + Colors.RESET,
        "                              " + Colors.YELLOW + "*" + Colors.RESET + "           " + Colors.YELLOW + "*" + Colors.RESET,
        "                                   " + Colors.LIGHT_YELLOW + "*  *" + Colors.RESET,
    ]


def draw_clouds(frame):
    """Drifting clouds"""
    lines = []

    offset1 = (frame // 2) % 75
    cloud1_pos = min(5 + offset1, 65)
    lines.append(" " * cloud1_pos + Colors.GRAY + "   ___   " + Colors.RESET)

    offset2 = (frame // 3) % 80
    cloud2_pos = max(3, 68 - offset2)
    lines.append(" " * cloud2_pos + Colors.GRAY + "  ____  " + Colors.RESET)
    lines.append(" " * cloud2_pos + Colors.GRAY + " (    ) " + Colors.RESET)

    offset3 = (frame // 4) % 70
    cloud3_pos = 10 + offset3
    lines.append(" " * min(cloud3_pos, 64) + Colors.GRAY + " (  ) " + Colors.RESET)

    return lines


def draw_birds(frame):
    """Flying birds with wing flap"""
    bird_line = list(' ' * 72)
    wing = ['˄', 'ᐯ'][(frame // 2) % 2]

    for x in [12 + (frame % 50), 32 + ((frame + 15) % 45), 50 - (frame % 40)]:
        if 1 < x < 69:
            bird_line[x] = Colors.BLACK + wing + Colors.RESET

    return ["".join(bird_line)]


def draw_horizon(frame):
    """Horizon with a blinking lighthouse on the right"""
    # Lighthouse light blinks on a slow cycle
    light_on = (frame // 6) % 4 == 0
    lighthouse = (
        Colors.GRAY + "│" + Colors.RESET +
        (Colors.BRIGHT_YELLOW + "★" + Colors.RESET if light_on else Colors.GRAY + "·" + Colors.RESET) +
        Colors.GRAY + "│" + Colors.RESET
    )
    horizon = Colors.ORANGE + "━" * 66 + Colors.RESET
    return [horizon + lighthouse]


def draw_boat(frame):
    """Sailboat rocking on the waves"""
    rock = (frame // 3) % 4
    offsets = ["    ", "   ", "  ", "   "]
    pad = offsets[rock]
    G = Colors.GRAY
    R = Colors.RESET
    return [
        "                                  " + pad + G + "|"  + R,
        "                                   "       + G + "/|\\" + R,
        "                                  "        + G + "//|\\\\" + R,
        "                                 "         + G + "≈════≈" + R,
    ]


def draw_ocean(frame, dolphin_state):
    """Animated waves, with optional dolphin leap on top row"""
    wave_chars = ['~', '≈', '∿', '⌢']
    row_colors = [Colors.LIGHT_BLUE, Colors.LIGHT_BLUE, Colors.CYAN, Colors.CYAN,
                  Colors.BLUE, Colors.BLUE, Colors.DARK_BLUE, Colors.DARK_BLUE]
    lines = []

    for row in range(8):
        offset = (frame + row * 2) % 4
        wave = ''.join(
            row_colors[row] + wave_chars[(i + offset + row) % 4] + Colors.RESET
            for i in range(70)
        )
        # Splice dolphin onto first wave row
        if row == 0 and dolphin_state is not None:
            dx, dchar = dolphin_state
            wave_list = list(wave)
            # Each visible char is color_seq + char + reset = long string; easier to rebuild
            chars = [row_colors[0] + wave_chars[(i + offset) % 4] + Colors.RESET for i in range(70)]
            if 0 <= dx <= 67:
                chars[dx] = Colors.CYAN + dchar + Colors.RESET
            wave = ''.join(chars)
        lines.append(wave)

    return lines


def get_dolphin_state(frame):
    """Returns (x, char) for dolphin or None. Leaps every 90 frames, visible for 12."""
    cycle = frame % 90
    if cycle >= 12:
        return None
    # x drifts slowly between leaps
    base_x = 20 + ((frame // 90) * 11) % 35
    x = base_x + (cycle // 3)
    char = '>°)' if cycle < 6 else '<°)'
    # Return just the first char of char string since we're in a char grid
    return (min(x, 67), char[0])


def draw_frame(frame):
    """Render full frame — accumulate into one write to avoid flicker"""
    dolphin = get_dolphin_state(frame)

    parts = []
    parts.extend(draw_sky(frame))
    parts.extend(draw_clouds(frame))
    parts.append(' ' * 70)
    parts.extend(draw_birds(frame))
    parts.extend(draw_sun(frame))
    parts.extend(draw_horizon(frame))
    parts.extend(draw_boat(frame))
    parts.extend(draw_ocean(frame, dolphin))
    parts.append(Colors.DARK_BLUE + '▓' * 70 + Colors.RESET)
    parts.append('\n' + Colors.GRAY + 'Ctrl+C to exit' + Colors.RESET + ' ' * 20)

    # Move cursor home (no clear = no flash), write everything in one shot
    sys.stdout.write(Colors.HOME + '\n'.join(parts))
    sys.stdout.flush()


def main():
    sys.stdout.write(Colors.CLEAR + Colors.HIDE_CURSOR)
    sys.stdout.flush()
    frame = 0
    try:
        while True:
            draw_frame(frame)
            frame += 1
            time.sleep(0.1)
    except KeyboardInterrupt:
        sys.stdout.write(Colors.CLEAR + Colors.HOME + Colors.SHOW_CURSOR)
        sys.stdout.flush()
        print('\n' + Colors.CYAN + 'Goodbye! 🌊' + Colors.RESET)
        sys.exit(0)


main()
