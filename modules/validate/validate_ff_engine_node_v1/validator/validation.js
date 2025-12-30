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
        // Validate navigation edges
        if (section.navigation) {
            section.navigation.forEach((link, index) => {
                if (!sectionIds.has(link.targetSection)) {
                    errors.push({
                        path: `/sections/${sectionKey}/navigation/${index}/targetSection`,
                        message: `Navigation target section "${link.targetSection}" does not exist`,
                        expected: 'existing section ID',
                        received: link.targetSection,
                    });
                }
            });
        }
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
        // Add navigation edges
        if (section.navigation) {
            section.navigation.forEach(link => {
                if (!visited.has(link.targetSection)) {
                    queue.push(link.targetSection);
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
        // 5. Stat modifications validation (schema covers this, but placeholder for custom checks)
        errors.push(...validateStatModifications(gamebook));
        // 6. Item actions validation (schema covers this)
        errors.push(...validateItemActions(gamebook));
        // 7. Creature stats validation (schema covers this)
        errors.push(...validateCreatureStats(gamebook));
        // 8. Reachability analysis (warnings, not errors)
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
