# Idea: Narrow Graphical Frontend

Inspired by Rusty's Retirement — a small strip that lives at the bottom (or corner) of the
screen while you work. Not a game you play, just something happening nearby.

Ancient Nations may not be the right vehicle (the 100×100 world is hard to compress into a
strip readably), but the concept is worth revisiting for a future project.

## The appeal

- Johnny Castaway energy: something is going on, you can glance at it, you don't have to watch
- Rusty's Retirement execution: explicitly designed to be ignored, tiny window, ambient progress
- The "corner of the screen" genre — ambient, not demanding

## Why Ancient Nations might not fit

- 100×100 world doesn't compress to a strip without losing legibility
- The interesting stuff (diplomacy, betrayal, rebellion) is text-level, not visual
- Would need a purpose-built small-scale sim to make a strip readable at a glance

## If revisiting this concept

- Start with the sim, not the frontend — design for a strip from the beginning
- Small world (20×10 tiles max), few entities, one or two numbers to track
- The NDJSON CLI here (cli.py --stream) is a good architectural model: sim as backend, renderer as consumer
- pygame or tkinter for the strip; no curses, no terminal
- "Highlight reel" camera that cuts to wherever something just happened
