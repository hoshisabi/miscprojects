"""
cli.py – Headless CLI / API for Ancient Nations.

Designed to be consumed programmatically (e.g. by Claude) via JSON output.

Usage
-----
  python cli.py run   --seed 42 --turns 200
  python cli.py run   --seed 42 --turns 200 --events
  python cli.py run   --seed 42 --turns 200 --no-events
  python cli.py query --seed 42 --turns 100 --tile 45,32
  python cli.py query --seed 42 --turns 100 --nation Romanus
  python cli.py query --seed 42 --turns 100 --region 3,4
  python cli.py stream --seed 42 --turns 50   # NDJSON one line per turn
  python cli.py battles --seed 42 --turns 200
  python cli.py map    --seed 42              # ASCII world map (no simulation)

All commands write JSON (or NDJSON for stream) to stdout.
Pass --pretty for human-readable indented JSON.
"""

import argparse
import json
import sys
import math
from game import Game
from constants import *


# ── Serialisation helpers ─────────────────────────────────────────────────────

def nation_dict(n, turn=0):
    cap = n.capital
    return {
        'idx':              n.idx,
        'name':             n.name,
        'alive':            n.alive,
        'territory':        len(n.tiles),
        'population':       int(n.total_population()),
        'armies':           n.total_armies(),
        'army_strength':    round(n.army_strength(), 1),
        'resources':        {RESOURCE_NAMES[r]: round(n.res[r], 1) for r in range(NUM_RESOURCES)},
        'towns':            [town_dict(t) for t in n.towns],
        'capital':          cap.name if cap else None,
        'wars_with':        [],   # filled in game_summary
        'allied_with':      [],   # filled in game_summary
        'battles_won':      n.history.get('battles_won', 0),
        'battles_lost':     n.history.get('battles_lost', 0),
        'trades_done':      n.history.get('trades_done', 0),
        'alliances_formed': n.history.get('alliances_formed', 0),
    }


def town_dict(t):
    return {
        'name':       t.name,
        'x':          t.x,
        'y':          t.y,
        'level':      t.level,
        'level_name': t.level_name(),
        'population': int(t.population),
        'is_capital': t.is_capital,
        'radius':     t.radius,
    }


def army_dict(a, nation_names):
    return {
        'id':       a.id,
        'nation':   nation_names[a.nation],
        'x':        a.x,
        'y':        a.y,
        'level':    a.level,
        'health':   a.health,
        'max_health': a.max_health,
        'order':    a.order,
        'battles_won':  a.battles_won,
        'battles_lost': a.battles_lost,
    }


def tile_dict(t, game):
    owner = game.nations[t.owner].name if t.owner >= 0 else 'Neutral'
    return {
        'x':        t.x,
        'y':        t.y,
        'terrain':  TERRAIN_NAMES[t.terrain],
        'owner':    owner,
        'entity':   t.entity,
        'road':     t.road,
        'elevation': round(t.elevation, 3),
        'moisture':  round(t.moisture, 3),
        'deposits': {RESOURCE_NAMES[r]: round(t.deposits[r], 2) for r in range(NUM_RESOURCES)},
        'town':     town_dict(t.town) if t.town else None,
        'armies':   [army_dict(a, [n.name for n in game.nations]) for a in t.armies],
    }


def battle_dict(b, nation_names):
    return {
        'turn':       b.turn,
        'location':   [b.x, b.y],
        'attacker':   nation_names[b.atk_nation],
        'defender':   nation_names[b.def_nation] if b.def_nation >= 0 else 'Neutral',
        'winner':     nation_names[b.winner] if b.winner >= 0 else 'Neutral',
        'atk_losses': b.atk_losses,
        'def_losses': b.def_losses,
        'notes':      b.notes,
    }


def game_summary(game):
    """Full snapshot of game state at current turn."""
    nation_names = [n.name for n in game.nations]

    # Attach war / alliance lists
    nations_out = []
    for n in game.nations:
        nd = nation_dict(n, game.turn)
        nd['wars_with']   = [o.name for o in game.nations
                             if o.idx != n.idx and n.at_war_with(o.idx)]
        nd['allied_with'] = [o.name for o in game.nations
                             if o.idx != n.idx and n.allied_with(o.idx)]
        nations_out.append(nd)

    return {
        'turn':           game.turn,
        'seed':           game.world.seed,
        'map_size':       MAP_SIZE,
        'nations':        nations_out,
        'battles_total':  len(game.battles),
        'events_total':   len(game.events_history),
        'events':         [e.to_dict() for e in game.events_history],
        'resource_values': {RESOURCE_NAMES[r]: round(game.world.resource_values[r], 2)
                            for r in range(NUM_RESOURCES)},
        'logs':           [{'turn': t, 'msg': m, 'nation': n}
                           for t, m, n in game.logs[-50:]],
    }


def turn_summary(game):
    """Lightweight per-turn snapshot for NDJSON streaming."""
    return {
        'turn': game.turn,
        'nations': [
            {
                'name':      n.name,
                'territory': len(n.tiles),
                'armies':    n.total_armies(),
                'gold':      round(n.res[RES_GOLD], 1),
                'alive':     n.alive,
            }
            for n in game.nations
        ],
        'battles_this_turn': [
            battle_dict(b, [n.name for n in game.nations])
            for b in game.battles if b.turn == game.turn
        ],
        'events_this_turn': [
            e.to_dict() for e in game.events_history
            if e.turn == game.turn
        ],
    }


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_run(args):
    """Run N turns and print final state summary."""
    g = Game(seed=args.seed, num_nations=args.nations)
    if args.no_events:
        # Disable all events by making rarity huge
        for k in g.events._cooldowns:
            g.events._cooldowns[k] = 999999

    for _ in range(args.turns):
        g.process_turn()

    out = game_summary(g)
    out['battles'] = [battle_dict(b, [n.name for n in g.nations]) for b in g.battles]
    _print(out, args.pretty)


def cmd_query(args):
    """Query specific aspect of game state after N turns."""
    g = Game(seed=args.seed, num_nations=args.nations)
    for _ in range(args.turns):
        g.process_turn()

    if args.tile:
        x, y = map(int, args.tile.split(','))
        if not g.world.in_bounds(x, y):
            _print({'error': f'Tile ({x},{y}) out of bounds'}, args.pretty)
            return
        _print(tile_dict(g.world.t(x, y), g), args.pretty)

    elif args.nation:
        match = [n for n in g.nations
                 if n.name.lower().startswith(args.nation.lower())]
        if not match:
            _print({'error': f'Nation "{args.nation}" not found'}, args.pretty)
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
            _print({'error': f'Region ({ox},{oy}) out of bounds (0-{OUTER_SIZE-1})'}, args.pretty)
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
        _print({
            'turn':   g.turn,
            'events': [e.to_dict() for e in g.events_history],
        }, args.pretty)

    else:
        # Default: full summary
        _print(game_summary(g), args.pretty)


def cmd_stream(args):
    """Run turn by turn, emitting one JSON line per turn (NDJSON)."""
    g = Game(seed=args.seed, num_nations=args.nations)
    if args.no_events:
        for k in g.events._cooldowns:
            g.events._cooldowns[k] = 999999

    for _ in range(args.turns):
        g.process_turn()
        line = json.dumps(turn_summary(g))
        sys.stdout.write(line + '\n')
        sys.stdout.flush()


def cmd_battles(args):
    """Run N turns and print the full battle log."""
    g = Game(seed=args.seed, num_nations=args.nations)
    for _ in range(args.turns):
        g.process_turn()

    nation_names = [n.name for n in g.nations]
    _print({
        'turn':    g.turn,
        'seed':    g.world.seed,
        'count':   len(g.battles),
        'battles': [battle_dict(b, nation_names) for b in g.battles],
    }, args.pretty)


def cmd_map(args):
    """Generate world and dump ASCII map + terrain/resource summary (no simulation)."""
    g = Game(seed=args.seed, num_nations=args.nations)
    # Optionally advance turns
    for _ in range(args.turns):
        g.process_turn()

    w  = g.world
    rows = []
    for y in range(0, MAP_SIZE, 2):     # sample every other row to compress
        row = ''
        for x in range(0, MAP_SIZE, 2): # sample every other col
            t = w.t(x, y)
            if t.owner >= 0:
                row += NATION_LETTERS[t.owner]
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


# ── Utilities ─────────────────────────────────────────────────────────────────

def _print(obj, pretty=False):
    if pretty:
        sys.stdout.write(json.dumps(obj, indent=2) + '\n')
    else:
        sys.stdout.write(json.dumps(obj) + '\n')
    sys.stdout.flush()


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

    # query
    sq = sub.add_parser('query', parents=[shared], help='Query a specific aspect of state')
    sq.add_argument('--tile',    type=str, help='Tile coordinates x,y')
    sq.add_argument('--nation',  type=str, help='Nation name (prefix match)')
    sq.add_argument('--region',  type=str, help='Outer region ox,oy')
    sq.add_argument('--events',  action='store_true', help='List all world events')

    # stream
    sub.add_parser('stream', parents=[shared],
                   help='Emit one JSON line per turn (NDJSON)')

    # battles
    sub.add_parser('battles', parents=[shared], help='Print full battle log')

    # map
    sm = sub.add_parser('map', parents=[shared], help='Print ASCII map and terrain info')

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
        'battles': cmd_battles,
        'map':     cmd_map,
    }
    dispatch[args.command](args)


if __name__ == '__main__':
    main()
