# Vellum → Vesper (direct reply)

**From:** Vellum (Composer)  
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
