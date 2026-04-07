"""
snapshot.py – Read-only views of Game state for clients (CLI, tests, APIs).

Pure functions over a Game instance; no simulation side effects.
"""

from __future__ import annotations

from constants import *


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
        'trait':            n.trait['name'] if n.trait else None,
        'trait_id':         n.trait['id'] if n.trait else None,
        'slot_revivals':    n.slot_revivals,
        'death_turn':       n.death_turn,
        'absorbed_by':      n.absorbed_by,
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


def game_summary(game, log_limit=50):
    """Full snapshot of game state at current turn."""
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
                           for t, m, n in game.logs[-log_limit:]],
    }


def turn_summary(game):
    """Lightweight per-turn snapshot for NDJSON streaming.

    Dead nations have territory/armies/gold zeroed out so consumers
    aren't misled by draining tile counts. death_turn and absorbed_by
    appear on dead nation rows; use alive=false as the reliable signal.
    """
    def _nation_row(n):
        row = {
            'name':          n.name,
            'trait':         n.trait['name'] if n.trait else None,
            'trait_id':      n.trait['id'] if n.trait else None,
            'slot_revivals': n.slot_revivals,
            'territory':     len(n.tiles) if n.alive else 0,
            'armies':        n.total_armies() if n.alive else 0,
            'gold':          round(n.res[RES_GOLD], 1) if n.alive else 0,
            'alive':         n.alive,
        }
        if not n.alive:
            row['death_turn']  = n.death_turn
            row['absorbed_by'] = n.absorbed_by
        return row

    return {
        'turn': game.turn,
        'nations': [_nation_row(n) for n in game.nations],
        'battles_this_turn': [
            battle_dict(b, [n.name for n in game.nations])
            for b in game.battles if b.turn == game.turn
        ],
        'events_this_turn': [
            e.to_dict() for e in game.events_history
            if e.turn == game.turn
        ],
    }
