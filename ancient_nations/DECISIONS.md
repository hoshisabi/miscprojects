# Decisions — Ancient Nations

Standing decisions and the reasoning behind them, so a session in any tool on any
machine can pick up without reconstructing an argument from chat. Newest first.
If you overturn one, add a new entry rather than editing the old one; the wrong
turns are as useful as the right ones.

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
Still needs a concrete observable before code. Dan's soft-power veto stands.

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
