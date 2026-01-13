"use strict";
/**
 * Comprehensive JSON Validation for Gamebook Format
 *
 * Provides comprehensive validation using JSON Schema and custom validation rules.
 * This validator is standalone and can be used by other projects (PDF parser, etc.).
 *
 * Features:
 * - JSON Schema validation using docs/gamebook-schema.json
 * - Collects ALL errors (not just first)
 * - Validates all sequence targets
 * - Missing/duplicate section checks
 * - Empty text + no-choice warnings
 * - Reachability analysis (warnings for unreachable sections)
 * - Detailed, actionable error messages with JSON paths
 */
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.validateGamebook = validateGamebook;
exports.validateGamebookJSON = validateGamebookJSON;
exports.evaluateCondition = evaluateCondition;
const ajv_1 = __importDefault(require("ajv"));
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
/**
 * Load JSON Schema from file
 *
 * Looks for schema in this order:
 * 1. Same directory as validation.js (for standalone validator package)
 * 2. Relative to engine/dist (for development)
 * 3. Relative to docs (for full repository)
 */
function loadSchema() {
    // Try same directory first (for standalone validator package)
    const sameDirPath = path.join(__dirname, 'gamebook-schema.json');
    if (fs.existsSync(sameDirPath)) {
        const schemaContent = fs.readFileSync(sameDirPath, 'utf-8');
        return JSON.parse(schemaContent);
    }
    // Try relative to engine/dist (for development)
    const distPath = path.join(__dirname, '../../docs/gamebook-schema.json');
    if (fs.existsSync(distPath)) {
        const schemaContent = fs.readFileSync(distPath, 'utf-8');
        return JSON.parse(schemaContent);
    }
    // Try docs directory (for full repository)
    const docsPath = path.join(__dirname, '../../../docs/gamebook-schema.json');
    if (fs.existsSync(docsPath)) {
        const schemaContent = fs.readFileSync(docsPath, 'utf-8');
        return JSON.parse(schemaContent);
    }
    throw new Error(`JSON Schema file not found. Tried:
  - ${sameDirPath}
  - ${distPath}
  - ${docsPath}`);
}
/**
 * Convert AJV error to ValidationError
 */
function ajvErrorToValidationError(error) {
    const path = error.instancePath || error.schemaPath || '';
    let message = error.message || 'Validation error';
    // Enhance error messages with context
    if (error.keyword === 'required') {
        message = `Missing required field: ${error.params.missingProperty}`;
    }
    else if (error.keyword === 'type') {
        message = `Expected ${error.params.type}, got ${typeof error.data}`;
    }
    else if (error.keyword === 'enum') {
        message = `Invalid value. Expected one of: ${error.params.allowedValues?.join(', ')}`;
    }
    return {
        path,
        message,
        expected: error.params?.type || error.params?.allowedValues?.join(', '),
        received: String(error.data),
    };
}
function stripHtmlToText(html) {
    if (!html) {
        return '';
    }
    return html
        .replace(/<script[\s\S]*?<\/script>/gi, ' ')
        .replace(/<style[\s\S]*?<\/style>/gi, ' ')
        .replace(/<[^>]+>/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

/**
 * Runtime helper: evaluate a ConditionalEvent condition against a runtime context.
 * This is intentionally lightweight and conservative (unknown conditions => false).
 *
 * Supported conditions:
 * - { kind: 'item', itemName, operator?: 'has'|'missing' }
 * - { kind: 'combat_metric', metric: 'enemy_round_wins', operator: 'gt'|'gte'|'lt'|'lte'|'eq', value: number }
 */
function evaluateCondition(condition, context) {
    if (!condition || typeof condition !== 'object') {
        return false;
    }
    const kind = String(condition.kind || '').toLowerCase();
    if (kind === 'item') {
        const itemName = String(condition.itemName || '').trim();
        if (!itemName) {
            return false;
        }
        const op = String(condition.operator || 'has').toLowerCase();
        const items = context?.items;
        const needle = itemName.toLowerCase();
        let has = false;
        if (Array.isArray(items)) {
            has = items.some((x) => String(x || '').toLowerCase() === needle);
        }
        else if (items && typeof items.has === 'function') {
            // Set<string>
            has = items.has(itemName) || items.has(needle);
        }
        if (op === 'missing') {
            return !has;
        }
        return has;
    }
    if (kind === 'combat_metric') {
        const metric = String(condition.metric || '').trim();
        const op = String(condition.operator || '').toLowerCase();
        const value = Number(condition.value);
        if (!metric || !Number.isFinite(value)) {
            return false;
        }
        const metrics = context?.combatMetrics || {};
        const observed = Number(metrics[metric]);
        if (!Number.isFinite(observed)) {
            return false;
        }
        switch (op) {
            case 'gt':
                return observed > value;
            case 'gte':
                return observed >= value;
            case 'lt':
                return observed < value;
            case 'lte':
                return observed <= value;
            case 'eq':
                return observed === value;
            default:
                return false;
        }
    }
    return false;
}
function parseExpectedRange(gamebook) {
    const metaCount = gamebook?.metadata?.sectionCount;
    if (Number.isFinite(metaCount) && metaCount > 0) {
        return { min: 1, max: Math.floor(metaCount) };
    }
    const fromProvenance = gamebook?.provenance?.expected_range || gamebook?.provenance?.expectedRange;
    const raw = typeof fromProvenance === 'string' && fromProvenance ? fromProvenance : '1-400';
    const match = raw.match(/^\s*(\d+)\s*-\s*(\d+)\s*$/);
    if (!match) {
        return { min: 1, max: 400 };
    }
    const min = Number(match[1]);
    const max = Number(match[2]);
    if (!Number.isFinite(min) || !Number.isFinite(max) || min <= 0 || max <= 0 || min > max) {
        return { min: 1, max: 400 };
    }
    return { min, max };
}
function validateMissingSections(gamebook) {
    const errors = [];
    const sectionIds = Object.keys(gamebook.sections || {});
    const numericIds = new Set(sectionIds.filter(id => /^\d+$/.test(id)));
    const { min, max } = parseExpectedRange(gamebook);
    const missing = [];
    for (let i = min; i <= max; i += 1) {
        const sid = String(i);
        if (!numericIds.has(sid)) {
            missing.push(sid);
        }
    }
    if (missing.length > 0) {
        const sample = missing.slice(0, 10);
        let msg = `Missing ${missing.length} sections in range ${min}-${max}: ${sample.join(', ')}`;
        if (missing.length > 10) {
            msg += ` (and ${missing.length - 10} more)`;
        }
        errors.push({
            path: '/sections',
            message: msg,
            expected: `all sections in range ${min}-${max}`,
            received: `missing ${missing.length} sections`,
        });
    }
    return errors;
}
function validateDuplicateSections(gamebook) {
    const errors = [];
    const seen = new Map();
    for (const [key, section] of Object.entries(gamebook.sections || {})) {
        const id = section?.id || key;
        if (!seen.has(id)) {
            seen.set(id, [key]);
        }
        else {
            seen.get(id).push(key);
        }
    }
    const duplicates = [];
    for (const [id, keys] of seen.entries()) {
        if (keys.length > 1) {
            duplicates.push({ id, keys });
        }
    }
    if (duplicates.length > 0) {
        errors.push({
            path: '/sections',
            message: `Duplicate section IDs detected: ${duplicates
                .map(d => `${d.id} (keys: ${d.keys.join(', ')})`)
                .join('; ')}`,
            expected: 'unique section IDs',
            received: 'duplicates',
        });
    }
    return errors;
}
function validateEmptyText(gamebook) {
    const warnings = [];
    for (const [key, section] of Object.entries(gamebook.sections || {})) {
        const rawHtml = section?.presentation_html || section?.html || '';
        const text = stripHtmlToText(rawHtml);
        if (!text) {
            warnings.push({
                path: `/sections/${key}/presentation_html`,
                message: `Section "${key}" has no text`,
            });
        }
    }
    return warnings;
}
function validateNoChoices(gamebook) {
    const warnings = [];
    
    /**
     * Check if sequence has any navigation (choices or conditional events with targets).
     * Navigation can be via:
     * - Direct choices (kind === 'choice')
     * - Conditional events (stat_check, test_luck, item_check, etc.) with targetSection outcomes
     */
    function hasNavigation(sequence) {
        if (!Array.isArray(sequence)) return false;
        for (const event of sequence) {
            if (!event) continue;
            const kind = event.kind;
            
            if (kind === 'choice') {
                if (event.targetSection) return true;
            } else if (kind === 'stat_check') {
                // Check pass/fail outcomes
                if ((event.pass && event.pass.targetSection) || 
                    (event.fail && event.fail.targetSection)) {
                    return true;
                }
            } else if (kind === 'stat_change') {
                // Check else outcome
                if (event.else && event.else.targetSection) {
                    return true;
                }
            } else if (kind === 'test_luck') {
                // Check lucky/unlucky outcomes
                if ((event.lucky && event.lucky.targetSection) || 
                    (event.unlucky && event.unlucky.targetSection)) {
                    return true;
                }
            } else if (kind === 'item_check' || kind === 'state_check') {
                // Check has/missing outcomes
                if ((event.has && event.has.targetSection) || 
                    (event.missing && event.missing.targetSection)) {
                    return true;
                }
            } else if (kind === 'combat') {
                // Check combat outcomes
                const outcomes = event.outcomes || {};
                if ((outcomes.win && outcomes.win.targetSection) ||
                    (outcomes.lose && outcomes.lose.targetSection) ||
                    (outcomes.escape && outcomes.escape.targetSection)) {
                    return true;
                }
            } else if (kind === 'death') {
                // Check death outcome
                if (event.outcome && event.outcome.targetSection) {
                    return true;
                }
            } else {
                // Generic event with targetSection
                if (event.targetSection) {
                    return true;
                }
            }
        }
        return false;
    }
    
    for (const [key, section] of Object.entries(gamebook.sections || {})) {
        if (!section?.isGameplaySection) {
            continue;
        }
        if (section?.end_game) {
            continue;
        }
        if (section?.provenance?.stub) {
            continue;
        }
        const sequence = section?.sequence || [];
        if (!hasNavigation(sequence)) {
            warnings.push({
                path: `/sections/${key}/sequence`,
                message: `Gameplay section "${key}" has no choices (potential dead end)`,
            });
        }
    }
    return warnings;
}
/**
 * Validate gamebook using JSON Schema
 */
function validateWithSchema(gamebook) {
    const schema = loadSchema();
    // Allow additional properties - extra data is fine, we just validate what we care about
    const ajv = new ajv_1.default({
        allErrors: true,
        verbose: true,
        strict: false, // Don't be strict about additional properties
        removeAdditional: false, // Don't remove additional properties
        allowUnionTypes: true, // Allow union types
    });
    const validate = ajv.compile(schema);
    const valid = validate(gamebook);
    if (!valid && validate.errors) {
        return validate.errors.map(ajvErrorToValidationError);
    }
    return [];
}
/**
 * Validate section ID matches its key
 */
function validateSectionIds(gamebook) {
    const errors = [];
    for (const [key, section] of Object.entries(gamebook.sections)) {
        if (section.id !== key) {
            errors.push({
                path: `/sections/${key}/id`,
                message: `Section ID "${section.id}" does not match its key "${key}"`,
                expected: key,
                received: section.id,
            });
        }
    }
    return errors;
}
/**
 * Validate all sequence target sections exist
 */
function validateSequenceTargets(gamebook) {
    const errors = [];
    const sectionIds = new Set(Object.keys(gamebook.sections));
    const validateEvents = (events, pathPrefix, sectionKey) => {
        if (!Array.isArray(events))
            return;
        events.forEach((event, index) => {
            const pathBase = `${pathPrefix}/${index}`;
            const kind = event.kind;
            const checkOutcome = (outcome, pathSuffix) => {
                if (!outcome)
                    return;
                if (outcome.targetSection) {
                    if (!sectionIds.has(outcome.targetSection)) {
                        errors.push({
                            path: `${pathBase}/${pathSuffix}/targetSection`,
                            message: `Sequence target section "${outcome.targetSection}" does not exist`,
                            expected: 'existing section ID',
                            received: outcome.targetSection,
                        });
                    }
                }
                else if (!outcome.terminal) {
                    errors.push({
                        path: `${pathBase}/${pathSuffix}`,
                        message: "Outcome missing targetSection or terminal outcome",
                        expected: "targetSection or terminal",
                        received: "none",
                    });
                }
            };
            if (kind === 'choice') {
                if (!event.targetSection) {
                    errors.push({
                        path: `${pathBase}/targetSection`,
                        message: "Choice event missing targetSection",
                        expected: "targetSection",
                        received: "none",
                    });
                }
                else if (!sectionIds.has(event.targetSection)) {
                    errors.push({
                        path: `${pathBase}/targetSection`,
                        message: `Sequence target section "${event.targetSection}" does not exist`,
                        expected: 'existing section ID',
                        received: event.targetSection,
                    });
                }
                return;
            }
            if (kind === 'stat_check') {
                checkOutcome(event.pass, 'pass');
                checkOutcome(event.fail, 'fail');
                return;
            }
            if (kind === 'stat_change') {
                checkOutcome(event.else, 'else');
                return;
            }
            if (kind === 'test_luck') {
                checkOutcome(event.lucky, 'lucky');
                checkOutcome(event.unlucky, 'unlucky');
                return;
            }
            if (kind === 'item_check' || kind === 'state_check') {
                checkOutcome(event.has, 'has');
                checkOutcome(event.missing, 'missing');
                if (kind === 'item_check' && Array.isArray(event.itemsAll)) {
                    if (event.itemsAll.length < 2) {
                        errors.push({
                            path: `${pathBase}/itemsAll`,
                            message: 'itemsAll must include at least two items',
                            expected: 'array length >= 2',
                            received: String(event.itemsAll.length)
                        });
                    }
                    event.itemsAll.forEach((item, idx) => {
                        if (typeof item !== 'string' || item.trim().length === 0) {
                            errors.push({
                                path: `${pathBase}/itemsAll/${idx}`,
                                message: 'itemsAll entries must be non-empty strings',
                                expected: 'non-empty string',
                                received: typeof item
                            });
                        }
                    });
                }
                return;
            }
            if (kind === 'conditional') {
                validateEvents(event.then || [], `${pathBase}/then`, sectionKey);
                validateEvents(event.else || [], `${pathBase}/else`, sectionKey);
                return;
            }
            if (kind === 'combat') {
                const outcomes = event.outcomes || {};
                checkOutcome(outcomes.win, 'outcomes/win');
                checkOutcome(outcomes.lose, 'outcomes/lose');
                checkOutcome(outcomes.escape, 'outcomes/escape');
                return;
            }
            if (kind === 'death') {
                checkOutcome(event.outcome, 'outcome');
            }
        });
    };
    for (const [sectionKey, section] of Object.entries(gamebook.sections)) {
        if (!section.isGameplaySection)
            continue;
        validateEvents(section.sequence || [], `/sections/${sectionKey}/sequence`, sectionKey);
    }
    return errors;
}
/**
 * Find all reachable sections from startSection using BFS
 */
function findReachableSections(gamebook) {
    const reachable = new Set();
    const queue = [gamebook.metadata.startSection];
    const visited = new Set();
    while (queue.length > 0) {
        const currentId = queue.shift();
        if (visited.has(currentId))
            continue;
        visited.add(currentId);
        const section = gamebook.sections[currentId];
        if (!section || !section.isGameplaySection)
            continue;
        reachable.add(currentId);
        const pushTargetsFromEvents = (events) => {
            if (!Array.isArray(events))
                return;
            events.forEach(event => {
                const kind = event.kind;
                const pushTarget = (outcome) => {
                    if (outcome && outcome.targetSection && !visited.has(outcome.targetSection)) {
                        queue.push(outcome.targetSection);
                    }
                };
                if (kind === 'choice' && event.targetSection) {
                    pushTarget({ targetSection: event.targetSection });
                }
                else if (kind === 'stat_check') {
                    pushTarget(event.pass);
                    pushTarget(event.fail);
                }
                else if (kind === 'stat_change') {
                    pushTarget(event.else);
                }
                else if (kind === 'test_luck') {
                    pushTarget(event.lucky);
                    pushTarget(event.unlucky);
                }
                else if (kind === 'item_check' || kind === 'state_check') {
                    pushTarget(event.has);
                    pushTarget(event.missing);
                }
                else if (kind === 'conditional') {
                    pushTargetsFromEvents(event.then || []);
                    pushTargetsFromEvents(event.else || []);
                }
                else if (kind === 'combat') {
                    const outcomes = event.outcomes || {};
                    pushTarget(outcomes.win);
                    pushTarget(outcomes.lose);
                    pushTarget(outcomes.escape);
                }
                else if (kind === 'death') {
                    pushTarget(event.outcome);
                }
                else if (event.targetSection) {
                    pushTarget({ targetSection: event.targetSection });
                }
            });
        };
        pushTargetsFromEvents(section.sequence || []);
    }
    return reachable;
}
/**
 * Identify unreachable gameplay sections and entry points
 *
 * Entry points are unreachable sections that are not referenced by other unreachable sections.
 * This helps distinguish root causes (e.g., 8 orphaned sections) from descendants (e.g., 13 sections in chains).
 */
function findUnreachableSections(gamebook) {
    const warnings = [];
    const reachable = findReachableSections(gamebook);
    const unreachableSections = [];

    // Find all unreachable sections
    for (const [sectionKey, section] of Object.entries(gamebook.sections)) {
        if (section.isGameplaySection && !reachable.has(sectionKey)) {
            unreachableSections.push(sectionKey);
            warnings.push({
                path: `/sections/${sectionKey}`,
                message: `Gameplay section "${sectionKey}" is unreachable from startSection "${gamebook.metadata.startSection}"`,
            });
        }
    }

    // Build a map of which unreachable sections reference other unreachable sections
    const unreachableReferences = new Set();
    for (const sectionKey of unreachableSections) {
        const section = gamebook.sections[sectionKey];
        const sequence = section.sequence || [];

        // Extract all target sections from sequence events
        for (const event of sequence) {
            const targets = extractTargetsFromEvent(event);
            for (const target of targets) {
                if (unreachableSections.includes(target)) {
                    unreachableReferences.add(target);
                }
            }
        }
    }

    // Entry points are unreachable sections NOT referenced by other unreachable sections
    const entryPoints = unreachableSections.filter(id => !unreachableReferences.has(id));

    // Detect manual conditional navigation sections (unreachable via code but reachable via manual instructions)
    const manualNavigationSections = detectManualNavigationSections(gamebook, entryPoints);

    // Add metadata to first warning (if any)
    if (warnings.length > 0 && entryPoints.length > 0) {
        warnings[0].entryPoints = entryPoints;
        warnings[0].manualNavigationSections = manualNavigationSections;
    }

    return warnings;
}

/**
 * Detect sections that are reachable via manual conditional navigation
 *
 * These are sections that appear unreachable via extracted choices, but are actually
 * reachable through "turn to X" instructions in the text (not code-extractable).
 *
 * Detection patterns:
 * 1. Section text contains password/countersign usage (e.g., "You give the proper countersign")
 * 2. Numeric section IDs that might be password references (e.g., section 7 for "seven")
 * 3. Sections with conditional access language (e.g., "You use the code-words")
 */
function detectManualNavigationSections(gamebook, entryPoints) {
    const manualNavigation = [];

    for (const sectionId of entryPoints) {
        const section = gamebook.sections[sectionId];
        if (!section) continue;

        const html = section.presentation_html || '';
        const text = html.toLowerCase();

        // Pattern 1: Password/countersign usage (player is already using something they learned)
        const hasPasswordUsage = /\b(you give|you use|you show|you present)\b.*\b(password|countersign|code-?word|map reference)\b/i.test(text);

        // Pattern 2: Conditional access language at the start
        const hasConditionalStart = /^<[^>]*>\s*(you give|you use|you have|what will you do)/i.test(html);

        // Pattern 3: Numeric section ID that could be a password (small numbers or round numbers)
        const numericId = parseInt(sectionId);
        const isPotentialPasswordNumber = !isNaN(numericId) && (
            (numericId >= 1 && numericId <= 20) ||  // Small numbers (one, two, ..., twenty)
            (numericId % 100 === 0)  // Round numbers (100, 200, 300)
        );

        // Pattern 4: Text mentions challenge or encounter by name (e.g., "Challenge Minos")
        const hasNamedChallenge = /\b(challenge|meet|confront|face)\b.*\b[A-Z][a-z]+\b/i.test(text);

        if (hasPasswordUsage || (hasConditionalStart && isPotentialPasswordNumber) || hasNamedChallenge) {
            manualNavigation.push(sectionId);
        }
    }

    return manualNavigation;
}

/**
 * Extract target sections from a sequence event
 */
function extractTargetsFromEvent(event) {
    const targets = [];
    const kind = event.kind;

    if (kind === 'choice' && event.targetSection) {
        targets.push(event.targetSection);
    } else if (kind === 'stat_check' || kind === 'test_luck') {
        for (const key of ['pass', 'fail', 'lucky', 'unlucky']) {
            const outcome = event[key];
            if (outcome && outcome.targetSection) {
                targets.push(outcome.targetSection);
            }
        }
    } else if (kind === 'item_check' || kind === 'state_check') {
        for (const key of ['has', 'missing']) {
            const outcome = event[key];
            if (outcome && outcome.targetSection) {
                targets.push(outcome.targetSection);
            }
        }
    } else if (kind === 'combat') {
        const outcomes = event.outcomes || {};
        for (const key of ['win', 'lose', 'escape']) {
            const outcome = outcomes[key];
            if (outcome && outcome.targetSection) {
                targets.push(outcome.targetSection);
            }
        }
    } else if (kind === 'death') {
        const outcome = event.outcome;
        if (outcome && outcome.targetSection) {
            targets.push(outcome.targetSection);
        }
    } else if (event.targetSection) {
        // Generic fallback for events with targetSection
        targets.push(event.targetSection);
    }

    return targets;
}
/**
 * Validate stat modifications have valid stat names
 * (This is already covered by JSON Schema, but we can add custom validation if needed)
 */
function validateStatModifications(_gamebook) {
    // JSON Schema already validates stat enum, so this is mainly for custom checks if needed
    // For now, we rely on schema validation
    return [];
}
/**
 * Validate item references have valid actions
 * (This is already covered by JSON Schema)
 */
function validateItemActions(_gamebook) {
    // JSON Schema already validates action enum
    return [];
}
/**
 * Validate combat encounters have valid creature stats
 * (This is already covered by JSON Schema, but we can add range checks if needed)
 */
function validateCreatureStats(_gamebook) {
    // JSON Schema validates types, but we could add range checks here if needed
    // For now, we rely on schema validation
    return [];
}

function getValidatorVersion() {
    const pkgPath = path.join(__dirname, 'package.json');
    if (!fs.existsSync(pkgPath)) {
        return null;
    }
    try {
        const pkg = JSON.parse(fs.readFileSync(pkgPath, 'utf-8'));
        const name = pkg.name;
        const version = pkg.version;
        if (name && version) {
            return `${name}@${version}`;
        }
        return version || null;
    }
    catch (_a) {
        return null;
    }
}
/**
 * Comprehensive gamebook validation
 *
 * Validates a gamebook JSON against the JSON Schema and performs custom validation
 * checks for sequence targets, reachability, etc.
 *
 * @param gamebook - The gamebook JSON to validate
 * @returns Validation result with errors and warnings
 */
function validateGamebook(gamebook) {
    const errors = [];
    const warnings = [];
    const validatorVersion = getValidatorVersion();
    // 1. JSON Schema validation
    errors.push(...validateWithSchema(gamebook));
    // Only proceed with other validations if basic structure is valid
    // (i.e., metadata and sections exist)
    const hasBasicStructure = gamebook.metadata && gamebook.sections;
    if (hasBasicStructure) {
        // 2. Validate startSection exists in sections
        if (gamebook.metadata.startSection && !(gamebook.metadata.startSection in gamebook.sections)) {
            errors.push({
                path: '/metadata/startSection',
                message: `startSection "${gamebook.metadata.startSection}" does not exist in sections`,
                expected: 'existing section ID',
                received: gamebook.metadata.startSection,
            });
        }
        // 3. Section ID validation
        errors.push(...validateSectionIds(gamebook));
        // 4. Missing/duplicate section validation
        errors.push(...validateMissingSections(gamebook));
        errors.push(...validateDuplicateSections(gamebook));
        // 5. Sequence target validation
        errors.push(...validateSequenceTargets(gamebook));
        // 6. Stat modifications validation (schema covers this, but placeholder for custom checks)
        errors.push(...validateStatModifications(gamebook));
        // 7. Item actions validation (schema covers this)
        errors.push(...validateItemActions(gamebook));
        // 8. Creature stats validation (schema covers this)
        errors.push(...validateCreatureStats(gamebook));
        // 9. Empty text / no-choice warnings
        warnings.push(...validateEmptyText(gamebook));
        warnings.push(...validateNoChoices(gamebook));
        // 10. Reachability analysis (warnings, not errors)
        // Only run if startSection exists and is valid
        if (gamebook.metadata.startSection && gamebook.sections[gamebook.metadata.startSection]) {
            warnings.push(...findUnreachableSections(gamebook));
        }
        if (validatorVersion) {
            const expectedVersion = gamebook.metadata.validatorVersion;
            if (!expectedVersion) {
                warnings.push({
                    path: '/metadata/validatorVersion',
                    message: 'metadata.validatorVersion missing; version mismatch checks disabled',
                });
            }
            else if (expectedVersion !== validatorVersion) {
                warnings.push({
                    path: '/metadata/validatorVersion',
                    message: `Validator version mismatch (gamebook expects ${expectedVersion}, validator is ${validatorVersion})`,
                });
            }
        }
    }
    // Calculate summary statistics (only if basic structure exists)
    let summary;
    if (hasBasicStructure && gamebook.sections) {
        const totalSections = Object.keys(gamebook.sections).length;
        const gameplaySections = Object.values(gamebook.sections).filter(s => s.isGameplaySection).length;
        let reachableSections = 0;
        let unreachableSections = 0;
        let unreachableEntryPoints = 0;
        let manualNavigationSections = 0;
        if (gamebook.metadata.startSection && gamebook.sections[gamebook.metadata.startSection]) {
            const reachable = findReachableSections(gamebook);
            reachableSections = reachable.size;
            unreachableSections = warnings.filter(w => w.message.includes('unreachable')).length;

            // Extract entry points and manual navigation counts from warnings metadata
            const firstUnreachableWarning = warnings.find(w => w.message.includes('unreachable'));
            if (firstUnreachableWarning && firstUnreachableWarning.entryPoints) {
                unreachableEntryPoints = firstUnreachableWarning.entryPoints.length;
            }
            if (firstUnreachableWarning && firstUnreachableWarning.manualNavigationSections) {
                manualNavigationSections = firstUnreachableWarning.manualNavigationSections.length;
            }
        }
        summary = {
            totalSections,
            gameplaySections,
            reachableSections,
            unreachableSections,
            unreachableEntryPoints,
            manualNavigationSections,
            totalErrors: errors.length,
            totalWarnings: warnings.length,
        };
    }
    return {
        valid: errors.length === 0,
        errors,
        warnings,
        summary,
        validatorVersion: validatorVersion || undefined,
        versionMismatch: Boolean(validatorVersion &&
            gamebook?.metadata?.validatorVersion &&
            gamebook.metadata.validatorVersion !== validatorVersion),
    };
}
/**
 * Legacy validation function for backward compatibility
 *
 * @deprecated Use validateGamebook() instead
 */
function validateGamebookJSON(json) {
    const result = validateGamebook(json);
    if (!result.valid) {
        const errorMessages = result.errors.map(e => `${e.path}: ${e.message}`).join('\n');
        throw new Error(`Gamebook validation failed:\n${errorMessages}`);
    }
}
//# sourceMappingURL=validation.js.map
