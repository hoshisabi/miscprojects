# Wiki Structure

Markdown documents that grow over time and serve as context for future DM assistant prompts.
Stored in the campaign's git repo alongside session logs.

## Directory layout

```
campaign/
  wiki/
    characters/
      pcs/
        oskar.md        # one file per PC
        kaelisa.md
        cinder.md
        araken.md
      npcs/
        [name].md       # one file per notable NPC
    locations/
      [name].md         # one file per location visited or known
    factions/
      [name].md         # organizations, cults, tribes, etc.
    threads.md          # active plot hooks; mark resolved with date
    timeline.md         # session-by-session event log, one line per beat
  sessions/
    YYYY-MM-DD.md       # DM assistant report per session (not public)
    YYYY-MM-DD.txt      # raw corrected transcript (not public)
  public/
    sessions/           # player-facing recaps
    characters/         # player-facing character pages
    index.md
```

## Document conventions

### Character files (PCs and NPCs)
- Known facts only — what the party knows, not DM secrets
- Updated after each session that advances the character
- Sections: Description, Known History, Relationships, Session Notes (brief per-session bullet)

### Location files
- First visited date
- What the party observed/learned
- Known connections to other locations or factions
- Open questions

### threads.md
- One bullet per thread
- Format: `- [ACTIVE/RESOLVED YYYY-MM-DD] **Thread name**: description`

### timeline.md
- One line per significant event, chronological
- Format: `- [Session YYYY-MM-DD] Brief description of event`

## How to use with prompts

For each new session, feed the prompt:
- Full transcript
- All PC files
- Any NPC files for characters who appeared
- Any location files for places visited
- threads.md
- Previous session summary (optional, for continuity)

When the wiki is large, select only relevant documents rather than dumping everything.
After generating the report, update wiki files to reflect new session info.
