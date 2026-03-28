"""
namegen.py — Procedural nation-name generator for Ancient Nations.

Names are formed by combining a PREFIX stem with a SUFFIX ending.  The
generator uses the global random module (seeded by World.__init__) so
output is fully deterministic for a given game seed.

Uniqueness is tracked across the entire game — including civil-war respawns —
so the same name can never appear twice in one run.  First-letter uniqueness
is also maintained where possible so ASCII map markers stay distinct.
"""

import random


# ── Word parts ────────────────────────────────────────────────────────────────

PREFIXES = [
    'Aeg', 'Alb', 'Ald', 'Alg', 'Alv', 'And', 'Ang', 'Ant',
    'Arb', 'Arc', 'Ard', 'Arg', 'Arm', 'Arv',
    'Bel', 'Ber', 'Bol', 'Bor', 'Bry',
    'Cal', 'Can', 'Car', 'Cel', 'Cer', 'Col', 'Cor', 'Cyr',
    'Dal', 'Dan', 'Del', 'Der', 'Dol', 'Dor',
    'Eld', 'Elv', 'End', 'Erd', 'Ern',
    'Fal', 'Fan', 'Far', 'Fer', 'Fol',
    'Gal', 'Gan', 'Gar', 'Gel', 'Ger', 'Gol', 'Gor',
    'Hal', 'Han', 'Har', 'Hel', 'Her', 'Hol',
    'Kal', 'Kan', 'Kar', 'Kel', 'Ker', 'Kol', 'Kor', 'Kul',
    'Lan', 'Lar', 'Ler', 'Lod', 'Lor',
    'Mal', 'Man', 'Mar', 'Mel', 'Mer', 'Mol', 'Mor',
    'Nal', 'Nan', 'Nar', 'Nel', 'Ner', 'Nor',
    'Pal', 'Pan', 'Par', 'Pel', 'Per', 'Pol', 'Por',
    'Ral', 'Ran', 'Rar', 'Rel', 'Rol', 'Ror',
    'Sal', 'San', 'Sar', 'Sel', 'Ser', 'Sol', 'Sor', 'Sul', 'Sur',
    'Tal', 'Tan', 'Tar', 'Tel', 'Ter', 'Tol', 'Tor', 'Tul', 'Tur',
    'Val', 'Van', 'Var', 'Vel', 'Ver', 'Vol', 'Vor',
    'Xan', 'Xar', 'Xel',
    'Yar', 'Yel',
    'Zal', 'Zan', 'Zar', 'Zel', 'Zor',
]

SUFFIXES = [
    'ia', 'ius', 'ium', 'us', 'os', 'is', 'on', 'an',
    'ikos', 'anus', 'ica', 'ara',
]


# ── Generator ─────────────────────────────────────────────────────────────────

class NationNameGenerator:
    """
    Generates unique nation names for one game run.

    Uses the global random module, which is seeded before Game.__init__
    runs, so names are reproducible for a given world seed.
    """

    def __init__(self):
        self._used_names:   set[str] = set()
        self._used_letters: set[str] = set()

    def generate(self) -> str:
        """
        Return a name that has not yet appeared in this game.
        Prefers names whose first letter is also new (for distinct map markers).
        Falls back to name-only uniqueness if all letters are exhausted.
        """
        # Primary: unique name AND unique first letter
        for _ in range(300):
            name   = random.choice(PREFIXES) + random.choice(SUFFIXES)
            letter = name[0].upper()
            if name not in self._used_names and letter not in self._used_letters:
                self._used_names.add(name)
                self._used_letters.add(letter)
                return name

        # Fallback: unique name only (letters may collide)
        for _ in range(300):
            name = random.choice(PREFIXES) + random.choice(SUFFIXES)
            if name not in self._used_names:
                self._used_names.add(name)
                return name

        # Should never reach here with ~900 combinations and ~20 nations per game
        name = f'Natio{len(self._used_names) + 1}n'
        self._used_names.add(name)
        return name
