/**
 * TypeScript type definitions for Fighting Fantasy Gamebook JSON format
 *
 * This defines the ideal JSON structure that the engine expects.
 * The PDF-to-JSON parser should adapt to produce this format.
 *
 * Design principle: Parser does heavy lifting (extraction, parsing),
 * engine receives clean, structured data that's easy to process.
 */
/**
 * Unique identifier for a section (e.g., "1", "270", "S003")
 * Can be numeric string or alphanumeric
 */
export type SectionId = string;
/**
 * Terminal outcome when a sequence event ends the game without a target section
 */
export interface TerminalOutcome {
    /** Terminal outcome type */
    kind: 'death' | 'victory' | 'defeat' | 'end' | 'continue';
    /** Optional narrative message */
    message?: string;
}
/**
 * Outcome reference for conditional events (target or terminal)
 */
export interface OutcomeRef {
    targetSection?: SectionId;
    terminal?: TerminalOutcome;
}
/**
 * Sequence events define ordered gameplay flow
 */
export type SequenceEvent = ChoiceEvent | StatChangeEvent | StatCheckEvent | TestLuckEvent | ItemEvent | ItemCheckEvent | StateCheckEvent | ConditionalEvent | CombatEvent | DeathEvent | CustomEvent;
export interface ChoiceEvent {
    kind: 'choice';
    targetSection: SectionId;
    choiceText?: string;
    effects?: ItemEvent[];
}
export interface StatChangeEvent {
    kind: 'stat_change';
    stat: 'skill' | 'stamina' | 'luck' | string | string[];
    amount: number | string;
    scope: 'permanent' | 'section' | 'combat' | 'round';
    reason?: string;
}
export interface StatCheckEvent {
    kind: 'stat_check';
    stat: 'skill' | 'stamina' | 'luck' | string | string[];
    diceRoll?: string;
    passCondition?: string;
    failCondition?: string;
    pass?: OutcomeRef;
    fail?: OutcomeRef;
}
export interface TestLuckEvent {
    kind: 'test_luck';
    lucky?: OutcomeRef;
    unlucky?: OutcomeRef;
}
export interface ItemEvent {
    kind: 'item';
    action: 'add' | 'remove' | 'reference';
    name: string;
}
export interface ItemCheckEvent {
    kind: 'item_check';
    itemName?: string;
    itemsAll?: string[];
    has?: OutcomeRef;
    missing?: OutcomeRef;
}
export interface StateCheckEvent {
    kind: 'state_check';
    conditionText?: string;
    has?: OutcomeRef;
    missing?: OutcomeRef;
}
export interface ItemCondition {
    kind: 'item';
    itemName: string;
    operator?: 'has' | 'missing';
}
export type Condition = ItemCondition;
export interface ConditionalEvent {
    kind: 'conditional';
    condition: Condition;
    then: SequenceEvent[];
    else?: SequenceEvent[];
}
export interface CombatEvent {
    kind: 'combat';
    mode?: 'single' | 'sequential' | 'simultaneous' | 'split-target';
    enemies: CombatEncounter[];
    rules?: CombatRule[];
    modifiers?: StatChangeEvent[];
    triggers?: CombatTrigger[];
    outcomes: {
        win: OutcomeRef;
        lose?: OutcomeRef;
        escape?: OutcomeRef;
    };
}
export interface DeathEvent {
    kind: 'death';
    outcome: OutcomeRef;
    description?: string;
}
export interface CustomEvent {
    kind: 'custom';
    data?: Record<string, unknown>;
}
/**
 * Combat encounter embedded in a section
 */
export interface CombatEncounter {
    /** Creature name */
    enemy: string;
    /** Combat Skill value */
    skill: number;
    /** Stamina (hit points) */
    stamina: number;
}
export interface CombatRule {
    kind: 'fight_singly' | 'both_attack_each_round' | 'choose_target_each_round' | 'secondary_target_no_damage' | 'secondary_enemy_defense_only' | 'note';
    text?: string;
}
export interface CombatTrigger {
    kind: 'enemy_round_win' | 'no_enemy_round_wins' | 'enemy_attack_strength_total' | 'player_round_win';
    value?: number;
    count?: number;
    outcome: OutcomeRef;
}
/**
 * Item reference - items mentioned in section text
 */
export interface ItemReference {
    /** Item name (as it appears in text) */
    name: string;
    /** Whether this section adds the item to inventory */
    action: 'add' | 'remove' | 'check' | 'reference';
}
/**
 * Stat modification - changes to player stats (Skill, Stamina, Luck)
 */
export interface StatModification {
    /** Stat name: 'skill', 'stamina', or 'luck' */
    stat: 'skill' | 'stamina' | 'luck';
    /** Amount to change (can be negative) */
    amount: number;
    /** Duration for the change */
    scope: 'permanent' | 'section' | 'combat' | 'round';
    /** Optional explanation of the modification */
    reason?: string;
}
/**
 * Death condition - ways the player can die in this section
 */
export interface DeathCondition {
    /** Death trigger type */
    trigger: 'stamina_zero' | 'instant_death' | 'conditional';
    /** Death message/reason */
    message?: string;
}
/**
 * Section types - categorizes different kinds of content
 */
export type SectionType = 'section' | 'front_cover' | 'back_cover' | 'title_page' | 'publishing_info' | 'toc' | 'intro' | 'rules' | 'adventure_sheet' | 'template' | 'background';
/**
 * A gamebook section - represents any content from the book
 *
 * The parser captures ALL content from the book, including covers, rules, etc.
 * The engine only processes sections where isGameplaySection === true
 */
export interface GamebookSection {
    /** Unique section identifier */
    id: SectionId;
    /** Cleaned HTML content for display (final narrative payload) */
    presentation_html: string;
    /** Page reference (optional, for citation) */
    pageStart?: number;
    pageEnd?: number;
    /**
     * Whether this is a gameplay section that the engine should process.
     * Set to false for covers, rules, publishing info, etc.
     * Gameplay sections define ordered sequence events.
     */
    isGameplaySection: boolean;
    /** Section type - categorizes the content */
    type: SectionType;
    /** Optional ending status for the section */
    status?: 'death' | 'victory' | 'defeat';
    /** Optional end-game marker (suppresses no-choice warnings) */
    end_game?: boolean;
    /** Ordered gameplay sequence events (required for gameplay sections) */
    sequence?: SequenceEvent[];
    /** Section metadata */
    metadata?: {
        /** Section title (if available) */
        title?: string;
    };
}
/**
 * Complete gamebook JSON structure
 */
export interface GamebookJSON {
    /** Book metadata */
    metadata: {
        /** Book title */
        title: string;
        /** Book author */
        author?: string;
        /** Starting section ID (usually "1") */
        startSection: SectionId;
        /** Version of the JSON format */
        formatVersion: string;
        /** Validator version expected to validate this gamebook */
        validatorVersion?: string;
        /** Expected numeric section count for validation (optional) */
        sectionCount?: number;
    };
    /** All sections in the gamebook, keyed by section ID */
    sections: Record<SectionId, GamebookSection>;
}
/**
 * Player character statistics
 */
export interface PlayerStats {
    /** Combat Skill (1-12, typically rolled at start) */
    skill: number;
    /** Stamina (hit points, typically rolled at start) */
    stamina: number;
    /** Luck (typically rolled at start) */
    luck: number;
    /** Initial Skill value (for reference) */
    initialSkill?: number;
    /** Initial Stamina value (for reference) */
    initialStamina?: number;
    /** Initial Luck value (for reference) */
    initialLuck?: number;
}
/**
 * Game status values
 */
export type GameStatus = 'idle' | 'playing' | 'combat' | 'dead' | 'game_over' | 'victory';
/**
 * Game state - represents the current state of the game
 *
 * This is the complete game state structure that tracks:
 * - Current section ID
 * - Player statistics (Skill, Stamina, Luck with initial values)
 * - Inventory (list of items)
 * - Provisions count
 * - Game status
 * - Combat state (optional, for when in combat)
 * - Death information (optional, when player is dead)
 */
export interface GameState {
    /** Current section ID */
    currentSection?: SectionId;
    /** Player statistics */
    playerStats?: PlayerStats;
    /** Player inventory */
    inventory: string[];
    /** Provisions count */
    provisions: number;
    /** Game status */
    status: GameStatus;
    /** Combat state (if in combat) */
    combatState?: {
        state: 'idle' | 'initiating' | 'active' | 'round_complete' | 'victory' | 'defeat';
        creature?: CreatureStats;
        playerStamina?: number;
        creatureStamina?: number;
    };
    /** Death reason/message (when status is 'dead' or 'game_over') */
    deathReason?: string;
}
/**
 * Combat round result
 * (Placeholder - will be fully implemented in Story 009)
 */
export interface CombatResult {
    /** Player's attack strength */
    playerAttackStrength: number;
    /** Creature's attack strength */
    creatureAttackStrength: number;
    /** Who won the round */
    winner: 'player' | 'creature' | 'tie';
    /** Damage dealt */
    damage: number;
    /** Player's new stamina */
    playerStamina: number;
    /** Creature's new stamina */
    creatureStamina: number;
    /** Combat state after round */
    combatState: 'active' | 'victory' | 'defeat';
}
/**
 * Test Your Luck result
 * (Placeholder - will be fully implemented in Story 011)
 */
export interface LuckResult {
    /** Whether the player was lucky */
    isLucky: boolean;
    /** Dice roll result (2d6) */
    roll: number;
    /** Player's current luck value */
    currentLuck: number;
    /** New luck value (reduced by 1 after testing) */
    newLuck: number;
}
//# sourceMappingURL=types.d.ts.map
