"""
combat.py – RISK-style dice combat resolution.
"""
import random
import math
from constants import *
from entities import Battle


DICE_SIDES = 6

def roll_dice(n, sides=DICE_SIDES):
    return sorted([random.randint(1, sides) for _ in range(n)], reverse=True)


def resolve_battle(attacker, defender, def_tile, turn, log_fn,
                   atk_surge=False, tier4_def=False,
                   atk_trait_dice=0, def_trait_dice=0,
                   nations=None):
    """
    Resolve a battle between two armies.
    Returns (winner, battle_record).
    defender may be None (neutral tile conquest).

    atk_surge      – attacker gets +1 die (post-betrayal surge bonus)
    tier4_def      – defender gets +1 die (Tier-4 alliance joint-command bonus)
    atk_trait_dice – extra attacker dice from nation trait (e.g. Militarist)
    def_trait_dice – extra defender dice from nation trait (e.g. Fortifier)
    """
    def_nation = defender.nation if defender else -1

    def _bump_nation(idx, won=0, lost=0):
        if nations and idx >= 0:
            nations[idx].history['battles_won'] += won
            nations[idx].history['battles_lost'] += lost

    # Dice counts modified by level and traits
    atk_dice = COMBAT_ATK_DICE + max(0, attacker.level - 5) + atk_trait_dice
    if atk_surge:
        atk_dice += 1

    if defender:
        def_dice = COMBAT_DEF_DICE + max(0, defender.level - 5) + def_trait_dice
    else:
        def_dice = 1   # neutral tile — minimal resistance

    # Castle bonus
    castle_bonus = 0
    if def_tile.entity == 'castle':
        def_dice += CASTLE_DEF_BONUS
        castle_bonus = CASTLE_DEF_BONUS

    # Tier-4 alliance joint-command bonus
    if tier4_def and defender:
        def_dice += 1

    atk_losses = 0
    def_losses = 0
    rounds = max(attacker.level, defender.level if defender else 1)

    for _ in range(rounds):
        ar = roll_dice(atk_dice)
        dr = roll_dice(def_dice)
        pairs = min(len(ar), len(dr))
        for i in range(pairs):
            if ar[i] > dr[i]:
                def_losses += 1
            else:
                atk_losses += 1

    # Apply level modifier: higher level army loses fewer hp per loss
    atk_dmg = atk_losses * max(1, 5 - attacker.level // 2)
    def_dmg = def_losses * (max(1, 5 - defender.level // 2) if defender else 10)

    attacker.health = max(0, attacker.health - atk_dmg)
    if defender:
        defender.health = max(0, defender.health - def_dmg)

    # Determine winner
    if defender is None or defender.health <= 0:
        winner = attacker.nation
        attacker.battles_won += 1
        _bump_nation(attacker.nation, won=1)
        if defender:
            defender.battles_lost += 1
            _bump_nation(defender.nation, lost=1)
        parts = []
        if castle_bonus: parts.append(f'Castle+{castle_bonus}')
        if atk_surge:    parts.append('Surge')
        notes = ','.join(parts)
    elif attacker.health <= 0:
        winner = def_nation
        attacker.battles_lost += 1
        _bump_nation(attacker.nation, lost=1)
        if defender:
            defender.battles_won += 1
            _bump_nation(defender.nation, won=1)
        notes = 'Defender held'
    else:
        # Both survive — attacker repelled if less health
        if attacker.health <= defender.health:
            winner = def_nation
            attacker.battles_lost += 1
            _bump_nation(attacker.nation, lost=1)
            if defender:
                defender.battles_won += 1
                _bump_nation(defender.nation, won=1)
            notes = 'Repelled'
        else:
            winner = attacker.nation
            attacker.battles_won += 1
            _bump_nation(attacker.nation, won=1)
            if defender:
                defender.battles_lost += 1
                _bump_nation(defender.nation, lost=1)
            notes = 'Pyrrhic'

    b = Battle(
        turn=turn,
        ax=def_tile.x, ay=def_tile.y,
        atk_nation=attacker.nation, def_nation=def_nation,
        atk_army=attacker, def_army=defender,
        winner=winner,
        atk_losses=atk_losses, def_losses=def_losses,
        notes=notes,
    )
    return winner, b
