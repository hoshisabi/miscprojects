"""
narrative.py — Prose renderer for Ancient Nations game state.

Takes the dict produced by game_summary() (i.e. `cli.py run --format json`)
and returns a readable text chronicle.  Pure function: no file I/O, no game
objects, no network.  Call it on any source of game-state JSON.

    import narrative
    text = narrative.render(state_dict)
"""

from collections import defaultdict, Counter
import math


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ordinal(n: int) -> str:
    suffix = {1:'st', 2:'nd', 3:'rd'}.get(n if n < 20 else n % 10, 'th')
    return f"{n}{suffix}"


def _list_names(names: list[str], conjunction='and') -> str:
    if not names:
        return ''
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} {conjunction} {names[1]}"
    return ', '.join(names[:-1]) + f', {conjunction} {names[-1]}'


def _approx_pop(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f} million"
    if n >= 1_000:
        return f"{n//1000}k"
    return str(n)


def _resource_character(resource_values: dict) -> str:
    """Describe the world's resource character from its value multipliers."""
    riches, scarce = [], []
    for name, val in resource_values.items():
        if name == 'Wood':
            continue   # wood is always 1.0 baseline
        if val >= 3.0:
            riches.append(name.lower())
        elif val <= 0.8:
            scarce.append(name.lower())

    parts = []
    if riches:
        parts.append(f"rich in {_list_names(riches)}")
    if scarce:
        parts.append(f"poor in {_list_names(scarce)}")
    if not parts:
        return "balanced in resources"
    return ' but '.join(parts)


def _battles_in(battles: list, lo: int, hi: int) -> list:
    return [b for b in battles if lo <= b['turn'] <= hi]


def _events_in(events: list, lo: int, hi: int) -> list:
    return [e for e in events if lo <= e['turn'] <= hi]


def _death_info(nation: dict, battles: list) -> tuple[int | None, str | None]:
    """Return (death_turn, absorbed_by) for a dead nation."""
    if nation['alive']:
        return None, None
    # Use tracked fields if available
    dt = nation.get('death_turn')
    ab = nation.get('absorbed_by')
    if dt:
        return dt, ab
    # Fallback: infer from battle log
    turns = [b['turn'] for b in battles
             if b['attacker'] == nation['name'] or b['defender'] == nation['name']]
    return (max(turns) if turns else None), ab


# ── Section renderers ─────────────────────────────────────────────────────────

def _title(state: dict) -> str:
    turns = state['turn']
    seed  = state['seed']
    alive = sum(1 for n in state['nations'] if n['alive'])
    total = len(state['nations'])
    return (
        f"ANCIENT NATIONS — Seed {seed}\n"
        f"{'=' * 44}\n"
        f"A chronicle of {turns} turns.  "
        f"{alive} of {total} nations survive."
    )


def _world_intro(state: dict) -> str:
    rv   = state['resource_values']
    char = _resource_character(rv)
    gold_note = ''
    if rv.get('Gold', 1) > 20:
        gold_note = (
            f"  Gold commanded extraordinary value — {rv['Gold']:.0f} times its weight "
            f"in wood — making trade and tribute decisive levers of power."
        )
    elif rv.get('Metal', 1) > 4:
        gold_note = (
            f"  Metal was scarce and precious, worth {rv['Metal']:.1f} times its "
            f"standard value, driving competition over mines and veins."
        )

    return (
        f"The world of seed {state['seed']} was {char}."
        f"{gold_note}"
    )


def _nations_intro(state: dict, battles: list) -> str:
    """Opening paragraph introducing the nations."""
    names = [n['name'] for n in state['nations']]

    # Battle win rates to hint at military character without needing trait data
    wins_by   = Counter(b['winner'] for b in battles)
    fought_as = Counter()
    for b in battles:
        fought_as[b['attacker']] += 1
        fought_as[b['defender']] += 1

    lines = []
    for n in state['nations']:
        name   = n['name']
        fought = fought_as.get(name, 0)
        wins   = wins_by.get(name, 0)
        rate   = wins / fought if fought else 0
        towns  = len(n['towns'])
        cap    = n['capital'] or '?'

        trait = n.get('trait')
        if trait:
            character = f"a {trait.lower()} people"
        elif rate >= 0.70:
            character = "a fearsome military power"
        elif rate >= 0.55:
            character = "a capable and confident nation"
        elif rate >= 0.40:
            character = "a nation that fought hard for every gain"
        else:
            character = "a nation that struggled against stronger neighbours"

        town_str = f"{towns} {'town' if towns == 1 else 'towns'}"
        cap_str  = f"around {cap}" if cap and cap != '?' else "in an unknown land"
        lines.append(f"{name}, {character}, founded {cap_str} with {town_str}.")

    intro = (
        f"Six nations rose from the wilderness: "
        f"{_list_names(names[:-1])}, and {names[-1]}.  "
        f"Each would carve its own path.\n\n"
    )
    intro += '  '.join(lines)
    return intro


def _era_name(era_idx: int, era_battles: list, era_events: list, total_turns: int) -> str:
    """Choose a thematic name for an era based on what happened in it."""
    disasters = {'drought','plague','flood','earthquake','volcanic_ash','forest_fire'}
    n_dis  = sum(1 for e in era_events if e['type'] in disasters)
    n_reb  = sum(1 for e in era_events if e['type'] == 'rebellion')
    n_asn  = sum(1 for e in era_events if e['type'] == 'assassination')
    n_bat  = len(era_battles)

    if era_idx == 0:
        return "The Age of Founding"
    if n_reb > 0:
        return "The Age of Fracture"
    if n_bat == 0:
        return "The Quiet Age"
    if n_dis >= 5 and n_bat < 80:
        return "The Age of Trials"
    if n_bat > 300:
        return "The Age of War"
    if n_bat > 150:
        return "The Age of Conflict"
    if n_asn >= 2:
        return "The Age of Intrigue"

    labels = [
        "The Age of Expansion",
        "The Age of Rivalry",
        "The Age of Reckoning",
        "The Age of Dominion",
        "The Final Age",
    ]
    return labels[min(era_idx - 1, len(labels) - 1)]


def _describe_era_conflicts(era_battles: list, nations: list) -> str:
    """Summarise the wars of an era in a sentence or two."""
    if not era_battles:
        return "No battles were recorded in this period."

    # Count battles per nation pair (order-independent)
    pair_count: Counter = Counter()
    pair_wins:  dict    = defaultdict(Counter)
    for b in era_battles:
        pair = tuple(sorted([b['attacker'], b['defender']]))
        pair_count[pair] += 1
        pair_wins[pair][b['winner']] += 1

    # Top conflict
    top_pair, top_count = pair_count.most_common(1)[0]
    a, b_ = top_pair
    a_wins = pair_wins[top_pair].get(a, 0)
    b_wins = pair_wins[top_pair].get(b_, 0)
    if a_wins > b_wins * 1.5:
        outcome = f"{a} held the upper hand, winning {a_wins} of {top_count} engagements"
    elif b_wins > a_wins * 1.5:
        outcome = f"{b_} held the upper hand, winning {b_wins} of {top_count} engagements"
    else:
        outcome = f"neither side could claim dominance across {top_count} engagements"

    sentence = f"The fiercest fighting was between {a} and {b_}: {outcome}."

    # Overall most successful attacker this era
    attacker_wins = Counter(b['winner'] for b in era_battles
                            if b['winner'] == b['attacker'])  # won as attacker
    # Actually just: who won most battles overall
    overall_wins = Counter(b['winner'] for b in era_battles)
    if overall_wins:
        top_nation, top_wins = overall_wins.most_common(1)[0]
        total = len(era_battles)
        if top_wins > total * 0.35 and len(pair_count) > 1:
            sentence += (
                f"  Across all fronts, {top_nation} proved the dominant force, "
                f"claiming {top_wins} of {total} battles."
            )

    return sentence


def _describe_era_events(era_events: list) -> str:
    """Turn world events into a prose sentence or two."""
    if not era_events:
        return ""

    sentences = []
    event_templates = {
        'gold_rush':    lambda e: (
            f"A gold rush near {tuple(e['location'])} brought new wealth to the region"
            + (f", adding {int(e['effects'].get('gold_added',0)):.0f} in value"
               if e['effects'].get('gold_added', 0) > 100 else "") + "."
        ),
        'rich_vein':    lambda e: (
            f"Prospectors struck rich metal deposits near {tuple(e['location'])}, "
            f"opening new veins across {e['effects'].get('tiles', '?')} tiles."
        ),
        'assassination': lambda e: (
            f"An assassin's blade ended the reign of {e['effects'].get('nation','a ruler')}'s leader"
            + (f", ushering in a {e['effects']['new_trait']} era"
               if e['effects'].get('trait_changed') else "") + "."
        ),
        'rebellion':    lambda e: (
            f"Civil war tore {e['effects'].get('parent','a great power')} apart: "
            f"{e['effects'].get('rebel','rebels')} rose with "
            f"{e['effects'].get('tiles_split', '?')} tiles, declaring themselves a "
            f"{e['effects'].get('trait','new')} state."
        ),
        'plague':       lambda e: (
            f"Plague swept through the region near {tuple(e['location'])}"
            + (f", killing {e['effects']['pop_lost']} and weakening {e['effects']['armies_weakened']} armies"
               if e['effects'].get('pop_lost', 0) > 0 else ", though it passed without great loss") + "."
        ),
        'drought':      lambda e: (
            f"Drought gripped the lands near {tuple(e['location'])}, "
            f"costing {int(e['effects'].get('food_lost', 0))} food across "
            f"{e['effects'].get('nations_affected', '?')} nation(s)."
        ),
        'flood':        lambda e: (
            f"Floods near {tuple(e['location'])} inundated {e['effects'].get('tiles_flooded','?')} tiles"
            + (f" and destroyed {e['effects']['farms_destroyed']} farms"
               if e['effects'].get('farms_destroyed', 0) > 0 else "") + "."
        ),
        'earthquake':   lambda e: (
            f"A magnitude-{e['magnitude']} earthquake struck near {tuple(e['location'])}"
            + (f", destroying {e['effects']['buildings_destroyed']} buildings"
               if e['effects'].get('buildings_destroyed', 0) > 0 else "") + "."
        ),
        'volcanic_ash': lambda e: (
            f"Volcanic ash from {tuple(e['location'])} blanketed {e['effects'].get('tiles_covered','?')} tiles, "
            f"costing {int(e['effects'].get('food_lost',0))} food."
        ),
        'forest_fire':  lambda e: (
            f"Fire swept the forests near {tuple(e['location'])}, "
            f"burning {e['effects'].get('forests_burned','?')} tiles to plains."
        ),
        'migration':    lambda e: (
            f"Migration swelled {e['effects'].get('nation','a nation')}'s population."
        ),
    }

    # Deduplicate similar events, pick the most impactful
    seen_types: set = set()
    for e in sorted(era_events, key=lambda x: -x.get('magnitude', 0)):
        t = e['type']
        # Always include rebellions and assassinations; limit repeats of others
        if t in ('rebellion', 'assassination'):
            tmpl = event_templates.get(t)
            if tmpl:
                sentences.append(tmpl(e))
        elif t not in seen_types:
            seen_types.add(t)
            tmpl = event_templates.get(t)
            if tmpl:
                sentences.append(tmpl(e))

    return '  '.join(sentences)


def _era_paragraph(era_idx: int, lo: int, hi: int,
                   state: dict, battles: list, events: list,
                   used_names: dict | None = None) -> str:
    era_bat = _battles_in(battles, lo, hi)
    era_evt = _events_in(events, lo, hi)

    base_name = _era_name(era_idx, era_bat, era_evt, state['turn'])
    if used_names is not None:
        count = used_names.get(base_name, 0)
        used_names[base_name] = count + 1
        name = base_name if count == 0 else f"{base_name}, {_ordinal(count + 1)} Period"
    else:
        name = base_name
    header = f"{name} (Turns {lo}–{hi})"
    border = '—' * len(header)

    # Detect deaths in this era
    deaths = []
    for n in state['nations']:
        if not n['alive']:
            dt, ab = _death_info(n, battles)
            if dt and lo <= dt <= hi:
                deaths.append((n['name'], dt, ab))

    body_parts = []

    # Opening sentence for the era
    total_bat = len(era_bat)
    if total_bat == 0:
        body_parts.append("An unusual calm settled over the known world during this period.")
    else:
        body_parts.append(
            f"{total_bat} battles were fought across {hi - lo} turns "
            f"as the nations jostled for position."
        )

    # Conflict summary
    conflict = _describe_era_conflicts(era_bat, state['nations'])
    if conflict:
        body_parts.append(conflict)

    # World events
    evt_prose = _describe_era_events(era_evt)
    if evt_prose:
        body_parts.append(evt_prose)

    # Deaths
    for name_, turn, absorber in sorted(deaths, key=lambda x: x[1]):
        if absorber:
            body_parts.append(f"{name_} fell in turn {turn}, absorbed by {absorber}.")
        else:
            body_parts.append(f"{name_} fell in turn {turn}.")

    body = '  '.join(body_parts)
    return f"{header}\n{border}\n{body}"


def _chronicle(state: dict) -> str:
    battles = state.get('battles', [])
    events  = state.get('events', [])
    turns   = state['turn']

    # Choose era size: aim for 4–8 eras
    era_size = max(50, (turns // 6 // 50) * 50) if turns > 200 else 100
    era_size  = min(era_size, 200)

    eras      = []
    used_names: dict[str, int] = {}
    lo   = 1
    idx  = 0
    while lo <= turns:
        hi = min(lo + era_size - 1, turns)
        eras.append(_era_paragraph(idx, lo, hi, state, battles, events, used_names))
        lo  += era_size
        idx += 1

    return '\n\n'.join(eras)


def _closing(state: dict, battles: list) -> str:
    nations  = state['nations']
    alive    = [n for n in nations if n['alive']]
    dead     = [n for n in nations if not n['alive']]

    # Sort survivors by territory
    alive_sorted = sorted(alive, key=lambda n: -n['territory'])

    lines = ["FINAL STANDING\n" + "=" * 14]

    for rank, n in enumerate(alive_sorted, 1):
        lines.append(
            f"  {_ordinal(rank)}: {n['name']}"
            f" — {n['territory']} tiles, "
            f"population {_approx_pop(n['population'])}"
            + (f", at war with {_list_names(n['wars_with'])}" if n['wars_with'] else "")
            + "."
        )

    if dead:
        lines.append("\nFallen:")
        for n in sorted(dead, key=lambda x: x.get('death_turn') or 0):
            dt  = n.get('death_turn')
            ab  = n.get('absorbed_by')
            tr  = n.get('trait')
            desc = n['name']
            if tr:
                desc += f" ({tr})"
            if dt and ab:
                desc += f" — absorbed by {ab} in turn {dt}"
            elif dt:
                desc += f" — fell in turn {dt}"
            elif ab:
                desc += f" — absorbed by {ab}"
            lines.append(f"  {desc}.")

    # Records
    records = []
    wins_by = Counter(b['winner'] for b in battles)
    if wins_by:
        top, top_w = wins_by.most_common(1)[0]
        records.append(f"{top} won the most battles: {top_w}.")

    most_pop = max(nations, key=lambda n: n['population'])
    records.append(
        f"{most_pop['name']} built the largest population: "
        f"{_approx_pop(most_pop['population'])}."
    )

    most_terr = max(nations, key=lambda n: n['territory'])
    if most_terr['name'] != alive_sorted[0]['name']:
        records.append(
            f"{most_terr['name']} held the most territory at game end: "
            f"{most_terr['territory']} tiles."
        )

    if records:
        lines.append("\nRecords:")
        for r in records:
            lines.append(f"  {r}")

    return '\n'.join(lines)


# ── Public API ────────────────────────────────────────────────────────────────

def render(state: dict) -> str:
    """
    Render a game_summary dict as a prose chronicle.

    state must be the dict produced by cli.py's game_summary() —
    i.e. the output of `cli.py run` (JSON or parsed).
    """
    battles = state.get('battles', [])

    sections = [
        _title(state),
        _world_intro(state),
        _nations_intro(state, battles),
        _chronicle(state),
        _closing(state, battles),
    ]
    return '\n\n'.join(s for s in sections if s.strip())
