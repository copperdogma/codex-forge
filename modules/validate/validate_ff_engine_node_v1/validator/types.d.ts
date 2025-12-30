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
 * Canonical navigation edge for a section
 */
export interface NavigationEdge {
    /** Target section ID */
    targetSection: SectionId;
    /** Navigation kind (choice vs mechanic) */
    kind: 'choice' | 'test_luck' | 'item_check' | 'combat' | 'stat_check' | 'death' | 'custom';
    /** Outcome label for conditional navigation */
    outcome?: 'lucky' | 'unlucky' | 'has_item' | 'no_item' | 'win' | 'lose' | 'escape' | 'pass' | 'fail' | 'death' | string;
    /** Optional descriptive text for the choice (if available from context) */
    choiceText?: string;
    /** Optional parameters (item name, enemy name, etc.) */
    params?: Record<string, unknown>;
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
    /** Optional special combat rules */
    special_rules?: string;
    /** Whether escape is allowed from this combat */
    allow_escape?: boolean;
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
    /** Whether this is a permanent modification (affects initial value) */
    permanent?: boolean;
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
export type SectionType = 'section' | 'front_cover' | 'back_cover' | 'title_page' | 'publishing_info' | 'toc' | 'intro' | 'rules' | 'adventure_sheet' | 'template';
/**
 * A gamebook section - represents any content from the book
 *
 * The parser captures ALL content from the book, including covers, rules, etc.
 * The engine only processes sections where isGameplaySection === true
 */
export interface GamebookSection {
    /** Unique section identifier */
    id: SectionId;
    /** Narrative text content */
    text: string;
    /** Page reference (optional, for citation) */
    pageStart?: number;
    pageEnd?: number;
    /**
     * Whether this is a gameplay section that the engine should process.
     * Set to false for covers, rules, publishing info, etc.
     * Only gameplay sections have navigation, combat, items, etc.
     */
    isGameplaySection: boolean;
    /** Section type - categorizes the content */
    type: SectionType;
    /** Canonical navigation edges (only for gameplay sections) */
    navigation?: NavigationEdge[];
    /** Combat encounters (only for gameplay sections) */
    combat?: CombatEncounter[];
    /** Item references (only for gameplay sections) */
    items?: ItemReference[];
    /** Stat modifications (only for gameplay sections) */
    statModifications?: StatModification[];
    /** Death conditions (only for gameplay sections) */
    deathConditions?: DeathCondition[];
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
