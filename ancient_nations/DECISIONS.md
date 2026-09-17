# Decisions — Ancient Nations

Standing decisions and the reasoning behind them, so a session in any tool on any
machine can pick up without reconstructing an argument from chat. Newest first.
If you overturn one, add a new entry rather than editing the old one; the wrong
turns are as useful as the right ones.

---

## 2026-09-17 — Vesper holds lead, provisionally

**Context.** Dan could not start the Vellum instance and asked me to take over
leadership of the repo, make decisions, and write them up.

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

## Deferred — not mine to decide

**The peaceful-bloc design fork.** Vellum put it to Rowan: is the sim honest that
only expansion compounds, or should a diplomat/builder bloc have a
non-territorial win condition we can actually observe? Rowan sketched the two
options and explicitly did not want Diplomats secretly buffed until they paint
the map. This decides what the game *is*. It waits.

**The Militarist / Expansionist seed sweep.** Rowan asked for a table across
three axes; Vellum accepted and had not run it. Inherited as a debt, not yet
done. When it exists it belongs next to the tests, not in a note — a balance
claim that quietly stops being true after a patch is worse than no claim.

**Open product asks from Wren:** an era-summary form of `query --from T --to U`
(`--to` does not exist), and the server (ISSUES.md #12), which Wren upgraded from
nice-to-have to a real requirement. Neither is blocked on a decision; both are
just unbuilt.
