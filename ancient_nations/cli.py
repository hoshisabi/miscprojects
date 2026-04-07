"""
cli.py – Headless CLI / API for Ancient Nations.

Designed to be consumed programmatically (e.g. by Claude) via JSON output.

Usage
-----
  python cli.py run   --seed 42 --turns 200
  python cli.py run   --seed 42 --turns 200 --no-events
  python cli.py run   --seed 42 --turns 200 --log-limit 200
  python cli.py query --seed 42 --turns 100 --tile 45,32
  python cli.py query --seed 42 --turns 100 --nation Romanus
  python cli.py query --seed 42 --turns 100 --region 3,4
  python cli.py query --seed 42 --turns 800 --events --from 600   # events with turn >= 600
  python cli.py stream --seed 42 --turns 50            # NDJSON one line per turn
  python cli.py stream --seed 42 --turns 200 --from 150   # only emit turns >= 150
  python cli.py battles --seed 42 --turns 200
  python cli.py map    --seed 42              # ASCII map: no turns simulated unless --turns set

All commands write JSON (or NDJSON for stream) to stdout.
Pass --pretty for human-readable indented JSON.
"""

import argparse
import json
import sys
import math
from engine import GameSession
from constants import *
from snapshot import army_dict, battle_dict, nation_dict, tile_dict


# ── Session helper ────────────────────────────────────────────────────────────

def _open_session(args) -> GameSession:
    s = GameSession(seed=args.seed, num_nations=args.nations)
    if getattr(args, 'no_events', False):
        s.disable_random_events()
    return s


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_run(args):
    """Run N turns and print final state summary."""
    s = _open_session(args)
    s.run_turns(args.turns)
    g = s.game

    log_limit = max(1, min(args.log_limit, min(10_000, LOG_MAX)))
    out = s.snapshot(log_limit=log_limit)
    out['battles'] = [battle_dict(b, [n.name for n in g.nations]) for b in g.battles]

    if getattr(args, 'format', 'json') == 'narrative':
        import narrative
        sys.stdout.write(narrative.render(out) + '\n')
    else:
        _print(out, args.pretty)


def cmd_query(args):
    """Query specific aspect of game state after N turns."""
    s = _open_session(args)
    s.run_turns(args.turns)
    g = s.game

    from_turn = getattr(args, 'from_turn', None)

    if args.tile:
        x, y = map(int, args.tile.split(','))
        if not g.world.in_bounds(x, y):
            _error({'error': f'Tile ({x},{y}) out of bounds'}, args.pretty)
            return
        _print(tile_dict(g.world.t(x, y), g), args.pretty)

    elif args.nation:
        match = [n for n in g.nations
                 if n.name.lower().startswith(args.nation.lower())]
        if not match:
            _error({'error': f'Nation "{args.nation}" not found'}, args.pretty)
            return
        n   = match[0]
        out = nation_dict(n, g.turn)
        out['wars_with'] = [o.name for o in g.nations
                            if o.idx != n.idx and n.at_war_with(o.idx)]
        # History arrays
        out['history'] = n.history
        # All armies
        out['army_details'] = [army_dict(a, [x.name for x in g.nations])
                                for a in n.armies if a.is_alive()]
        _print(out, args.pretty)

    elif args.region:
        ox, oy = map(int, args.region.split(','))
        if not (0 <= ox < OUTER_SIZE and 0 <= oy < OUTER_SIZE):
            _error({'error': f'Region ({ox},{oy}) out of bounds (0-{OUTER_SIZE-1})'}, args.pretty)
            return
        tiles = g.world.outer_region(ox, oy)
        # Summarise ownership
        owner_counts = {}
        terrain_counts = {}
        for t in tiles:
            owner = g.nations[t.owner].name if t.owner >= 0 else 'Neutral'
            owner_counts[owner] = owner_counts.get(owner, 0) + 1
            tn = TERRAIN_NAMES[t.terrain]
            terrain_counts[tn] = terrain_counts.get(tn, 0) + 1
        towns_in_region = [tile_dict(t, g) for t in tiles if t.town]
        armies_in_region = [army_dict(a, [n.name for n in g.nations])
                            for t in tiles for a in t.armies]
        _print({
            'region':          [ox, oy],
            'turn':            g.turn,
            'ownership':       owner_counts,
            'terrain_types':   terrain_counts,
            'towns':           towns_in_region,
            'armies':          armies_in_region,
            'tile_details':    [tile_dict(t, g) for t in tiles],
        }, args.pretty)

    elif args.events:
        ev = g.events_history
        if from_turn is not None:
            ev = [e for e in ev if e.turn >= from_turn]
        _print({
            'turn':   g.turn,
            'events': [e.to_dict() for e in ev],
        }, args.pretty)

    else:
        # Default: full summary
        out = s.snapshot()
        if from_turn is not None:
            out['events'] = [e for e in out['events'] if e['turn'] >= from_turn]
            out['events_total'] = len(out['events'])
        _print(out, args.pretty)


def cmd_stream(args):
    """Run turn by turn, emitting one JSON line per turn (NDJSON)."""
    s = _open_session(args)
    g = s.game
    from_turn = getattr(args, 'from_turn', None)
    for _ in range(args.turns):
        s.step()
        if from_turn is not None and g.turn < from_turn:
            continue
        line = json.dumps(s.turn_snapshot())
        sys.stdout.write(line + '\n')
        sys.stdout.flush()


def cmd_battles(args):
    """Run N turns and print the full battle log."""
    s = _open_session(args)
    s.run_turns(args.turns)
    g = s.game

    nation_names = [n.name for n in g.nations]
    _print({
        'turn':    g.turn,
        'seed':    g.world.seed,
        'count':   len(g.battles),
        'battles': [battle_dict(b, nation_names) for b in g.battles],
    }, args.pretty)


def cmd_map(args):
    """Generate world and dump ASCII map + terrain/resource summary (no simulation)."""
    s = _open_session(args)
    s.run_turns(args.turns)
    g = s.game

    w  = g.world
    rows = []
    for y in range(0, MAP_SIZE, 2):     # sample every other row to compress
        row = ''
        for x in range(0, MAP_SIZE, 2): # sample every other col
            t = w.t(x, y)
            if t.owner >= 0:
                row += g.nations[t.owner].letter
            else:
                row += TERRAIN_CHARS[t.terrain]
        rows.append(row)

    # Terrain census
    terrain_counts = {}
    for y in range(MAP_SIZE):
        for x in range(MAP_SIZE):
            tn = TERRAIN_NAMES[w.t(x,y).terrain]
            terrain_counts[tn] = terrain_counts.get(tn,0) + 1

    _print({
        'seed':          g.world.seed,
        'turn':          g.turn,
        'map_ascii':     rows,
        'terrain_dist':  terrain_counts,
        'resource_values': {RESOURCE_NAMES[r]: round(g.world.resource_values[r], 2)
                            for r in range(NUM_RESOURCES)},
        'nations':       [{'name': n.name, 'capital': [n.capital.x, n.capital.y]
                           if n.capital else None}
                          for n in g.nations],
    }, args.pretty)


def cmd_summary(args):
    """Run simulation and emit a compact human-readable summary for sharing."""
    s = _open_session(args)
    s.run_turns(args.turns)
    g = s.game

    out   = s.snapshot()
    out['battles'] = [battle_dict(b, [n.name for n in g.nations]) for b in g.battles]

    nations  = out['nations']
    battles  = out['battles']
    events   = out['events']
    turns    = out['turn']
    seed     = out['seed']

    alive   = sorted([n for n in nations if n['alive']],     key=lambda n: -n['territory'])
    dead    = sorted([n for n in nations if not n['alive']], key=lambda n: n.get('death_turn') or 0)

    lines = []
    lines.append(f"Ancient Nations — seed {seed}, {turns} turns")
    lines.append("")

    # Standings
    lines.append("Standings:")
    for i, n in enumerate(alive, 1):
        trait = n.get('trait') or '?'
        lines.append(f"  {i}. {n['name']} ({trait}) — {n['territory']} tiles, "
                     f"pop {n['population']:,}, {n['battles_won']}W/{n['battles_lost']}L")
    for n in dead:
        dt = n.get('death_turn')
        ab = n.get('absorbed_by')
        trait = n.get('trait') or '?'
        fate = f"absorbed by {ab} at t{dt}" if ab and dt else (f"eliminated at t{dt}" if dt else "eliminated")
        lines.append(f"  ✗ {n['name']} ({trait}) — {fate}")

    # Notable events
    HIGH_IMPACT = {'civil_war', 'assassination', 'rebellion', 'plague', 'drought', 'earthquake'}
    notable = [e for e in events if e.get('type') in HIGH_IMPACT]
    notable.sort(key=lambda e: e['turn'])
    if notable:
        lines.append("")
        lines.append("Notable events:")
        for e in notable[:8]:
            lines.append(f"  t{e['turn']:>4}: {e['description']}")

    # Battle totals
    lines.append("")
    lines.append(f"Battles: {out['battles_total']} total, {out['events_total']} world events")

    sys.stdout.write('\n'.join(lines) + '\n')
    sys.stdout.flush()


# ── Utilities ─────────────────────────────────────────────────────────────────

def _print(obj, pretty=False):
    if pretty:
        sys.stdout.write(json.dumps(obj, indent=2) + '\n')
    else:
        sys.stdout.write(json.dumps(obj) + '\n')
    sys.stdout.flush()


def _error(obj, pretty=False):
    """Print an error dict and exit with non-zero status."""
    _print(obj, pretty)
    sys.exit(1)


# ── Argument parsing ──────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(
        prog='cli.py',
        description='Ancient Nations headless CLI / API',
    )
    sub = p.add_subparsers(dest='command', required=True)

    # Shared flags
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument('--seed',    type=int, default=None,       help='World seed')
    shared.add_argument('--turns',   type=int, default=100,        help='Number of turns to simulate')
    shared.add_argument('--nations', type=int, default=NUM_NATIONS, help='Number of nations')
    shared.add_argument('--pretty',  action='store_true',          help='Pretty-print JSON')
    shared.add_argument('--no-events', action='store_true',        help='Disable random world events')

    # run
    sp = sub.add_parser('run', parents=[shared], help='Run simulation and print final state')
    sp.add_argument('--format', choices=['json', 'narrative'], default='json',
                    help='Output format (default: json)')
    sp.add_argument('--log-limit', type=int, default=50, dest='log_limit',
                    help='Max log entries in output (default 50; sim only retains up to LOG_MAX lines in memory)')

    # query
    sq = sub.add_parser('query', parents=[shared], help='Query a specific aspect of state')
    sq.add_argument('--tile',    type=str, help='Tile coordinates x,y')
    sq.add_argument('--nation',  type=str, help='Nation name (prefix match)')
    sq.add_argument('--region',  type=str, help='Outer region ox,oy')
    sq.add_argument('--events',  action='store_true', help='List all world events')
    sq.add_argument('--from', dest='from_turn', type=int, default=None, metavar='T',
                    help='With default query or --events: only include world events with turn >= T')

    # stream
    st = sub.add_parser('stream', parents=[shared],
                        help='Emit one JSON line per turn (NDJSON)')
    st.add_argument('--from', dest='from_turn', type=int, default=None, metavar='T',
                    help='Only emit lines for turns >= T (full sim still runs from start)')

    # summary
    sub.add_parser('summary', parents=[shared],
                   help='Compact human-readable summary — standings, deaths, notable events')

    # battles
    sub.add_parser('battles', parents=[shared], help='Print full battle log')

    # map
    sm = sub.add_parser('map', parents=[shared], help='Print ASCII map and terrain info')
    sm.set_defaults(turns=0)

    return p


def main():
    # Ensure UTF-8 output even on Windows
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    parser = build_parser()
    args   = parser.parse_args()

    dispatch = {
        'run':     cmd_run,
        'query':   cmd_query,
        'stream':  cmd_stream,
        'summary': cmd_summary,
        'battles': cmd_battles,
        'map':     cmd_map,
    }
    dispatch[args.command](args)


if __name__ == '__main__':
    main()
