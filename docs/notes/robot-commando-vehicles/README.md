# Robot Commando Vehicle Special Abilities Analysis

This directory contains extracted sections from Robot Commando that include player vehicles/robots, for the purpose of analyzing their special abilities and determining how to parse them into structured rules that the game engine can use.

## Overview

Each file contains:
- Vehicle stats (ARMOUR, SPEED, COMBAT BONUS)
- Full special abilities text
- Full section HTML and text for context
- Analysis notes for parsing requirements

## Special Abilities Parsing Requirements

Similar to how combat rules are parsed in `extract_combat_v1`, we need to parse vehicle special abilities into structured rules/modifiers that can modify:

1. **Combat mechanics** (e.g., stat modifications, automatic wins, escape rules)
2. **Gameplay mechanics** (e.g., conditional effects, movement rules)

### Examples of Special Abilities Patterns

- **Stat modifications**: "Reduce the SKILL of any enemy dinosaur by 1"
- **Automatic win conditions**: "Whenever the Wasp's Attack Roll exceeds its foe's roll by 4 or more, it automatically wins the next combat round"
- **Escape rules**: "you can escape from any opponent – even another 'Very Fast' one"
- **Combat modifiers**: "clumsy attack (-2 to your roll), but if it succeeds, the foe takes 6 points of damage"
- **Conditional effects**: "no use against other robots" (conditional on enemy type)

## Reference: Combat Rules Parsing

See `modules/enrich/extract_combat_v1/main.py`:
- `_extract_combat_rules()` - extracts structured rules (fight_singly, both_attack_each_round, etc.)
- `_extract_combat_triggers()` - extracts conditional outcome triggers
- `_normalize_modifiers()` - normalizes stat changes into structured format

We need similar parsing for vehicle special abilities.

## Files

- `section-9-SUPER-COWBOY-ROBOT.md` - Sonic Screamer weapon (reduce enemy SKILL by 1)
- `section-13-DIGGER-ROBOT.md` - Scoop-shovel attack (-2 to roll, 6 damage on success)
- `section-24-COWBOY-ROBOT.md` - No special abilities
- `section-41-WASP-FIGHTER.md` - Automatic win if attack roll exceeds by 4+
- `section-47-DRAGONFLY-MODEL-D.md` - Can escape from any opponent
- ... (see directory listing for all files)
