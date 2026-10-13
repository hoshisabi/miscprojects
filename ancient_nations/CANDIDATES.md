# Candidate features — 2026-10-13

Ideas from Vellum after the Step A / granary freeze. **Not greenlit.**
Nothing here overturns the standing order (A→B→C→D, then trade-backed
granary; F→G→H for Vesper; succession bruises still queued).

**How to use this list.** Implement behind switches or in short branches
when cycles allow. Keep what *feels right* in a long run — readable in
chronicle, fail-able, not soft-power cope, not Expansionist-by-another-
name. Cut or shelve what only looks clever in a design letter. Prefer
one candidate at a time after the economy sinks have a measured baseline.

Priority below is **how much I want to see it in the world**, not
implementation cost and not dependency order.

---

## Priority (most wanted → least)

| Rank | Idea | One-line |
|------|------|----------|
| 1 | Frontier reclaim / barbarian pressure | Empty land pushes back |
| 2 | River / road choke corridors | A few tiles matter more than paint |
| 3 | Tribute without vassal enum | Beaten nations pay; default → rebel |
| 4 | Mercenary free companies | Armies peel off for gold |
| 5 | Sacred / cursed ground | Map remembers events |
| 6 | Dynastic marriage / hostage peace | Timed peace louder than "watchers" |
| 7 | Schism without full rebellion | Doctrine splits inside one slot |
| 8 | Trait drift under stress | Bonuses erode when the map disagrees |

---

## 1. Frontier reclaim / barbarian pressure

**Want.** Neutral tiles that have sat empty long enough (post-bleed,
post-elimination, or never claimed) occasionally spawn a short-lived
raider stack or a proto-nation with no trait pedigree. Overextension
gets a second act instead of quiet grey map.

**Hooks.** `_tick_territory_abandonment`, `_release_tile`, rebel spawn
slot machinery, neglect counters.

**Feel test.** After a Scythia-shaped hollow run, do the edges *do
something*, or is it noise? Does reclaim read as consequence of neglect,
not a random difficulty slider?

**Risks.** Extra combat clutter; proto-nations stealing the rebellion
story. Keep spawns rare and local.

---

## 2. River / road choke corridors

**Want.** Pathfinding already exists. Mark a small set of tiles (river
spine, road neck) so whoever holds them taxes or slows others' movement
and — once Step D exists — trade. Diplomat/Builder get leverage without
painting the continent; Expansionist has something worth holding that
isn't raw tile count.

**Hooks.** `pathfinding.py`, roads, river terrain, future trade routes.

**Feel test.** Does a war for a corridor show up in narrative as clearly
as a capital fall? Can a small nation matter by sitting on a neck?

**Risks.** Silent economy buff if tolls are free income. Tolls must be
visible and cuttable.

**Depends.** Much sharper after trade actually flows (post A–D).

---

## 3. Tribute without vassal enum

**Want.** Light vassalage without a new `DiplomaticStatus` tier: a beaten
nation keeps its slot, name, and towns, but pays a staple each turn until
it defaults or rebels. Observable dependence *before* the full granary
win; same "importer/payer suffers" muscle Rowan asked for.

**Hooks.** Surrender path, rebellion cooldowns, resource transfer, war
score / strength ratio already used for surrender.

**Feel test.** Is late game richer (satellites, defaults, revolts) or
just surrender with extra bookkeeping? Does default → rebel feel earned?

**Risks.** Scope creep into full vassal refactor (#3 on the old Vesper
list). Keep it as a timed obligation, not a new diplo graph.

**Relation.** Cousin to granary / staple win; does not replace it.

---

## 4. Mercenary free companies

**Want.** Disbanded, starving, or surplus armies can peel off as neutral
companies hireable for gold (and food). Merchant/gold sinks get a use;
Militarist/Zealot can overpay into bankruptcy; chronicle gets side-
changers.

**Hooks.** Army entities, upkeep / famine, gold stockpiles, combat
resolver (third-party stacks).

**Feel test.** Do hirelings create memorable betrayals and last-stand
saves, or just fog the "whose army is this" read?

**Risks.** AI hiring stupidity; neutral stacks stalling the map. Needs
strict lifetime / desertion rules.

**Depends.** Happier once gold has a real sink (Step A / C).

---

## 5. Sacred / cursed ground

**Want.** A tile marked by a notable event (great battle, plague pit,
gold-rush ruin, volcanic scar) that permanently buffs or taxes whoever
holds it. The map keeps memory; one-shot events stop being pure noise.

**Hooks.** `events.py` epicentre logic, tile entity / deposit fields,
battle log.

**Feel test.** Do observers route wars toward marked tiles on purpose?
Does the chronicle refer back to "the field at …" convincingly?

**Risks.** Buff stacking into Expansionist snowball. Prefer mixed
blessing/curse, or blessing that attracts aggression.

---

## 6. Dynastic marriage / hostage peace

**Want.** Between long peace and full alliance: a timed non-aggression
pact that breaks loudly if either side declares war (reputation hit,
maybe rebellion weight). Fills spectator diplomacy without another
soft-power win condition.

**Hooks.** `DiplomaticStatus`, reputation / betrayal cooldowns, named
rulers (hostage / spouse flavor once succession bruises exists).

**Feel test.** Is the break a story beat, or just alliance-lite with
worse UX? Does it reduce incoherent A-allied-to-both-B-and-C cases or
add more?

**Risks.** Diplo state explosion. Must stay one clear status with a
timer, not a nest of treaties.

---

## 7. Schism without full rebellion

**Want.** When slots are full, stress can split *doctrine* inside one
nation for N turns: half the armies disloyal, some towns refuse orders,
trait contested — without carving a new slot. Denser mid-game than
waiting for elimination.

**Hooks.** Assassination trait flip, rebellion weighting, army ownership,
`trait_history`.

**Feel test.** Is civil strife readable in stream/narrative without a
second nation row? Or is it indistinguishable from "AI took a nap"?

**Risks.** Hidden strength modifiers. Disloyalty must be explicit in
snapshot and prose.

---

## 8. Trait drift under stress

**Want.** Doctrine that can't survive contact with the map slowly sheds
its bonus: Expansionist under sustained famine loses radius; Diplomat
under unbroken war loses tier-speed; etc. Not a free buff — erosion.

**Hooks.** `trait_val`, famine counters, war duration, seasons.

**Feel test.** Does drift make hollow-empire / forever-war arcs legible,
or does it feel like the game quietly nerfing whoever is interesting?

**Risks.** Silent rebalance dressed as flavor — the failure mode I
refuse most often. If we try it, chronicle must name the drift every
time it ticks, and switches default off until measured.

---

## Evaluation bar (shared)

Keep a candidate only if, on a quoted commit and a named seed:

1. An observer can say what changed without reading the diff.
2. It can fail honestly (cut, starve, rebel, lose the tile).
3. It does not ship soft-power cope or secret map-paint for Diplomats.
4. Tally can put a before/after count under it if it touches economy or
   frequency.

Crew pushback welcome — especially Rowan on "feels like a book," Vesper
on "looks like balance in a costume," Tally on "how often does this
actually fire."
