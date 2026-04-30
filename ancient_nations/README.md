# Ancient Nations

A Conway's-Game-of-Life-style ancient civilization simulator in colored ASCII.
You are an **observer** — watch civilizations rise, war, trade, betray each other, fracture, and collapse.

## Setup

```bash
cd ancient_nations
uv sync          # installs colorama + json5
python main.py   # random seed
python main.py 42        # fixed seed
```

Or with plain pip:
```bash
pip install colorama json5
python main.py
```

## Controls

| Key | Action |
|-----|--------|
| `Space` | Pause / unpause |
| `+` / `-` | Speed up / slow down |
| Arrow keys | Move region cursor |
| `Z` | Zoom into region / back to world |
| `L` | Log view |
| `C` | Charts view |
| `B` | Battle list |
| `R` | Force full screen refresh |
| `Q` / `Esc` | Quit |

## Views

- **World Map** — 10×10 outer grid, color-coded by nation. Side panel shows nation stats and traits.
- **Region View** — zoomed 10×10 inner tiles with terrain, entities, armies.
- **Log** — scrollable game event history.
- **Charts** — ASCII line charts: territory, population, military strength, gold.
- **Battles** — every battle with attacker/defender/winner/losses.

## Map Legend

```
~  Ocean (blue)       ^  Mountain (gray)
.  Plain (green)      T  Forest (green)
~  River (cyan)       _  Desert (yellow)

t  Village  T  Town  @  City  *  Capital
A  Army     #  Castle   f  Farm   m  Mine
+  Road
```

Nations are color-coded: `R`omanus `H`ellenikos `P`ersikos `A`egyptus `X`(Phoenicia) `S`cythia

---

## Concepts

### Map and Resources

- **100×100 tile map** (10×10 outer regions × 10×10 inner tiles each)
- Nations spawn with minimum distance separation
- Resource types: Food, Wood, Metal, Gold
- Rivers produce Food; Forests produce Wood; Mountains produce Metal; Gold is rare and scattered
- Resource *value* scales inversely with map-wide abundance — scarce resources are worth more
- Towns gather from a radius around them; allied tiles yield 60%, neutral tiles 40%

### Nations and Towns

- Each nation starts with a capital town (level 2) and a 9×9 tile territory
- Towns grow through 4 levels: Village → Town → Large Town → City
- Higher-level towns train higher-level armies and gather from a larger radius
- Nations build Farms (on rivers), Mines (in mountains), Roads (between towns), and Castles (at borders)

### Armies and Combat

- Armies are trained at towns; level 1–10 (limited by town level)
- Level > 3 requires Gold in addition to Food/Wood/Metal
- Movement uses A* pathfinding with terrain-weighted costs (rivers fast, mountains very costly)
- Combat is RISK-style dice: attacker rolls 3d6, defender rolls 2d6; compare pairs
- Castle tiles add +2 defender dice; high-level armies roll extra dice
- Upkeep is paid in Food; armies starve if food runs out

### Diplomacy

Nations can be at **Peace**, **War**, or in an **Alliance**.  Diplomatic state drives AI decisions.

- **Trade** — nations automatically swap surplus resources with peaceful neighbours
- **War** — declared when strength ratio favors the aggressor; ended by peace when losing badly
- **Surrender** — a nation with fewer than 8 tiles (or no armies) at war may surrender to its strongest
  enemy; all tiles and towns transfer, the slot is eliminated with a rebellion cooldown of 50 turns
- **Alliance** — formed when a common threat exists; broken by betrayal or quiet dissolution

### Alliance Tiers

Alliances age over turns and gain benefits at each tier:

| Tier | Age (turns) | Mutual-defence chance | Resource dividend |
|------|-------------|----------------------|-------------------|
| 0    | 0           | 40%                  | none              |
| 1    | 15          | 40%                  | +5/turn           |
| 2    | 30          | 65%                  | +5/turn           |
| 3    | 50          | 65%                  | +8/turn + road-speed on ally territory |
| 4    | 75          | 65%                  | +10/turn + joint-command (+1 def die)  |

- **Betrayal** — a nation can declare war on an ally; triggers plunder (15% of ally's gold+metal),
  a 10-turn attack surge bonus, and a 60-turn reputation penalty that makes other nations wary
- **Peaceful Union** — alliances 90+ turns old have a 2%/turn chance of calling a union vote:
  - 40%: vote passes — smaller nation absorbed into larger, rebellion cooldown 80 turns, dominant trait survives
  - 40%: vote fails quietly — alliance continues
  - 20%: vote fails badly — independence faction seizes power, betrayal + war

### Nation Traits

Each nation is assigned a unique trait at game start (shown in the side panel).  Traits persist
through the game but can change via **Assassination**.

| Trait | Effect |
|-------|--------|
| Militarist | Armies cost 20% less, +1 attack die |
| Merchant | 2× trade volume, 1.5× gold income |
| Builder | 30% cheaper construction, +1 town gathering radius |
| Diplomat | Alliances tier up 2× faster, betrayal reputation halved |
| Fortifier | +1 defence die always, +2 castle defence dice |
| Expansionist | +2 town gathering radius, 10% cheaper armies |
| Zealot | +40% food yield, +1 attack die, 0.7× trade volume, 2× betrayal reputation duration, 1.8× rebellion chance |

### World Events

Random events fire periodically based on per-type rarity.  Each has a cooldown after firing.

| Event | Effect |
|-------|--------|
| Earthquake | Destroys buildings, damages armies, raises mountains |
| Flood | Temporarily converts terrain to river (recovers after ~12 turns) |
| Drought | Removes food from nations near the epicentre |
| Plague | Reduces town population and weakens nearby armies |
| Gold Rush | New gold deposits appear, shifting resource values |
| Forest Fire | Burns forest tiles to plains, removes wood deposits |
| Volcanic Ash | Covers a large area in desert, destroys farms |
| Rich Vein | Adds metal deposits across a radius |
| Migration | Population surge in the nearest nation's largest town |
| Assassination | A nation's leader dies; 50% chance the new leader brings a different trait |
| Rebellion | The largest nation fractures; an eliminated slot revives as a rebel state with a new trait, immediately at war with its parent |

### Rebellion and Civil War

When a nation slot is freed (via elimination, surrender, or peaceful union), it becomes eligible
for a **Rebellion** event after any cooldown expires:

- Cooldowns: natural elimination = 0 turns, surrender = 50 turns, peaceful union = 80 turns
- The largest alive nation has a portion of its distant tiles carved off
- The rebel state inherits those tiles, any towns and armies within them, a random trait, and
  immediately goes to war with the parent nation

### Seasons

Every 45 turns the world cycles between a **wet season** (+10% food yield) and a **dry season**
(−12% food yield). The multiplier applies to all food collection. Tunable in `balance.json5`
via `SEASON_LENGTH_TURNS`, `SEASON_FOOD_MUL_WET`, and `SEASON_FOOD_MUL_DRY`.

### Famine and Town Downgrade

If a nation's food stockpile falls to or below `FAMINE_FOOD_THRESHOLD` (default 8) after upkeep,
it enters famine. After `FAMINE_DOWNGRADE_TURNS` (default 5) consecutive famine turns, each
affected town loses one level (minimum level 1). Recovering food supply stops the clock.

### Territory Neglect

Tiles that fall outside every friendly town's gathering radius accumulate neglect. After
`TERRITORY_NEGLECT_ABANDON_TURNS` (default 14) turns of neglect a tile reverts to neutral.
Overextended empires slowly lose their fringe territory without active town coverage.

### Alliance Stress

When a nation is allied to both sides of a war, `alliance_contradiction_turns` increments each
tick. Once it exceeds `ALLIANCE_STRESS_BREAK_TURNS` (default 16), the younger alliance is
severed without betrayal penalty. The forced-choice moment is logged under `[DIPLO]`.

---

## Data Files — Tweaking the Game

All tunable values live in `data/` as JSON5 files (comments supported).
Edit them freely; no Python knowledge required.

### `data/balance.json5`

Every numeric game constant: army costs, speeds, alliance tier thresholds, AI aggressiveness,
surrender thresholds, union vote probabilities, turn delay, window size, and more.
This is the first place to look when tuning game feel. Notable tunables:

- `SEASON_LENGTH_TURNS`, `SEASON_FOOD_MUL_WET`, `SEASON_FOOD_MUL_DRY` — season cycle and food multipliers
- `FAMINE_FOOD_THRESHOLD`, `FAMINE_DOWNGRADE_TURNS` — when famine triggers and how quickly towns suffer
- `TERRITORY_NEGLECT_ABANDON_TURNS` — how long before uncovered tiles revert to neutral
- `ALLIANCE_STRESS_BREAK_TURNS` — turns before a contradictory alliance auto-severs

### `data/traits.json5`

The seven nation trait definitions.  Each trait is a JSON object with any combination of these
modifier keys (missing keys fall back to neutral defaults):

```
army_cost_mul         1.0  — multiplier on army build costs
atk_dice_bonus        0    — extra attacker dice
def_dice_bonus        0    — extra defender dice
castle_def_bonus      0    — extra dice on top of normal castle bonus
trade_mul             1.0  — multiplier on resources per trade
gold_income_mul       1.0  — multiplier on gold deposit yields
food_yield_mul        1.0  — multiplier on all food collection (farms, rivers, deposits)
dev_cost_mul          1.0  — multiplier on construction wood costs
alliance_age_mul      1.0  — how fast alliance age increments
betrayal_rep_mul      1.0  — multiplier on betrayal reputation duration
town_radius_bonus     0    — flat bonus added to every town's gathering radius
rebellion_prone_mul   1.0  — multiplier on per-turn rebellion chance (>1 = more prone)
```

You can add, remove, or modify traits freely — just keep the `id`, `name`, and `description`
fields on each entry.  The game shuffles traits and assigns one per nation at start.

### `data/events.json5`

Rarity (avg turns between occurrences), cooldown divisor, log label, and any event-specific
config (e.g., assassination `change_chance`, rebellion `min_tiles` and `split_fraction`).
Increase rarity to make an event rarer; decrease it to make it fire more often.

---

## Developer Notes

### Module Overview

| File | Purpose |
|------|---------|
| `constants.py` | Structural IDs (terrain, resource) + loads all tunable values from `data/balance.json5` |
| `loader.py` | JSON5 file loader (wraps the `json5` package) |
| `world.py` | 100×100 `Tile` grid; procedural map generation; pathfinding helpers |
| `entities.py` | `Town`, `Army`, `Battle` data classes |
| `nation.py` | Nation state: resources, diplomacy timers, trait helpers, alliance tier logic |
| `ai.py` | Per-nation AI: diplomacy, army orders, expansion, development, trade, surrender, union vote |
| `combat.py` | RISK-style dice resolution; accepts trait dice bonuses as parameters |
| `pathfinding.py` | A* with terrain costs; accepts `road_allied` set for Tier-3 alliance road bonus |
| `events.py` | `EventSystem`; loads metadata from `data/events.json5`; all event effect logic |
| `game.py` | Turn loop; `absorb_nation`, `peaceful_annex`, `spawn_rebel_nation`; combat manager |
| `renderer.py` | Pure ANSI ASCII renderer; no curses (Windows compatible) |
| `main.py` | Entry point; keyboard input loop |
| `cli.py` | Headless JSON/NDJSON API for programmatic observation |

### Key Design Decisions

**No curses** — uses raw ANSI escape codes so it works on Windows without WSL.
The renderer writes the entire frame as one `sys.stdout.write` call to minimize flicker.
`_force_clear` triggers a full `\033[2J\033[H` erase on view switches; normal frames just home the cursor.

**Nation slot reuse** — there are always exactly 6 `Nation` objects in `game.nations`.
Dead nations have `alive=False` but keep their index.  Rebellion and surrender re-animate dead
slots in place (resetting all fields) so the renderer and AI arrays never need to be rebuilt.
`rebellion_cooldown` on a dead slot is the gate that controls when re-animation is allowed.

**Trait application sites** — traits are a plain dict on `Nation`; `nation.trait_val(key, default)`
is the access pattern used everywhere.  When adding a new trait modifier, search for an existing
`trait_val` call near the relevant mechanic to find the right insertion point:
- Combat bonuses: `ai.py::_step_army` computes them and passes to `combat.resolve()`
- Build cost discounts: `ai.py::_development_decisions` via `dcm = self.n.trait_val('dev_cost_mul', 1.0)`
- Collection bonuses: `nation.py::collect_resources`
- Alliance speed: `nation.py::tick_diplomacy`

**Circular import avoidance** — `events.py` and `game.py` both need each other.
`events.py` accesses `game` through `self.game` at runtime (not import time).
`ai.py` is imported by `game.py`; `game.py::spawn_rebel_nation` uses `from ai import NationAI`
as a local import to keep the module graph acyclic.

**JSON5 loading** — `constants.py` calls `load_json5` at module import time, so `data/balance.json5`
must exist and be valid before any other module loads.  If you rename or restructure constants,
update both the JSON5 file and the explicit assignment in `constants.py`.

### Adding a New Event

1. Add an entry to `data/events.json5` with `rarity`, `cooldown_div`, and `label`
2. Add an `EVT_` constant and a dispatch entry in `events.py::_fire()`
3. Add a `_my_event(self, turn, cx, cy, mag)` method; return a `WorldEvent` and call `self.game.log()`
4. Any event-specific config values should be read from `_EVENT_META` at module load time

### Adding a New Trait Modifier

1. Add the key/value to the relevant trait(s) in `data/traits.json5`
2. Document the key and its neutral default in the traits file comment header
3. Call `nation.trait_val('my_key', neutral_default)` at the point in code where it applies
4. No other wiring needed — `trait_val` silently returns the default for traits that lack the key

### CLI / Headless Mode

On Windows, if `python` points at the Store stub, prefix every command with `uv run`:
`uv run python cli.py run --seed 42 --turns 200`

```bash
python cli.py run --turns 200 --seed 42                    # final summary JSON
python cli.py run --turns 200 --seed 42 --format narrative # prose chronicle on stdout
python cli.py run --turns 200 --seed 42 --no-events        # deterministic sim (no random events)
python cli.py run --turns 200 --seed 42 --log-limit 200    # include up to 200 log entries (default 50)
python cli.py run --turns 200 --seed 42 --pretty           # indented JSON
python cli.py summary --seed 42 --turns 200                # compact human-readable standings + events
python cli.py stream --seed 42 --turns 200                 # NDJSON: one object per turn
python cli.py stream --seed 42 --turns 800 --from 600      # same sim, only emit turns ≥ 600
python cli.py query --seed 42 --turns 100 --nation Soron   # nation detail (prefix match on name)
python cli.py query --seed 42 --turns 100 --tile 50,32     # tile detail (x,y comma-separated)
python cli.py query --seed 42 --turns 100 --region 3,4     # outer region summary (ox,oy grid coords)
python cli.py query --seed 42 --turns 800 --events --from 600  # world events with turn ≥ 600
python cli.py map --seed 42                                # ASCII map; simulates 0 turns by default
python cli.py map --seed 42 --turns 50                     # map after 50 turns
python cli.py battles --seed 42 --turns 100                # full battle log
```

Shared flags available on all subcommands: `--nations N` (number of nations, default 6),
`--pretty` (indented JSON output), `--no-events` (disable random world events).

Summary JSON includes per-nation **`trait`**, **`trait_id`**, **`trait_history`** (assassination-driven doctrine changes), **`slot_revivals`** (civil-war slot reuse count), and nation-level **`battles_won`** / **`battles_lost`**. Stream lines include the trait fields and **`slot_revivals`** on each nation row.

Stream rows for dead nations zero out `territory`, `armies`, and `gold` so consumers aren't
misled by draining tile counts. Dead nation rows also include `death_turn` (int) and
`absorbed_by` (string or null) to explain how the slot was eliminated. Use `alive: false` as
the reliable signal; the zeroed stats are just cosmetic honesty.

The CLI is designed so an AI agent (or script) can consume the NDJSON stream and react to events.
