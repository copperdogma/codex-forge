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
import { GamebookJSON } from './types';
/**
 * Validation error with path and message
 */
export interface ValidationError {
    /** JSON path to the error (e.g., "/sections/1/sequence/0/targetSection") */
    path: string;
    /** Human-readable error message */
    message: string;
    /** Expected value (if applicable) */
    expected?: string;
    /** Received value (if applicable) */
    received?: string;
}
/**
 * Validation warning (non-fatal issues)
 */
export interface ValidationWarning {
    /** JSON path to the warning */
    path: string;
    /** Human-readable warning message */
    message: string;
}
/**
 * Validation result summary statistics
 */
export interface ValidationSummary {
    /** Total number of sections in the gamebook */
    totalSections: number;
    /** Number of gameplay sections */
    gameplaySections: number;
    /** Number of sections reachable from startSection */
    reachableSections: number;
    /** Number of unreachable gameplay sections */
    unreachableSections: number;
    /** Total number of validation errors */
    totalErrors: number;
    /** Total number of validation warnings */
    totalWarnings: number;
}
/**
 * Validation result
 */
export interface ValidationResult {
    /** Whether the gamebook is valid */
    valid: boolean;
    /** Array of validation errors */
    errors: ValidationError[];
    /** Array of validation warnings */
    warnings: ValidationWarning[];
    /** Summary statistics (optional, included when available) */
    summary?: ValidationSummary;
    /** Validator version used for this validation run */
    validatorVersion?: string;
    /** Whether the validator version mismatched gamebook metadata */
    versionMismatch?: boolean;
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
export declare function validateGamebook(gamebook: GamebookJSON): ValidationResult;
/**
 * Legacy validation function for backward compatibility
 *
 * @deprecated Use validateGamebook() instead
 */
export declare function validateGamebookJSON(json: GamebookJSON): void;
//# sourceMappingURL=validation.d.ts.map
