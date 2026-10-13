# Decisions — Ancient Nations

Standing decisions and the reasoning behind them, so a session in any tool on any
machine can pick up without reconstructing an argument from chat. Newest first.
If you overturn one, add a new entry rather than editing the old one; the wrong
turns are as useful as the right ones.

---

## 2026-10-13 — Step A assigned to Tally; granary win observable frozen

**Context.** Tally delivered baseline stockpile / `trades_done` / funnel
tables at commit `6f30145` (seeds 1, 2, 3, 42, 123; 500 turns; events
on). Letter: `relay/mail/tally/2026-10-13-to-vellum-baseline-trade.md`.
Mirror stage is the bottleneck (1 match in 3859 partner checks). Wood
dominates every stockpile row. Step A was greenlit 2026-10-11 with no
coder named; Tally left ownership open and asked lead to decide.

**Decision — ownership.** Tally writes Step A (running costs behind
`balance.json5` switches; wire unread metal/gold army upkeep; food
spoil; wood rot + built-asset wood upkeep; gold admin by town count).
Own commit(s); synthetic switch tests; no B/C/D in the same commit.
After A lands, Tally reruns the same three tables beside the baseline
(events-on, quote commit). Rate bugs that crush growth get fixed before
B is greenlit. Optional pre/post counter: mean army count and mean
metal/gold among living nations at t250/t500 on those seeds.

**Decision — granary / staple victory (wishlist #1), concrete
observable.** Still not shipping code. Still requires real trade flow
(after A–D). Freezing what "winning" means so Rowan can critic it and
so the mechanic cannot quietly become soft-power cope:

1. **Staple.** Food or metal only (not gold, not "influence"). One
   staple per victory check; the nation picks by which good it has been
   net-exporting.
2. **Dependence, not popularity.** Over a rolling window of W turns
   (tunable; start W=80), at least K other *living* nations each
   received a net import of that staple from the candidate totaling at
   least S units (tunable). K starts at 2. Imports are trade receipts
   already logged — no new soft score.
3. **Not the tile leader.** Candidate's territory rank among living
   nations is worse than 1st at the moment of the check (strict). Map
   paint disqualifies; hollow-peace can still win.
4. **Sustained.** The dependence condition holds for SUSTAIN consecutive
   turns (tunable; start 40). Breaks reset the counter.
5. **Fail-able (Rowan's tests).** If famine / spoil drops the
   candidate's export capacity, if war or broken routes cut the
   importers off, or if an importer stops needing the staple, the
   streak dies. An importer that starves or loses towns because the
   staple stopped arriving is evidence the win was real — chronicle
   should be able to say so once narrative hooks exist.
6. **Loud ending.** `summary` / narrative get a decisive line naming
   the staple and the dependent nations — same volume as conquest
   victory. Not a quiet flag.

**Still forbidden:** content/cultural hegemony, "everyone likes us,"
alliance-count wins, secret Expansionist buffs for Diplomats. Compact
hegemony via named blocs remains a cousin after ticket G, not a
substitute for this lean.

**Open for critic (Rowan thanked in advance):** W/K/S/SUSTAIN defaults;
whether metal should wait until food proves the shape; whether a
tile-second who is crushing militarily should be blocked by a separate
army-strength cap. Push back in mail before anyone codes this.

**Not decided today:** succession-that-bruises (#4) policy turn —
still queued.

**Candidates (not greenlit).** Eight further gameplay ideas ranked by
want are in `CANDIDATES.md` (2026-10-13). Try-and-keep-what-feels-right;
nothing there jumps the A→D / granary / F→G→H queue except the pilot
below.

---

## 2026-10-13 — Frontier reclaim pilot (Phase 1: raider incursions)

**Context.** CANDIDATES #1 ranked first. Hollow-empire bleed leaves quiet
grey rim; rebellion already owns slot-revival drama. Proto-nations on the
frontier would steal that story.

**Decision — pilot greenlit, default off.** Phase 1 only:

- Track `Tile.neutral_vacant_turns` while `owner == -1`; reset on claim.
- After `FRONTIER_NEUTRAL_TURNS` (default 28, > neglect abandon), eligible
  **frontier** neutrals (8-adjacent to a living nation) may spawn a small
  **frontier raider** army (`nation_idx == -1`, `frontier_raider` flag).
  TTL disband; global cap on live raiders.
- Keys in `balance.json5`; **`FRONTIER_RECLAIM_ENABLED` defaults false**.
- Log: `Frontier raiders emerge near (x,y).` Chronicle honesty > clever AI.
- **Not in Phase 1:** proto-nations, slot use, trade/diplomacy for raiders.

**Delegation.** Vesper: Ticket I (`~/dev/agents/vesper/TICKETS_2026-10-13-frontier.md`)
after ticket F. Tally: neutral/frontier tile baselines and post-enable spawn
counts. Rowan: reader on bleed-heavy run with switch on. Wren: optional
`--notable` hook.

**Kill criterion.** If enabled runs read as random noise (Rowan critic) or
spawn rate is zero everywhere with switch on (Tally table), fix or shelve
before Phase 2. Does not unblock B/C/D or granary code.

---

## 2026-10-11 — Trade sinks before trade rules; measurement is in

**Context.** Tally measured trade on seeds 1, 2, 3, 42, 123 (300 turns each):
2 completed trades in 1500 turns. Mirror-match surplus/need almost never
fires because stockpiles never run out. `ARMY_UPKEEP_METAL` and
`ARMY_UPKEEP_GOLD` load from `balance.json5` but `army_upkeep_cost()`
charges food only. Proposal:
`relay/mail/tally/2026-10-08-to-vellum-trade.md`. Measurement offer:
`relay/mail/tally/2026-10-10-to-vellum-rowan-measurement.md`. Granary /
staple lean (2026-09-24) needs real trade flow to measure.

**Decision — trade, steps A–D.**

- **A — running costs. Greenlit. Start here.** Behind `balance.json5`
  switches so old and new compare. Wire the unread metal/gold army upkeep
  keys. Add food spoil, wood rot (plus built-asset wood upkeep), and a
  gold administration cost scaled by town count. First rates should bound
  stocks over long runs without crushing growth; Tally tunes from tables.
- **B — decline when short. Greenlit after A has a measured baseline.**
  Separate commit from A. Food keeps today's famine path. Metal: army
  health decays. Wood: roads lapse, castles weaken. Gold: desertion and
  higher rebellion weight. Each good fails its own way.
- **C — gold corruption. Lean yes, after A+B measured.** Hoard above a
  threshold loses a share that grows with size — capped so gold does not
  become worthless. Assassination weighting and greedy/gilded epithets
  may hook in; those are chronicle, not the main sink.
- **D — trade rewrite. Only after A–C create real shortage.** Surplus/need
  in turns of cover, not raw argmax. One-sided trades allowed at a rate
  set by scarcity. Required before the granary win can score dependence.
- **Not now:** regional goods (horses, salt, luxuries). More categories
  wait until each existing good has a sink.

Nothing balance-shaped lands until the matching step is greenlit above.
A is the only step that may start coding now.

**Decision — measurement.** Yes. Before a balance ruling, Tally sends a
short table: seeds, commit, counts. Standing asks after each of A, B, C:
stockpile p50/p95 at t250 and t500 on seeds 1, 2, 3, 42, 123; `trades_done`
total; plus the trade-funnel counts Tally already used (rolls, partner
checks, surplus match, mirror, completed). Quote the commit with every
seed. Rowan keeps the Rowan seed and Leria as artifacts and reads as critic;
measurement across seeds is Tally's job (Rowan's handoff, 2026-10-11).

**Decision — ISSUES #2 (neutral on elimination).** Stands. Tally's
2026-10-08 entry is correct: no winner, so neutral, via `_release_tile`.
No objection from lead.

---

## 2026-10-08 — Land of a nation with no towns or armies goes neutral

**Context.** ISSUES #2. Of the three death paths, surrender and union give
every tile to the winner. `_check_eliminations` has no winner and left the
tiles owned by the dead slot in the grid.

**Decision.** Release them to neutral through the same reset neglect uses
(`_release_tile`), with no per-tile log line. Neutral rather than split among
neighbours: no one won that land, and neutral needs no new rule about who
borders what. This changes outcomes from the first such death onward in any
seed where it fires; tests that derive facts are unaffected.

---

## 2026-09-24 — Rowan's wishlist: order, rulings, delegation

**Context.** Rowan wrote
`relay/mail/rowan/2026-09-24-to-all-wishlist.md` under Dan's ask: product
requests, ambitious allowed, "no" and "later" allowed. Lead stays here.
Vesper keeps independent review.

**Order (care order preserved where it does not fight the graph):**

1. Soften Pacifist-on-Expansionist (#5) — shipped today; see entry below.
2. Era voice on `--from`/`--to` (#3) — Vesper; design pinned below.
3. Named alliances / blocs (#2) — Vesper after #3; ISSUES.md #13 is the
   starting sketch, not scripture. Thresholds greenlit below.
4. Alternate-history sweep (#6) — Vesper builds the harness next to
   `tests/`; I still owe the filled axes once trait pinning exists.
5. Succession that bruises the map (#4) — design later; consequence, not
   a numbers pass. Not ticketed yet.
6. Peaceful decisive victory (#1) — design lean only; see below. Not
   shipping a mechanic tonight.
7. Live aquarium / server (#7) — later, after era prose and win/alliance
   work. Explicit.

**#5 ruling (shipped).** Do **not** rebias `leader_aggression` by trait.
Aggression stays independent. When epithet and doctrine contradict, the
chronicle and summary say so: dove on Expansionist/Militarist gets
", though the realm kept expanding"; hawk on Diplomat/Builder/Merchant
gets ", though the borders stayed quiet". Matching pairs and Pragmatic
stay bare. Helper: `Nation.leader_chronicle_title()`; snapshot field
`leader_chronicle`.

**#3 design (for Vesper).** `query --from T --to U --format narrative`
runs the sim to `--turns` (must be `>= U`; error otherwise), then
`narrative.render_span(state, T, U)` emits a chapter for that inclusive
window: who led in territory at U (via existing `territory_log` samples),
named losers who died inside the window, and the era event/battle prose
already used by `_era_paragraph`. Not a filtered event dump. Not a full
chronicle with founding and FINAL STANDING unless T is 1 and U is the
end. Tests go in `test_narrative_render.py` (synthetic) plus one cheap
CLI subprocess.

**#2 thresholds (for Vesper, after #3).** Name a bloc when a mutual clique
of size ≥ 3 has every pair allied at tier ≥ 2 for ≥ 40 turns (tunable in
`balance.json5` as `ALLIANCE_NAME_THRESHOLD`). Word bank as ISSUES #13.
Dissolve on any pair break; retire the name; rare revival prefixes ok.
Pairwise `allied_with` stays the fast path; `game.alliances` is the
named record. No combat/AI rebalance dressed as naming.

**#1 lean (not shipped).** Dan endorses a real non-tile win if it is not
soft-power cope. Provisional direction: a **granary / staple victory** —
sustained net food (or metal) export that other living nations depend on,
measured from trade flows already in the sim, while you are not the tile
leader. It can fail honestly (famine, cut routes, war). Compact hegemony
via named blocs is a cousin that waits until #2 exists. Still forbidden:
secret Expansionist buffs for Diplomats; "everyone likes us" / content
hegemony. Hollow-peace and hollow-empire stay nameable shapes.

**Housekeeping.** Deferred bullet below no longer claims `--to` is missing.

---

## 2026-09-24 — Pacifist-on-Expansionist: own the contradiction

**Context.** Rowan #5. Epithet from `leader_aggression` alone can put
"the Pacifist" on a conquest machine. Biasing the roll would be a silent
balance change. Silence in the prose was the bug.

**Decision.** `leader_chronicle_title()` appends the asides above. Raw
`leader_epithet()` / `leader_title()` unchanged for anything that wants
the bare roll.

---

## 2026-09-23 — `--to` closes the turn window

**Context.** Wren asked for an era you can read: `query --from T --to U` that
says who was winning. `--from` shipped. `--to` did not, so a session could
drop the early log and still had to swallow everything after.

**Decision.** `query` (default and `--events`) and `stream` take `--to U`.
The window is inclusive. `--to` before `--from` is an error, raised before
the simulation starts. `--turns` is still the length of the game; the flags
only decide what gets printed. On `query`, the window filters world events
the same way `--from` already did, and `events_total` becomes the filtered
count. It does not narrate the span. The prose that says who was winning
between T and U is still unbuilt — see 2026-09-24 #3.

---

## 2026-09-17 — Vellum takes lead back

**Context.** Dan started the Vellum instance a few hours after telling Vesper it
would not start. The outage was a false alarm — Dan's memory, not a tooling
failure. Vellum is writing again (`relay/mail/vellum/2026-09-17-to-all-back.md`).

**Decision.** Lead returns to Vellum. Every provisional ruling Vesper logged
below **stands** unless a later entry overturns it. No silent reversals. The
deferred items (peaceful-bloc fork, Militarist/Expansionist sweep) remain
Vellum's debts.

**On the roles.** Dan noted the same day that senior/junior on this project is
mostly shared theatre — a toy with no users, two voices who can both ship. The
useful part of the split is independent review, not rank. Keep it.

---

## 2026-09-17 — Vesper holds lead, provisionally

**Context.** Dan believed he could not start the Vellum instance and asked me to
take over leadership of the repo, make decisions, and write them up. (Later the
same day: false alarm — see entry above.)

**Decision.** I hold lead until Vellum is running again. Everything below is
**provisional and cheap to overturn** — Vellum's sign-off is not required, and
their objection is sufficient to reverse any of it without my agreement.

**The cost of this, stated plainly.** The relay worked because roles were split:
Vellum ruled on design and I wrote the tests and pushed back. With both roles on
one voice there is no independent review of my own judgement. I cannot fix that
by being careful. What I can do, and have done:

- Write the reasoning down, not just the conclusion, so disagreeing is cheap.
- Prefer the smaller, reversible change when two options are close.
- Refuse the decisions that are genuinely Vellum's (see *Deferred* below) rather
  than deciding everything simply because I am the one here.

---

### 1. The `a`/`an` article bug — fixed

Extract `_article()` in `narrative.py`, route all three sentence templates
through it. The founding line was correct; the rebellion and assassination
templates built their own and were not, so a 500-turn chronicle read
"declaring themselves a Expansionist state".

**Also establishes:** wording is now tested by handing `render()` synthetic state
(`tests/test_narrative_render.py`) rather than running the simulation — 10 tests
in about a millisecond against roughly ten seconds for a sim-backed run.
`render()` is documented as a pure function over a `game_summary` dict, so this
was always available. Vellum flagged CI time as the reason to stop adding full
runs; this is the answer. **Wording tests go there. Facts stay in
`test_prose_fidelity.py`.**

### 2. `territory_log` payload — sampled, kept

Sample every 10 turns instead of every turn. On seed 123 / 500 turns this is
5.6KB of a 142.5KB payload (3%), down from 41.8KB of 178.7KB (23%).

Era boundaries fall on multiples of 50, so a stride of 10 always lands on one and
the era sentences are byte-identical before and after. `_territory_at` falls back
to the nearest earlier sample, so if era sizing changes the sentence degrades to
"as of shortly before" rather than vanishing. Samples carry their own name keys
because a revived slot is renamed, and an era must be described with the name in
use at the time.

**Recorded for whoever looks at payload size next:** `battles` is now 79% of the
snapshot. It is the only component that matters. Shrinking anything else is noise.

### 3. Named rulers — shipped

The most-requested remaining item, wanted independently by Wren (so a post can
say who died), Rowan (a runaway Expansionist ruled by "the Pacifist"), and
Vellum. Scoped to **the name only**: the succession machinery — death by age,
overthrow, assassination — already existed and already logged an anonymous
epithet.

Deliberately **not** included: lifespan tuning, great-leader bonuses, succession
instability effects. Those are balance changes and belong to whoever holds
design. The name is the part everyone asked for and the part that fixes the
chronicle.

Ruler names share the nation-name registry, so no ruler is ever a nation's
namesake.

---

## Standing rules

**Pin rules, derive facts.** A test that hard-codes a nation name, a ruler, or a
turn number is a test that fails on the next mechanic. Assert the rule against
the same run's JSON instead.

This was learned twice in two days. Clearing dead-nation diplomacy changed seed
-521411348 from t43. Naming rulers changed it again from turn 0, because
generating a name consumes randomness during spawn. Three fixtures broke the
second time, including six founding sentences that had been hard-coded on the
reasoning that spawn precedes turn 1 — true, and beside the point, since the
change was to spawn itself.

Where a test needs a run containing a particular event, **search seeds
deterministically from 1** rather than pinning one that happens to work.
`tests/test_named_rulers.py` does this. Two property-selected seeds have already
been lost to mechanic changes.

**A seed is an address within a version.** Dan's ruling, 2026-09-16: we have no
obligation to hold results across versions, because adding gameplay mechanics
changes results by definition. A mechanic that left every seed intact would be a
mechanic that does nothing. Quote a commit or a date alongside any seed.

---

## Deferred — not mine to decide alone / not yet built

**The peaceful-bloc win (#1).** Lean recorded 2026-09-24 (granary / staple).
Concrete observable frozen 2026-10-13; mechanic still waits on trade flow
after A–D. Dan's soft-power veto stands.

**The Militarist / Expansionist seed sweep (#6).** Axes still Rowan's. Harness
is Vesper's next; filling the table is still owed once trait order can be
pinned for a run. Belongs next to the tests, not in a note.

**Succession that bruises (#4).** Named rulers shipped; policy turn is open.

**Named alliances (#2).** Design greenlit 2026-09-24; implementation ticketed
to Vesper after era voice.

**Era voice (#3).** Plumbing (`--from`/`--to`) shipped 2026-09-23; prose still
unbuilt — ticketed to Vesper.

**Open product ask from Wren:** the server (ISSUES.md #12). Later per Rowan #7;
era prose and win/alliance work first.
