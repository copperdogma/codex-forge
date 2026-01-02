# Story 109 — Special Combat Analysis Notes

Purpose: scratchpad for classifying special combats and capturing structured mechanics.

## Candidate Criteria (Draft)
- Multiple enemies in one combat event (e.g., fight in sequence)
- Explicit "special rules" text in enemy or combat context
- Stat penalties or bonuses that apply during combat (e.g., "-3 SKILL during this combat")
- Conditional win/loss triggers beyond standard combat resolution (e.g., Attack Strength totals 22)
- Mandatory fight order, split targets, or unique mechanics (e.g., fight one at a time, choose which pincer)

## Data Sources
- Run id: ff-ai-ocr-gpt51-pristine-fast-full-combat-outcomes-20260101d
- Primary artifact: output/runs/ff-ai-ocr-gpt51-pristine-fast-full-combat-outcomes-20260101d/gamebook.json
- Upstream reference: output/runs/ff-ai-ocr-gpt51-pristine-fast-full-combat-outcomes-20260101b/09_sequence_order_v1/portions_with_sequence.jsonl

## Notes Format
- Section id
- Enemy/enemies
- Why special (criteria)
- Suggested structured mechanics (engine-facing)
- Raw special_rules snippet (if present)

## vNext Snapshot (run ff-ai-ocr-gpt51-pristine-fast-full-vnext-20260101f)
- Artifact: output/runs/ff-ai-ocr-gpt51-pristine-fast-full-vnext-20260101f/gamebook.json
- Validator: output/runs/ff-ai-ocr-gpt51-pristine-fast-full-vnext-20260101f/13_validate_ff_engine_node_v1/gamebook_validation_node.json (valid)

## vNext Structured Mechanics (manual mapping targets)

Format shorthand:
- mode: single|sequential|simultaneous|split-target
- rules: [{kind: ...}]
- modifiers: [{kind: stat_change, stat, amount, scope}]
- triggers: [{kind, value?, outcome}]

### Section 91
- mode: sequential
- rules: [{kind: fight_singly}]
- modifiers: [{kind: stat_change, stat: skill, amount: -4, scope: combat}]
- notes: bare-handed; tunnel too narrow (already covered by fight_singly)

### Section 124
- mode: split-target
- rules: [{kind: both_attack_each_round}, {kind: choose_target_each_round}, {kind: secondary_enemy_defense_only}, {kind: secondary_target_no_damage}]
- modifiers: []

### Section 130
- mode: sequential
- rules: [{kind: fight_singly}]
- modifiers: []

### Section 143
- mode: split-target
- rules: [{kind: both_attack_each_round}, {kind: choose_target_each_round}, {kind: secondary_enemy_defense_only}, {kind: secondary_target_no_damage}]
- modifiers: []
- triggers: [{kind: enemy_attack_strength_total, value: 22, outcome: {targetSection: "2"}}]
- outcomes.win: {targetSection: "163"}

### Section 145
- mode: single
- rules: []
- modifiers: [{kind: stat_change, stat: skill, amount: -2, scope: combat}]

### Section 148
- mode: sequential
- rules: [{kind: fight_singly}]
- modifiers: []

### Section 151
- mode: sequential
- rules: [{kind: fight_singly}]
- modifiers: [{kind: stat_change, stat: skill, amount: -2, scope: combat}]

### Section 166
- mode: sequential
- rules: [{kind: fight_singly}]
- modifiers: [{kind: stat_change, stat: skill, amount: -3, scope: combat}]

### Section 189
- mode: sequential
- rules: [{kind: fight_singly}]
- modifiers: []

### Section 294
- mode: single
- rules: []
- modifiers: [{kind: stat_change, stat: skill, amount: -2, scope: combat}]
- outcomes.win: {terminal: {kind: continue}}

### Section 327
- mode: single
- rules: []
- modifiers: []
- triggers: [{kind: enemy_round_win, outcome: {targetSection: "8"}}]
- outcomes.win: {targetSection: "92"}

### Section 380
- mode: sequential
- rules: [{kind: fight_singly}]
- modifiers: []

## vNext Extraction Gaps (current output vs targets)

Run inspected: `output/runs/ff-ai-ocr-gpt51-pristine-fast-full-vnext-20260101f/gamebook.json`

- Section 124: structured split-target rules populated in combat; no extra notes required.
- Section 143: structured split-target rules populated; trigger captured for Attack Strength 22.
- Section 189: pre‑combat damage (“Lose 3 STAMINA points”) should be captured by stat_modifications (not combat); verify it appears there if needed.

## Proposed Trigger Additions (if we want to model mid-combat wins precisely)

These are optional but would allow the engine to short-circuit combat before all enemies are defeated.

- `player_round_win` — fires when the player wins an Attack Round.
  - Optional fields: `count` (e.g., 1 for first win, 2 for second win).
  - Example (section 172): `{ kind: "player_round_win", count: 2, outcome: { targetSection: "278" } }`
  - Example (sections 225/294): `{ kind: "player_round_win", count: 1, outcome: { terminal: { kind: "continue" } } }`

If we adopt this, extraction should attach the trigger and still keep the `test_luck` event as the next sequence item (so combat win → continue → test luck).

## Trigger Implementation Snapshot (post-20260102 run)

Run inspected: `output/runs/ff-ai-ocr-gpt51-pristine-fast-full-vnext-20260101f/gamebook.json`

- Implemented `player_round_win` trigger with optional `count`.
- Verified triggers now present:
  - Section 172: `player_round_win` count=2 → targetSection 278.
  - Sections 225/294: `player_round_win` count=1 → terminal continue (followed by `test_luck`).
  - Section 143: `enemy_attack_strength_total` value=22 → targetSection 2.
  - Section 327: `enemy_round_win` → targetSection 8.

## Pre-combat Damage Audit (stat_change before combat)

Run inspected: `output/runs/ff-ai-ocr-gpt51-pristine-fast-full-vnext-20260101f/gamebook.json`

Sections with `stat_change` followed by `combat` in sequence:
- 6: STAMINA -2 before MANTICORE combat.
- 139: STAMINA -2 before IVY combat.
- 189: STAMINA -3 before ORC combat.
- 247: STAMINA -(1d6*2) before MANTICORE combat.

All four appear as `stat_change` sequence events preceding combat in the stamped gamebook.

## Example Seed
- Section 166
  - Enemies: First FLYING GUARDIAN (7/8), Second FLYING GUARDIAN (8/8)
  - Why special: multiple enemies; fight one at a time; -3 SKILL during combat
  - Suggested mechanics:
    - fight_singly: true
    - combat_stat_modifiers: [{ stat: "skill", amount: -3, duration: "battle" }]
  - special_rules: "Fight them one at a time; -3 SKILL penalty due to restricted position"

## Special Combat Inventory (auto-extracted)

### Section 91
- Reasons: multiple_enemies, special_rules
- Enemies: First ORC, Second ORC
- special_rules: You must fight them bare-handed, reducing your SKILL by 4 for the duration of the combat; the tunnel is too narrow for both Orcs to attack you at once; fight them one at a time.
- special_rules: You must fight them bare-handed, reducing your SKILL by 4 for the duration of the combat; the tunnel is too narrow for both Orcs to attack you at once; fight them one at a time.
- Snippet: 91 The Orc's morning star thuds into your arm, knocking your sword to the floor. You must fight them bare-handed, reducing your SKILL by 4 for the duration of the combat. Fortunately, the tunnel is too narrow for both Orcs to attack you at …

### Section 124
- Reasons: multiple_enemies, special_rules
- Enemies: First GOBLIN, Second GOBLIN
- special_rules: Both Goblins attack each round; fight chosen Goblin normally; defend against the other by Attack Strength roll without wounding it.
- special_rules: Both Goblins attack each round; fight chosen Goblin normally; defend against the other by Attack Strength roll without wounding it.
- Snippet: 124 You throw the trapdoor open and run up the steps into a bright, lantern-lit room. Two GOBLINS are sharpening their short swords on a stone set in the middle of the floor. You catch them momentarily off guard, but they quickly recover an…

### Section 130
- Reasons: multiple_enemies, special_rules
- Enemies: First HOBGOBLIN, Second HOBGOBLIN
- special_rules: Fight them one at a time
- special_rules: Fight them one at a time
- Snippet: 130 The Hobgoblins stop their fight immediately. They do not understand what you are saying and snarl at you viciously. Then they draw their short swords and run forward to attack you. Fight them one at a time. SKILL STAMINA First HOBGOBLIN…

### Section 143
- Reasons: explicit_lose_target
- Enemies: GIANT SCORPION
- Snippet: 143 You call out to the Dwarf, telling him to send in the SCORPION because you are ready to fight. Slowly the wooden door rises, and a huge, grotesque black Scorpion squeezes underneath it and enters the room. You draw your sword in readine…

### Section 145
- Reasons: special_rules
- Enemies: DWARF
- special_rules: reduce your Attack Strength by 2
- Snippet: 145 The Dwarf is expecting your move. Furthermore, you are not as fast as you should be because of your recent ordeal, so he easily evades your punch, saying, 'I could kill you now if I wished, but I yearn for a hand-to-hand fight.' Then he…

### Section 148
- Reasons: multiple_enemies, special_rules
- Enemies: First GUARD DOG, Second GUARD DOG
- special_rules: Fight them one at a time
- special_rules: Fight them one at a time
- Snippet: 148 There is nowhere to go except down the steps towards the barking dogs. You reach the bottom and, with your sword drawn, face the two huge black GUARD DOGS, which leap at you one at a time. SKILL STAMINA First GUARD DOG 7 7 Second GUARD …

### Section 151
- Reasons: multiple_enemies, special_rules
- Enemies: First FLYING GUARDIAN, Second FLYING GUARDIAN
- special_rules: Fight them one at a time; -2 SKILL penalty during combat
- special_rules: Fight them one at a time; -2 SKILL penalty during combat
- Snippet: 151 As you touch the idol's emerald eye you hear a creaking sound below you. Looking down, you are shocked to see the two stuffed birds flying off. Their wings flap in jerky movements, but they are soon above you and look set to attack. Fig…

### Section 166
- Reasons: multiple_enemies, special_rules
- Enemies: First FLYING GUARDIAN, Second FLYING GUARDIAN
- special_rules: Fight them one at a time; -3 SKILL penalty due to restricted position
- special_rules: Fight them one at a time; -3 SKILL penalty due to restricted position
- Snippet: 166 As you touch the emerald eye of the idol, you hear a creaking sound below you. Looking down, you are shocked to see the two stuffed birds taking flight. Their wings flap in jerky movements, but they are soon above you and look set to at…

### Section 189
- Reasons: multiple_enemies, special_rules
- Enemies: First ORC, Second ORC
- special_rules: Fight them one at a time
- special_rules: Fight them one at a time
- Snippet: 189 The Orc's morning star sinks agonizingly into your left thigh. Lose 3 STAMINA points. You stagger backwards, but manage to regain your balance in time to defend yourself. Fortunately, the tunnel is too narrow for both Orcs to attack you…

### Section 294
- Reasons: special_rules
- Enemies: BLOODBEAST
- special_rules: Reduce your SKILL by 2
- Snippet: 294 You pull the dagger from your belt with your free hand and hack at the Bloodbeast's tongue. The beast screams in pain and rolls forward as far as it can to try and clasp you between its blood-filled jaws. You must fight it from the floo…

### Section 327
- Reasons: explicit_lose_target
- Enemies: MIRROR DEMON
- Snippet: 327 The Mirror Demon, being solely intent on grabbing your arm, makes no attempt to defend itself. MIRROR DEMON SKILL 10 STAMINA 10 If, during any Attack Round, the Mirror Demon’s Attack Strength is greater than your own, turn to 8 92 328-3…

### Section 380
- Reasons: multiple_enemies, special_rules
- Enemies: First ORC, Second ORC
- special_rules: Fight them one at a time
- special_rules: Fight them one at a time
- Snippet: 380 The Orc’s morning star crashes into your shield and bounces off harmlessly. The tunnel is too narrow for both of them to attack you at once, so you are able to fight them one at a time. SKILL STAMINA First ORC 5 5 Second ORC 6 4 If you …

## Full Combat Inventory (manual classification)

Legend: classification = normal | special

### Section 6 — normal
- Enemies: MANTICORE(11/11)
- Outcomes: [{'win': {'targetSection': '364'}}]
- Snippet: Knowing that the Manticore will fire the spikes in its tail at you, you run for cover behind one of the pillars. Before you reach it, a volley of spikes flies through the air and one of them sinks into your arm. Lose 2 STAMINA points. If you are still alive, y…

### Section 39 — normal
- Enemies: GIANT FLY(7/8)
- Outcomes: [{'win': {'targetSection': '111'}}]
- Snippet: You manage to evade the outstretched legs of the diving Giant Fly. Stepping back, you draw your sword and prepare to fight the hideous insect as it turns to attack you again. GIANT FLY SKILL 7 STAMINA 8 If you win, turn to 111 267

### Section 40 — normal
- Enemies: MINOTAUR(9/9)
- Outcomes: [{'win': {'targetSection': '163'}}]
- Snippet: You call out to the Dwarf that you are ready to fight the MINOTAUR. The wooden door rises slowly and you see the fearsome beast, half man, half bull, step into the arena. Steam blows from its nostrils as it works itself up into a rage, ready to attack. Suddenl…

### Section 51 — normal
- Enemies: HOBGOBLIN(6/5)
- Outcomes: [{'win': {'targetSection': '9'}}]
- Snippet: The Hobgoblins are unprepared for your attack, and you are able to kill the first one before he can draw his sword. You turn to face the remaining Hobgoblin, who snarls at you with hatred. HOBGOBLIN SKILL 6 STAMINA 5 If you win, turn to 9

### Section 91 — special
- Enemies: First ORC(5/5); Second ORC(6/4)
- Reasons: multiple_enemies, special_rules
- special_rules: You must fight them bare-handed, reducing your SKILL by 4 for the duration of the combat; the tunnel is too narrow for both Orcs to attack you at once; fight them one at a time.
- Proposed mechanics:
  - fight_singly: true
  - combat_stat_modifiers: [{ stat: "skill", amount: -4, duration: "battle", reason: "bare-handed" }]
  - multi_enemy_mode: sequential
- Outcomes: [{'win': {'targetSection': '257'}}]
- Snippet: The Orc's morning star thuds into your arm, knocking your sword to the floor. You must fight them bare-handed, reducing your SKILL by 4 for the duration of the combat. Fortunately, the tunnel is too narrow for both Orcs to attack you at once. Fight them one at…
### Section 124 — special
- Enemies: First GOBLIN(5/4); Second GOBLIN(5/5)
- Reasons: multiple_enemies, special_rules
- special_rules: Both Goblins attack each round; fight chosen Goblin normally; defend against the other by Attack Strength roll without wounding it.
- Proposed mechanics:
  - multi_enemy_mode: simultaneous_two
  - secondary_enemy_defense_only: true
  - fight_singly: false
- Outcomes: [{'win': {'targetSection': '81'}}]
- Snippet: You throw the trapdoor open and run up the steps into a bright, lantern-lit room. Two GOBLINS are sharpening their short swords on a stone set in the middle of the floor. You catch them momentarily off guard, but they quickly recover and both rush forward to a…
### Section 130 — special
- Enemies: First HOBGOBLIN(7/5); Second HOBGOBLIN(6/5)
- Reasons: multiple_enemies, special_rules
- special_rules: Fight them one at a time
- Proposed mechanics:
  - fight_singly: true
  - multi_enemy_mode: sequential
- Outcomes: [{'win': {'targetSection': '9'}}]
- Snippet: The Hobgoblins stop their fight immediately. They do not understand what you are saying and snarl at you viciously. Then they draw their short swords and run forward to attack you. Fight them one at a time. SKILL STAMINA First HOBGOBLIN 7 5 Second HOBGOBLIN 6 …
### Section 139 — normal
- Enemies: IVY(9/9)
- Outcomes: [{'win': {'targetSection': '201'}}]
- Snippet: As you try to escape, Ivy whirls round and picks up a broken stool. She is angry and attacks you ferociously. Lose 2 STAMINA points. If you are still alive, you manage to draw your sword and fight back. IVY SKILL 9 STAMINA 9 If you win, turn to 201

### Section 143 — special
- Enemies: GIANT SCORPION(10/10)
- Reasons: explicit_lose_target
- Proposed mechanics:
  - special_loss_trigger: { kind: "attack_strength_total", value: 22, outcome: { targetSection: "2" } }
  - multi_enemy_mode: split_target_choice
- Outcomes: [{'win': {'targetSection': '163'}, 'lose': {'targetSection': '2'}}]
- Snippet: You call out to the Dwarf, telling him to send in the SCORPION because you are ready to fight. Slowly the wooden door rises, and a huge, grotesque black Scorpion squeezes underneath it and enters the room. You draw your sword in readiness and prepare to fight …
### Section 145 — special
- Enemies: DWARF(8/6)
- Reasons: special_rules
- special_rules: reduce your Attack Strength by 2
- Proposed mechanics:
  - combat_stat_modifiers: [{ stat: "attack_strength", amount: -2, duration: "battle" }]
- Outcomes: [{'win': {'targetSection': '28'}}]
- Snippet: The Dwarf is expecting your move. Furthermore, you are not as fast as you should be because of your recent ordeal, so he easily evades your punch, saying, 'I could kill you now if I wished, but I yearn for a hand-to-hand fight.' Then he throws down his crossbo…
### Section 148 — special
- Enemies: First GUARD DOG(7/7); Second GUARD DOG(7/8)
- Reasons: multiple_enemies, special_rules
- special_rules: Fight them one at a time
- Proposed mechanics:
  - fight_singly: true
  - multi_enemy_mode: sequential
- Outcomes: [{'win': {'targetSection': '315'}}]
- Snippet: There is nowhere to go except down the steps towards the barking dogs. You reach the bottom and, with your sword drawn, face the two huge black GUARD DOGS, which leap at you one at a time. SKILL STAMINA First GUARD DOG 7 7 Second GUARD DOG 7 8 If you win, turn…
### Section 151 — special
- Enemies: First FLYING GUARDIAN(7/8); Second FLYING GUARDIAN(8/8)
- Reasons: multiple_enemies, special_rules
- special_rules: Fight them one at a time; -2 SKILL penalty during combat
- Proposed mechanics:
  - fight_singly: true
  - multi_enemy_mode: sequential
  - combat_stat_modifiers: [{ stat: "skill", amount: -2, duration: "battle", reason: "restricted position" }]
- Outcomes: [{'win': {'targetSection': '240'}}]
- Snippet: As you touch the idol's emerald eye you hear a creaking sound below you. Looking down, you are shocked to see the two stuffed birds flying off. Their wings flap in jerky movements, but they are soon above you and look set to attack. Fight the FLYING GUARDIANS …
### Section 166 — special
- Enemies: First FLYING GUARDIAN(7/8); Second FLYING GUARDIAN(8/8)
- Reasons: multiple_enemies, special_rules
- special_rules: Fight them one at a time; -3 SKILL penalty due to restricted position
- Proposed mechanics:
  - fight_singly: true
  - multi_enemy_mode: sequential
  - combat_stat_modifiers: [{ stat: "skill", amount: -3, duration: "battle", reason: "restricted position" }]
- Outcomes: [{'win': {'targetSection': '11'}}]
- Snippet: As you touch the emerald eye of the idol, you hear a creaking sound below you. Looking down, you are shocked to see the two stuffed birds taking flight. Their wings flap in jerky movements, but they are soon above you and look set to attack. Fight the FLYING G…
### Section 172 — normal
- Enemies: BLOODBEAST(12/10)
- Outcomes: [{'win': {'targetSection': '278'}}]
- Snippet: Remembering the description of the vile Bloodbeast and the warning about toxic gas rising from its pool, you cover your mouth with your sleeve and step forward with your sword drawn, wary of the Bloodbeast's tongue. As you step round the side of its pool, it r…

### Section 189 — special
- Enemies: First ORC(5/5); Second ORC(6/4)
- Reasons: multiple_enemies, special_rules
- special_rules: Fight them one at a time
- Proposed mechanics:
  - fight_singly: true
  - multi_enemy_mode: sequential
- Outcomes: [{'win': {'targetSection': '257'}}]
- Snippet: The Orc's morning star sinks agonizingly into your left thigh. Lose 3 STAMINA points. You stagger backwards, but manage to regain your balance in time to defend yourself. Fortunately, the tunnel is too narrow for both Orcs to attack you at once. Fight them one…
### Section 196 — normal
- Enemies: MANTICORE(11/11)
- Outcomes: [{'win': {'targetSection': '364'}}]
- Snippet: You raise your shield in front of you just in time to protect yourself from a volley of spikes released from the Manticore’s tail and aimed straight at your heart. They sink into your shield and you remain unharmed. Swiftly you draw your sword and advance on t…

### Section 203 — normal
- Enemies: PIT FIEND(12/15)
- Outcomes: [{'win': {'targetSection': '258'}}]
- Snippet: You stagger to your feet and draw your sword. You are only just in time, for the fearsome beast is closing in on you fast. This is going to be one of the toughest fights of your life. PIT FIEND SKILL 12 STAMINA 15 If you win, turn to 258

### Section 211 — normal
- Enemies: IVY(9/9)
- Outcomes: [{'win': {'targetSection': '201'}}]
- Snippet: You manage to free yourself from Ivy's grip and draw your sword. Picking up a broken stool as a weapon, she advances towards you. IVY SKILL 9 STAMINA 9 If you win, turn to 201

### Section 225 — normal
- Enemies: BLOODBEAST(12/10)
- Outcomes: [{'win': {'terminal': {'kind': 'continue', 'message': 'continue'}}}]
- Snippet: You react quickly and manage to cleave the Blood-beast's outstretched tongue with one swipe of your blade. The beast screams in pain and hurls itself forward to try and clasp you between its blood-filled jaws. This will be a fight to the death. BLOODBEAST SKIL…

### Section 236 — normal
- Enemies: IMITATOR(9/8)
- Outcomes: [{'win': {'targetSection': '314'}}]
- Snippet: The fist retracts and prepares to strike again. With your free hand you draw your sword and try to cut the handle of the door. Although you do not recognize it, you are being attacked by the fluid form of an IMITATOR. IMITATOR SKILL 9 STAMINA 8 As soon as you …

### Section 245 — normal
- Enemies: PIT FIEND(12/15)
- Outcomes: [{'win': {'targetSection': '258'}}]
- Snippet: You have no choice but to open the door, as the wall is too smooth to climb. Taking a deep breath, you turn the handle and enter a sand-covered pit. There, standing some ten metres tall on its huge hind legs in front of large double doors in the opposite wall,…

### Section 247 — normal
- Enemies: MANTICORE(11/11)
- Outcomes: [{'win': {'targetSection': '364'}}]
- Snippet: The beast before you is the dreaded MANTICORE. The tip of its tail sprouts a profusion of sharp spikes, thick and hard as iron bolts. Suddenly it flicks its tail, sending a volley of spikes flying towards you. Roll one die. This is the number of spikes that si…

### Section 254 — normal
- Enemies: ROCK GRUB(7/11)
- Outcomes: [{'win': {'targetSection': '76'}}]
- Snippet: You draw your sword and advance slowly towards the huge, slimy Rock Grub. ROCK GRUB SKILL 7 STAMINA 11 If you win, turn to 76 117

### Section 294 — special
- Enemies: BLOODBEAST(12/10)
- Reasons: special_rules
- special_rules: Reduce your SKILL by 2
- Proposed mechanics:
  - combat_stat_modifiers: [{ stat: "skill", amount: -2, duration: "battle", reason: "dagger only" }]
- Outcomes: [{'win': {'terminal': {'kind': 'continue', 'message': 'continue'}}}]
- Snippet: You pull the dagger from your belt with your free hand and hack at the Bloodbeast's tongue. The beast screams in pain and rolls forward as far as it can to try and clasp you between its blood-filled jaws. You must fight it from the floor with your dagger. Redu…
### Section 302 — normal
- Enemies: THROM(10/12)
- Outcomes: [{'win': {'targetSection': '379'}}]
- Snippet: After about twenty minutes the Dwarf reappears on the balcony. He calls down to you, saying, 'Well, I do have an interesting problem on my hands. Prepare to fight your next opponent.' The wooden door rises once again and you are surprised to see a familiar fac…

### Section 312 — normal
- Enemies: NINJA(11/9)
- Outcomes: [{'win': {'targetSection': '232'}}]
- Snippet: The razor-sharp disc whistles past your head and bites deep into one of the pillars. Turning to face your would-be assassin, you prepare yourself as he advances, his long sword drawn. NINJA SKILL 11 STAMINA 9 If you win, turn to 232

### Section 327 — special
- Enemies: MIRROR DEMON(10/10)
- Reasons: explicit_lose_target
- Proposed mechanics:
  - special_loss_trigger: { kind: "enemy_attack_round_win", outcome: { targetSection: "8" } }
  - special_win_trigger: { kind: "no_enemy_round_wins", outcome: { targetSection: "92" } }
- Outcomes: [{'win': {'targetSection': '92'}, 'lose': {'targetSection': '8'}}]
- Snippet: The Mirror Demon, being solely intent on grabbing your arm, makes no attempt to defend itself. MIRROR DEMON SKILL 10 STAMINA 10 If, during any Attack Round, the Mirror Demon’s Attack Strength is greater than your own, turn to 8 92
### Section 331 — normal
- Enemies: SKELETON WARRIOR(8/6)
- Outcomes: [{'win': {'targetSection': '71'}}]
- Snippet: Touching the parchment has precisely the effect you had feared. The skeleton lurches forward and, rising from its chair in a series of jerky movements, raises its sword to strike you. Lunging sideways, you draw your sword to defend yourself. SKELETON WARRIOR S…

### Section 349 — normal
- Enemies: PIT FIEND(12/15)
- Outcomes: [{'win': {'targetSection': '258'}}]
- Snippet: You lower yourself down the rope into the pit with one hand, using the other to grip your sword. The Pit Fiend is one of the most fearsome beasts you have ever seen, and you know this is to be one of the hardest fights of your life. PIT FIEND SKILL 12 STAMINA …

### Section 369 — normal
- Enemies: CAVE TROLL(10/11)
- Outcomes: [{'win': {'targetSection': '288'}}]
- Snippet: The tunnel turns sharply to the right, continuing east for as far as you can see. Throm stops and tells you to halt as well. He turns his head slowly from side to side, listening. 'I hear footsteps coming down the tunnel towards us,' he whispers. 'Draw your sw…

### Section 380 — special
- Enemies: First ORC(5/5); Second ORC(6/4)
- Reasons: multiple_enemies, special_rules
- special_rules: Fight them one at a time
- Proposed mechanics:
  - fight_singly: true
  - multi_enemy_mode: sequential
- Outcomes: [{'win': {'targetSection': '257'}}]
- Snippet: The Orc’s morning star crashes into your shield and bounces off harmlessly. The tunnel is too narrow for both of them to attack you at once, so you are able to fight them one at a time. SKILL STAMINA First ORC 5 5 Second ORC 6 4 If you win, turn to 257
### Section 387 — normal
- Enemies: CAVEMAN(7/7)
- Outcomes: [{'win': {'targetSection': '114'}}]
- Snippet: Ahead you hear the thud of heavy footsteps approaching. Out of the gloom steps a large, primitive being dressed in animal hide and carrying a stone club. On seeing you, he grunts and spits on the floor, then raises his club and lumbers on towards you, looking …
