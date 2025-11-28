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
 * - Validates all navigation paths
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
 * Validate all navigation target sections exist
 */
function validateNavigationTargets(gamebook) {
    const errors = [];
    const sectionIds = new Set(Object.keys(gamebook.sections));
    for (const [sectionKey, section] of Object.entries(gamebook.sections)) {
        if (!section.isGameplaySection)
            continue;
        // Validate navigation links
        if (section.navigationLinks) {
            section.navigationLinks.forEach((link, index) => {
                if (!sectionIds.has(link.targetSection)) {
                    errors.push({
                        path: `/sections/${sectionKey}/navigationLinks/${index}/targetSection`,
                        message: `Navigation target section "${link.targetSection}" does not exist`,
                        expected: 'existing section ID',
                        received: link.targetSection,
                    });
                }
            });
        }
        // Validate conditional navigation
        if (section.conditionalNavigation) {
            section.conditionalNavigation.forEach((conditional, condIndex) => {
                if (!sectionIds.has(conditional.ifTrue.targetSection)) {
                    errors.push({
                        path: `/sections/${sectionKey}/conditionalNavigation/${condIndex}/ifTrue/targetSection`,
                        message: `Conditional navigation ifTrue target section "${conditional.ifTrue.targetSection}" does not exist`,
                        expected: 'existing section ID',
                        received: conditional.ifTrue.targetSection,
                    });
                }
                if (!sectionIds.has(conditional.ifFalse.targetSection)) {
                    errors.push({
                        path: `/sections/${sectionKey}/conditionalNavigation/${condIndex}/ifFalse/targetSection`,
                        message: `Conditional navigation ifFalse target section "${conditional.ifFalse.targetSection}" does not exist`,
                        expected: 'existing section ID',
                        received: conditional.ifFalse.targetSection,
                    });
                }
            });
        }
    }
    return errors;
}
/**
 * Validate combat encounter target sections
 */
function validateCombatTargets(gamebook) {
    const errors = [];
    const sectionIds = new Set(Object.keys(gamebook.sections));
    for (const [sectionKey, section] of Object.entries(gamebook.sections)) {
        if (!section.isGameplaySection || !section.combat)
            continue;
        const combat = section.combat;
        // Validate win section
        if (!sectionIds.has(combat.winSection)) {
            errors.push({
                path: `/sections/${sectionKey}/combat/winSection`,
                message: `Combat winSection "${combat.winSection}" does not exist`,
                expected: 'existing section ID',
                received: combat.winSection,
            });
        }
        // Validate lose section (if present)
        if (combat.loseSection && !sectionIds.has(combat.loseSection)) {
            errors.push({
                path: `/sections/${sectionKey}/combat/loseSection`,
                message: `Combat loseSection "${combat.loseSection}" does not exist`,
                expected: 'existing section ID',
                received: combat.loseSection,
            });
        }
        // Validate escape section (if present)
        if (combat.creature.escapeSection && !sectionIds.has(combat.creature.escapeSection)) {
            errors.push({
                path: `/sections/${sectionKey}/combat/creature/escapeSection`,
                message: `Combat escapeSection "${combat.creature.escapeSection}" does not exist`,
                expected: 'existing section ID',
                received: combat.creature.escapeSection,
            });
        }
    }
    return errors;
}
/**
 * Validate Test Your Luck target sections
 */
function validateTestYourLuckTargets(gamebook) {
    const errors = [];
    const sectionIds = new Set(Object.keys(gamebook.sections));
    for (const [sectionKey, section] of Object.entries(gamebook.sections)) {
        if (!section.isGameplaySection || !section.testYourLuck)
            continue;
        section.testYourLuck.forEach((tyl, index) => {
            if (!sectionIds.has(tyl.luckySection)) {
                errors.push({
                    path: `/sections/${sectionKey}/testYourLuck/${index}/luckySection`,
                    message: `Test Your Luck luckySection "${tyl.luckySection}" does not exist`,
                    expected: 'existing section ID',
                    received: tyl.luckySection,
                });
            }
            if (!sectionIds.has(tyl.unluckySection)) {
                errors.push({
                    path: `/sections/${sectionKey}/testYourLuck/${index}/unluckySection`,
                    message: `Test Your Luck unluckySection "${tyl.unluckySection}" does not exist`,
                    expected: 'existing section ID',
                    received: tyl.unluckySection,
                });
            }
        });
    }
    return errors;
}
/**
 * Validate item check target sections
 */
function validateItemCheckTargets(gamebook) {
    const errors = [];
    const sectionIds = new Set(Object.keys(gamebook.sections));
    for (const [sectionKey, section] of Object.entries(gamebook.sections)) {
        if (!section.isGameplaySection || !section.items)
            continue;
        section.items.forEach((item, index) => {
            if (item.action === 'check') {
                if (item.checkSuccessSection && !sectionIds.has(item.checkSuccessSection)) {
                    errors.push({
                        path: `/sections/${sectionKey}/items/${index}/checkSuccessSection`,
                        message: `Item check checkSuccessSection "${item.checkSuccessSection}" does not exist`,
                        expected: 'existing section ID',
                        received: item.checkSuccessSection,
                    });
                }
                if (item.checkFailureSection && !sectionIds.has(item.checkFailureSection)) {
                    errors.push({
                        path: `/sections/${sectionKey}/items/${index}/checkFailureSection`,
                        message: `Item check checkFailureSection "${item.checkFailureSection}" does not exist`,
                        expected: 'existing section ID',
                        received: item.checkFailureSection,
                    });
                }
            }
        });
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
        // Add navigation links
        if (section.navigationLinks) {
            section.navigationLinks.forEach(link => {
                if (!visited.has(link.targetSection)) {
                    queue.push(link.targetSection);
                }
            });
        }
        // Add conditional navigation (both paths)
        if (section.conditionalNavigation) {
            section.conditionalNavigation.forEach(conditional => {
                if (!visited.has(conditional.ifTrue.targetSection)) {
                    queue.push(conditional.ifTrue.targetSection);
                }
                if (!visited.has(conditional.ifFalse.targetSection)) {
                    queue.push(conditional.ifFalse.targetSection);
                }
            });
        }
        // Add combat outcomes
        if (section.combat) {
            if (!visited.has(section.combat.winSection)) {
                queue.push(section.combat.winSection);
            }
            if (section.combat.loseSection && !visited.has(section.combat.loseSection)) {
                queue.push(section.combat.loseSection);
            }
            if (section.combat.creature.escapeSection && !visited.has(section.combat.creature.escapeSection)) {
                queue.push(section.combat.creature.escapeSection);
            }
        }
        // Add Test Your Luck outcomes
        if (section.testYourLuck) {
            section.testYourLuck.forEach(tyl => {
                if (!visited.has(tyl.luckySection)) {
                    queue.push(tyl.luckySection);
                }
                if (!visited.has(tyl.unluckySection)) {
                    queue.push(tyl.unluckySection);
                }
            });
        }
        // Add item check outcomes
        if (section.items) {
            section.items.forEach(item => {
                if (item.action === 'check') {
                    if (item.checkSuccessSection && !visited.has(item.checkSuccessSection)) {
                        queue.push(item.checkSuccessSection);
                    }
                    if (item.checkFailureSection && !visited.has(item.checkFailureSection)) {
                        queue.push(item.checkFailureSection);
                    }
                }
            });
        }
    }
    return reachable;
}
/**
 * Identify unreachable gameplay sections
 */
function findUnreachableSections(gamebook) {
    const warnings = [];
    const reachable = findReachableSections(gamebook);
    for (const [sectionKey, section] of Object.entries(gamebook.sections)) {
        // Only warn about unreachable gameplay sections
        if (section.isGameplaySection && !reachable.has(sectionKey)) {
            warnings.push({
                path: `/sections/${sectionKey}`,
                message: `Gameplay section "${sectionKey}" is unreachable from startSection "${gamebook.metadata.startSection}"`,
            });
        }
    }
    return warnings;
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
/**
 * Comprehensive gamebook validation
 *
 * Validates a gamebook JSON against the JSON Schema and performs custom validation
 * checks for navigation paths, reachability, etc.
 *
 * @param gamebook - The gamebook JSON to validate
 * @returns Validation result with errors and warnings
 */
function validateGamebook(gamebook) {
    const errors = [];
    const warnings = [];
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
        // 4. Navigation target validation
        errors.push(...validateNavigationTargets(gamebook));
        // 5. Combat target validation
        errors.push(...validateCombatTargets(gamebook));
        // 6. Test Your Luck target validation
        errors.push(...validateTestYourLuckTargets(gamebook));
        // 7. Item check target validation
        errors.push(...validateItemCheckTargets(gamebook));
        // 8. Stat modifications validation (schema covers this, but placeholder for custom checks)
        errors.push(...validateStatModifications(gamebook));
        // 9. Item actions validation (schema covers this)
        errors.push(...validateItemActions(gamebook));
        // 10. Creature stats validation (schema covers this)
        errors.push(...validateCreatureStats(gamebook));
        // 11. Reachability analysis (warnings, not errors)
        // Only run if startSection exists and is valid
        if (gamebook.metadata.startSection && gamebook.sections[gamebook.metadata.startSection]) {
            warnings.push(...findUnreachableSections(gamebook));
        }
    }
    // Calculate summary statistics (only if basic structure exists)
    let summary;
    if (hasBasicStructure && gamebook.sections) {
        const totalSections = Object.keys(gamebook.sections).length;
        const gameplaySections = Object.values(gamebook.sections).filter(s => s.isGameplaySection).length;
        let reachableSections = 0;
        let unreachableSections = 0;
        if (gamebook.metadata.startSection && gamebook.sections[gamebook.metadata.startSection]) {
            const reachable = findReachableSections(gamebook);
            reachableSections = reachable.size;
            unreachableSections = warnings.filter(w => w.message.includes('unreachable')).length;
        }
        summary = {
            totalSections,
            gameplaySections,
            reachableSections,
            unreachableSections,
            totalErrors: errors.length,
            totalWarnings: warnings.length,
        };
    }
    return {
        valid: errors.length === 0,
        errors,
        warnings,
        summary,
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