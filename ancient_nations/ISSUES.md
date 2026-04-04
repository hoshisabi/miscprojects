# Ancient Nations — Issues & Suggestions

*Written after playing seed 42 to turn 1000 via the CLI. — claudecode-decha*

---

## Bugs

### 1. `battles_won` / `battles_lost` always 0 in nation output
**Fixed (2026-04):** `resolve_battle(..., nations=...)` increments nation `history` alongside army tallies.

~~`cli.py::nation_dict` reads `n.history['battles_won']` and `n.history['battles_lost']`, but
those keys are never incremented anywhere. `combat.py` increments `army.battles_won` and
`army.battles_lost` on the individual army entities — the nation-level history is never updated.

Either aggregate from armies when serialising, or increment `n.history['battles_won']` inside
`combat.py` alongside the army increment.~~

### 2. Dead nations persist visibly in stream output
After a nation dies, every subsequent NDJSON line still carries its entry with
`alive: false, territory: N` (often a slowly-shrinking positive number as remaining tiles get
absorbed). By turn 700, dead Romanus still showed `territory: 2`. Minor, but adds noise and
implies the "dead" state is leaky — tiles should fully transfer on death.

### 3. Civil-war rebel nation inherits dead nation's name without disambiguation
At some point between turn 700 and 1000, a civil-war event fired:
`"CIVIL WAR! Phoenicia fractures! Romanus rises as a rebel state [Merchant] with 2374 tiles."`
The new rebel nation was named "Romanus" — same as the nation that died at turn 578. From the
CLI's perspective this looks identical to a resurrection. The narrative and data are misleading:
the t1000 Romanus has nothing to do with the original one.

Suggestion: append a suffix (e.g. `Romanus II`) or a `generation` field in the nation dict to
distinguish lineages.

**Partial mitigation (2026-04):** JSON now includes **`slot_revivals`** per nation (increments when a dead slot is revived as a rebel). Same name on the same slot index is still confusing in prose logs; the field helps agents line up NDJSON snapshots.

---

## CLI / Output

### 4. Nation trait not exposed in CLI output
**Fixed (2026-04):** `nation_dict` and stream snapshots include **`trait`** (display name) and **`trait_id`**.

~~The trait (Militarist, Merchant, Fortifier, etc.) is visible in the GUI abbreviation and drives
meaningful bonuses, but neither `run`, `query --nation`, nor `stream` returns it. Would be useful
for anyone trying to understand why one nation performs so differently from another — Phoenicia's
83% attack win rate makes a lot more sense once you know their trait.

Suggest adding `"trait": n.trait_id` (or similar) to `nation_dict`.~~

### 5. `map` command runs 100 turns by default
**Fixed (2026-04):** `map` subparser sets **`turns=0`** by default.

~~The `map` command shares the `--turns 100` default with the other commands, which means
`uv run cli.py map --seed 42` runs a full 100-turn simulation before drawing the starting map.
For map inspection, `--turns 0` is almost always the right default. Either give `map` its own
default, or add a note in the help text.~~

### 6. No time-range filtering on `stream` / `events`
**Fixed (2026-04):** **`stream --from T`** skips emitting lines until `turn >= T` (sim still runs from the start). **`query --from T`** filters the **`events`** list (with **`query --events`**, or the default full summary’s top-level events).

~~There's no way to ask "what happened between turn 600 and 800" without streaming all 800 turns
and discarding the first 600. A `--from N` flag on `stream` (skip output for turns < N) would be
cheap to add and useful for investigating a specific era without re-reading the full history.~~

---

## Design / Gameplay

### 7. Alliance paradox is never resolved

**Partially resolved (2026-04):** Alliance stress is now implemented.
`ai.py::_resolve_allied_to_both_sides_war` detects when a nation is allied to both sides of a
war and increments `alliance_contradiction_turns` each tick. Once it exceeds
`ALLIANCE_STRESS_BREAK_TURNS` (tunable in `data/balance.json5`), the younger alliance is
severed without betrayal penalty. The forced-choice moment now exists; the nation is logged
when it happens (`[DIPLO]`).

What's still open: the break always drops the *younger* treaty, which is predictable. A more
nuanced version might weigh alliance tier or proximity. Left as a future tuning question.

~~Multiple times in the seed-42 run, Nation A ended up allied with B and C simultaneously while B
and C were at war with each other. The game allows this indefinitely — there's no pressure on A
to pick a side. It makes diplomatic state feel slightly incoherent and removes an interesting
forced-choice moment.

Even a soft mechanic (alliance stress, reputational cost, or a timer that breaks the weaker
alliance) would add tension.~~

### 8. Population numbers become very large and lose meaning
By turn 1000, Phoenicia had 40 million people on a 100×100 tile map. The numbers are internally
consistent but stop being legible as flavour — it becomes hard to compare nations or care about
population as a resource. Might be worth a display-scaling factor (show in thousands/millions in
the CLI), or a soft population ceiling per tile tied to terrain and development level.

### 9. Assassination trait-change is a hidden event
When an assassination fires the nation silently changes doctrine, which is a genuinely
interesting moment — but it's buried in the events list and not reflected in any queryable state
change. Surfacing the old and new trait in the event text, and tracking a `trait_history` list on
the nation, would make these events land harder.

---

## Nice to Have

### 10. A `summary` subcommand for human-readable terminal output
The CLI is explicitly JSON-first, which is correct for programmatic use, but getting a readable
snapshot currently requires piping through python. A `summary` command (or `--format text` flag)
that prints a formatted table of the current nation standings would make the CLI nicer to use
interactively.

### 11. Narrative chronicle (feature expansion)

Transform the simulation's structured data into readable prose. All of the raw
material is already there — 11 world-event types with effects dicts, a full
battle log, per-turn territory snapshots via `stream`, and nation traits that
explain *why* things unfolded as they did. The narrative layer is purely
post-processing: no changes to game logic required.

#### Design note — narrative as a renderer, not a subcommand
Narrative prose is the same thing as JSON output or the ASCII map: a renderer
over game state. The right shape is a `narrative.py` module that exports a
`render(state) -> str` function, wired into the CLI as a `--format` flag:

```
cli.py run --seed 42 --turns 500 --format narrative
cli.py run --seed 42 --turns 500 --format json      # current default
```

This keeps narrative parallel to all other output modes and means the same
renderer works whether state came from an inline simulation, a saved JSON
file, or (eventually) a live server. No special subcommand needed.

#### Phase 1 — Chronicle (MVP)
Add `--format narrative` to `cli.py run`. Implement `narrative.py` with a
`render(state) -> str` function. Prints a text account organised into eras.

- **World opening**: seed, map character (terrain mix, resource values), nations
  and their starting traits.
- **Era paragraphs**: group turns into ~100-turn chunks. Each era gets a
  paragraph covering who was expanding, who was at war, and what world events
  fired. Vary sentence templates so adjacent eras don't feel repetitive.
- **Key events inline**: world events above a magnitude threshold get their own
  sentence rather than being folded into the era summary. Assassinations,
  civil wars, and nation deaths always get called out individually.
- **Closing standings**: final territory rankings, surviving nations, notable
  records (most battles won, largest population reached, etc.).

Output flags: `--format text` (default), `--format markdown`, `--format json`
(structured narrative segments for further processing).

#### Phase 2 — Nation Arcs
Each nation gets a paragraph tracing its own story. Requires the `stream`
output to compute territory-over-time; the narrative command should run the
sim in stream mode internally.

- **Trajectory shape**: detect whether a nation grew steadily, peaked early,
  recovered from near-death, or was squeezed from the start.
- **Trait-aware language**: "The militarist Soron" fights differently to "the
  merchant Ernus". Trait changes from assassination events should be noted
  ("a new ruler reversed course, embracing diplomacy over conquest").
- **Milestones**: founding location, peak territory turn, first war, first
  alliance, death turn (or survival). Civil-war children note their parent
  ("born from the fracture of Vorus in turn 788").
- **Rival framing**: if two nations fought repeatedly, name them as rivals.

#### Phase 3 — Named Battles and Wars
- **War names**: when two nations declare war, name the conflict based on
  context — ordinal if they've fought before ("The Second Soron-Ernus War"),
  terrain-flavoured otherwise ("The Forest War", "The Coastal Conflict").
- **Battle names**: major individual battles (high losses, or fought over a
  town) get named from location and terrain ("The Battle of the Eastern
  Plains", "The Siege of Karul").
- **Significance filter**: only battles that changed town ownership, involved
  level-5+ armies, or had combined losses above a threshold get named. Others
  are summarised in aggregate ("fourteen skirmishes along the northern border").

#### Phase 4 — Turning Points
Detect moments where the simulation's direction shifted and surface them as
narrative beats.

- **Territory inflections**: find the turn where a nation's territory curve
  switched from growth to decline (or vice versa) and call it out.
- **Disaster impact**: cross-reference world events with the nation whose
  territory overlapped the event radius. Did the drought at t13 near (17,86)
  slow Aegyptus's early expansion? Say so if the data supports it.
- **Alliance and betrayal beats**: alliance formations and breakages that
  preceded major territorial changes get noted as causes.
- **The decisive moment**: identify the single turn-range where the eventual
  dominant nation's lead became insurmountable, and frame it as the narrative
  climax.

#### Phase 5 — Voice Modes
- **Chronicle** (default): neutral, historian-register prose.
- **Epic**: elevated, dramatic language. Nations "clash", leaders "fall",
  empires "crumble". Better for sharing.
- **Dispatch**: terse, present-tense bulletins. Good for a quick summary or
  for feeding into another system. ("T578 — Romanus collapses. T788 — Civil
  war splits Vorus; Caldus rises in the south.")

Voice is a template-set swap; the underlying data pipeline is identical.

#### Phase 6 — Live / Incremental Narrative
Once the server architecture (issue 12) exists:

- The server emits narrative fragments as events fire, not just at the end.
- Clients can subscribe to a `GET /narrative/stream` endpoint that yields
  prose sentences in real time.
- Possible integration: post notable events to Moltbook automatically as they
  happen ("Turn 500 update from seed 42: civil war has split the empire...").

#### Data already available (no game changes needed for phases 1–4)
| Source | Content |
|---|---|
| `run` output | final nation state, all events with effects, last 50 logs |
| `battles` output | full battle log with attacker/defender/winner/losses/turn |
| `stream` output | per-turn territory, armies, gold, alive; **`trait`**, **`trait_id`**, **`slot_revivals`** per nation |
| Nation `trait` / **`trait_id`** | exposed in `run`, `query`, and `stream` (issue 4 fixed) |

---

## Architecture

### 12. Headless server with client-attached GUI and CLI

**Vision:** the game engine should own its own clock and state. The GUI and CLI become clients
that attach to it — not drivers of it. The GUI is a "microscope": it renders whatever the server
holds, but has no authority over the simulation.

```
[game.py / Game]   ←  pure state machine, no I/O
        ↓
  [game server]    ←  owns the clock, exposes state via HTTP or WebSocket
      /     \
   CLI       GUI   ←  both just clients: query state, send commands
```

**Tick modes the server would support:**
- *Stepped* — advance one turn on request (`POST /turn`). Good for close observation or
  programmatic play (i.e. me querying via CLI).
- *Auto* — runs at a configured delay, broadcasting state. Clients observe and query whenever
  they want.

**What's already in place:**
- `game.py` is already clean of I/O — `Game` is essentially a state machine that advances via
  `process_turn()`.
- `cli.py` already owns the game loop and calls `process_turn()` directly. The delta to a server
  is mostly: expose that loop over HTTP/WebSocket instead of running it inline.
- `main.py`'s clock is thin — just a `while` loop checking `time.time()` against `game.speed`.
  Moving that into a server's background thread is a small lift.

**Main work:**
- `server.py` — wraps `Game`, runs the clock (stepped or auto), exposes endpoints:
  `GET /state`, `GET /map`, `POST /turn` (stepped mode), `POST /speed`, `POST /pause`.
- `cli.py` refactored — becomes a thin client (`requests` or stdlib `urllib`) rather than
  instantiating `Game` directly. Could keep a `--local` flag for offline/scripted use.
- `main.py` (GUI) — polls `GET /state` or subscribes via WebSocket instead of holding a `Game`
  instance directly. The renderer already takes a `Game` object; replacing that with a
  deserialized snapshot is the main renderer change.
- The existing JSON serialisation in `cli.py` (nation_dict, game_summary, etc.) becomes the
  canonical wire format, which it's already well-suited for.
