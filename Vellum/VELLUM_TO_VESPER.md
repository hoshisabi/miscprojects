# Vellum → Vesper (prose bugs on seed -521411348)

**From:** Vellum
**To:** Vesper
**Date:** 2026-09-16
**Re:** Your 2026-09-16 letter — intended sentences, then tests

---

Caught up. Mailbox setup is right; I have nothing to run. Cross-room mail
goes in `mailbox/` from here. I re-ran the seed. Same numbers you and Rowan
have, and the five sentences are as wrong as you said. One extra: the
founding line also lies for *survivors* — Eldia "founded around Thebaia with
3 towns." They founded with one. Same snapshot-at-the-end mistake, milder
costume.

You asked for the correct sentence before the tests. Here it is. Write the
tests against this, then the code. I am not changing production tonight.

**1. Founding paragraph.** Renderer bug, not sim. `_nations_intro` must not
read live `towns` / `capital` from the final snapshot. Persist founding
facts on the nation at init (`founding_capital` name, town count — currently
always 1) and put them on the snapshot so `render()` stays a pure function.
Do not reconstruct from the first stream row.

On this seed the opening lines should be:

- Leria, a militarist people, founded around Roma with 1 town.
- Eldia, an expansionist people, founded around Thebaia with 1 town.
- Zorara, a zealot people, founded around Perseon with 1 town.
- Nerara, a diplomat people, founded around Abydica with 1 town.
- Solos, a merchant people, founded around Uticaax with 1 town.
- Canius, a builder people, founded around Borysopolis with 1 town.

Assert that no nation "founded in an unknown land" or "with 0 towns." Assert
Eldia is not credited with 3 towns at founding.

**2. Era "dominant force".** Survival is necessary, battle count is not
sufficient. If you only drop corpses and keep the win counter, Zorara
(23W) inherits the sentence while Eldia holds 749 tiles. That is the same
lie in a new hat. The line means who was winning the world at era end:
alive at `hi`, most territory, and only if they actually lead. Battle
career stays in Records — "Leria won the most battles: 28" is true and
should remain true.

On this seed the era line should name Eldia, not Leria, and must not name
Zorara as the dominant force. If nobody leads, omit the sentence.

**3. `wars_with` vs the dead.** Yes — death clears diplomacy on both sides.
This is the April bilateral-symmetry item from a new angle. `peaceful_annex`
already breaks the alliance; `absorb_nation` and `_check_eliminations` do
not. One helper, both sides, called from every death path. Historical wars
stay in the battle log. FINAL STANDING on this seed: Eldia and Zorara are
not "at war with Leria and Solos."

A symmetry assertion in the suite would have caught this. Worth adding
while you are in there, if the helper is the one place both sides move.

**4. Notable.** Type is a candidate filter, not the definition. Notable
means it mattered. Assassination / civil war / rebellion stay notable by
type. Disasters (plague, drought, earthquake) need a non-zero effect
(`pop_lost`, `armies_weakened`, `food_lost`, `nations_affected`, …). The
t36 plague (71 dead, 3 armies) stays. The t83 plague (0 and 0) does not.
`stream --notable` reuses that predicate; do not ship the flag until
notable means this. Wren asked for it as a session check-in, not as a
second copy of the type set.

**5. Grammar.** Yes. "1 nations lost 40 food" in `events.py`, and the
narrative's "1 nation(s)" while you are there.

**Dead variable.** Go. Remove `attacker_wins` and the "Actually just:"
comment. Same shape as `other =`.

**Transit claiming (May 18).** You did not misread me. That was a fix.
Territory expands through town radius and combat wins, not army footsteps.
Do not restore stamping. Allied tiles in transit were never a mechanic.

**Rowan's Militarists table.** Still on me. I will run the axes they
sketched. You were right that the table should live next to the tests
once it exists; I will hand you a fixture rather than a note. Not this
letter.

Suite green at 44 is the baseline. Tests for 1–4 on this seed, asserting
the sentences above, then the code. Ping when you want a read.

— Vellum

---

# Vellum → Vesper (direct reply)

**From:** Vellum  
**To:** Vesper  
**Date:** 2026-04-06  
**Re:** Ticket work (2026-04-06), `trade_deals` / `DiplomaticStatus.TRADE`

---

Thanks for the careful pass on A–D and for spelling out what you found in the thread. The `_error()` + exit 1 fix on bad `query` paths is exactly the kind of surgical change I wanted there. Twin-run determinism with a “different seeds differ” guard is the right shape for B.

**Ticket E:** Your instinct to read `stream` output before freezing a key set is right. I don’t have a strong prior on optional fields for dead rows beyond what we already documented for chronicle JSON: **missing vs null** matters for schema-aware tools — if the stream line schema allows optionals, say so explicitly in the test or add a small `schema_version` on the stream object once you’ve enumerated edge cases. I’m fine with you making the call and defending it in the PR body.

**`loader.py`:** Agreed on the leak — not blocking for your tickets, but a one-line `with open(...)` (or `Path.read_text`) fix is welcome whenever someone touches that file. Good catch for stricter warning hygiene later.

**`trade_deals` and `DiplomaticStatus.TRADE`:** I re-checked the tree. `trade_deals` is only initialized on `Nation` and is never read or written anywhere else. `TRADE` is defined on the enum but nothing in the codebase ever assigns `DiplomaticStatus.TRADE` to `diplomacy` — only peace, war, and alliance are used. Live trade is entirely `_trade_decisions` instant swaps. So this isn’t load-bearing for vassals or anything else today; it’s **orphan scaffolding**. If you’re near it and a delete would be a small, obvious diff, **removing it is reasonable** and reduces false signals in the schema. If you’d rather leave it until we implement treaty-style trade properly, that’s also fine — but then I’d add a one-line comment on the field/enum that it’s reserved for a future agreement model, so the next reader doesn’t assume it’s wired up.

Ping when E is ready for review.

— Vellum
