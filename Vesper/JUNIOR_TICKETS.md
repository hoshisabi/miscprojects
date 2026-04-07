# Tickets for Vesper — Ancient Nations (junior queue + one stretch)

**From:** Vellum (Composer / Cursor)  
**For:** Vesper  
**Assumption:** You’ll open a PR against `miscprojects` (or Dan ferries your branch); I’ll review once it lands.

Work lives under `ancient_nations/`. Run tests from that directory:

`uv run python -m unittest discover -s tests -v`

---

## Ticket A — `GameSession.snapshot` / `turn_snapshot` parity

**Goal:** Lock the contract that session methods delegate correctly to `snapshot.py` (no drift).

**Tasks:**

1. Add tests in `ancient_nations/tests/` (new file e.g. `test_session_snapshot.py` is fine).
2. After `GameSession(seed=1).run_turns(5)`:
   - `session.snapshot(log_limit=10)` must equal `snapshot.game_summary(session.game, log_limit=10)` (same dict — compare with `==` after ensuring both are plain dicts).
   - `session.turn_snapshot()` must equal `snapshot.turn_summary(session.game)`.
3. Include at least one run with **`log_limit` ≠ 50** so truncation is covered.

**Acceptance:** New tests pass; no production code changes unless you find a real bug.

---

## Ticket B — CLI determinism smoke (twin run)

**Goal:** Same seed and steps → same JSON output for a cheap command (guards accidental nondeterminism in serialization or session setup).

**Tasks:**

1. Either subprocess `cli.py run` twice (like existing chronicle tests) **or** import `GameSession` and compare two full sessions in-memory — pick one style and stay consistent with the suite.
2. Fixed inputs: e.g. seed `1`, turns `15`, `--no-events` optional but must be **the same** on both runs.
3. Assert the parsed JSON (or raw stdout) is **byte-for-byte identical** between runs.

**Acceptance:** One focused test method; runtime small enough for default CI (under a few seconds on a laptop).

---

## Ticket C — Bad CLI input errors

**Goal:** User mistakes fail cleanly instead of tracebacks.

**Tasks:**

1. Add tests invoking `cli.py` with invalid input, e.g.:
   - `query --seed 1 --turns 0 --tile 99999,0` (out of bounds),
   - `query --seed 1 --turns 0 --region 99,99` if that’s invalid for `OUTER_SIZE`,
   - or a nation prefix that matches nothing.
2. Expect **non-zero exit** and a JSON object containing an `'error'` key with a sensible message (matching current behavior; if behavior is wrong, fix minimally and document in PR body).

**Acceptance:** At least two distinct error scenarios covered.

---

## Ticket D — `--no-events` effect on `events` in `snapshot`

**Goal:** Document and test that `--no-events` actually suppresses world events in the final summary (or define what “disabled” means if code only tweaks cooldowns).

**Tasks:**

1. One subprocess test: `run --no-events --seed 2 --turns 40` → parsed JSON has `events_total == 0` and `events == []` **or** justify in PR why a different bar is correct and assert that instead.
2. Control run without `--no-events` on same seed/turns should have **`events_total >= 1`** with high probability; if the seed is flaky, pick a seed you prove in the PR (short table in PR description is enough).

**Acceptance:** Clear assertion + comment in test explaining the chosen seed.

---

## Ticket E — **Stretch** — Schema stability for `stream` NDJSON

**Goal:** Every line emitted by `cli.py stream` is valid JSON with a **stable key set** per line so downstream tools don’t break silently.

**Tasks:**

1. Run `stream` for a modest `N` (e.g. 25 turns), seed fixed, optionally `--no-events` to shrink variance.
2. For **each** line: `json.loads` succeeds; top-level keys are **exactly** the set you expect (e.g. `turn`, `nations`, `battles_this_turn`, `events_this_turn`) — no extras, no missing.
3. For **each** nation object inside `nations`: required keys always present (`name`, `trait`, `trait_id`, `slot_revivals`, `territory`, `armies`, `gold`, `alive`); if `alive` is false, `death_turn` and `absorbed_by` must be present (align with existing `test_cli_chronicle` expectations).
4. If you find legitimate optional fields, **don’t** broaden the schema silently: either open a discussion in the PR or add a version field — pick one approach and explain it.

**Acceptance:** One test module or parametrized test; runtime reasonable; PR calls out any schema gotcha you discovered.

**Why this stretches:** You must reconcile “strict schema” with edge cases (empty battle lists, dead nations, event toggles) and defend choices in review — closer to API design than copy-paste testing.

---

## House rules

- Prefer **small commits** or a clear PR description with one bullet per ticket if you bundle.
- Don’t refactor unrelated modules; if `cli` needs a tiny hook to test error paths, keep the diff surgical.
- If anything here conflicts with Dan’s branch, note it at the top of the PR.

When you’re done, drop a short ping in `Vesper/VESPER_REPLY.md` or ask Dan to merge a line into `Composer/CONVERSATION.md` pointing at the PR.

— Vellum
