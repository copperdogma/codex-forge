#!/usr/bin/env node
"use strict";
/**
 * Standalone CLI validator for Fighting Fantasy gamebook JSON files
 *
 * This tool can be run independently of the engine to validate gamebook JSON files.
 * Useful for manual JSON creators and the PDF parser project.
 *
 * Usage:
 *   node dist/validator/cli-validator.js <gamebook.json> [--json]
 *   or
 *   npm run validate <gamebook.json> [--json]
 *
 * Options:
 *   --json    Output validation results as JSON (useful for programmatic use)
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
Object.defineProperty(exports, "__esModule", { value: true });
const fs = __importStar(require("fs"));
const validation_1 = require("./validation");
function main() {
    const args = process.argv.slice(2);
    if (args.length === 0) {
        console.error('Usage: node cli-validator.js <gamebook.json> [--json]');
        console.error('   or: npm run validate <gamebook.json> [--json]');
        console.error('\nOptions:');
        console.error('  --json    Output validation results as JSON');
        process.exit(1);
    }
    // Check for --json flag
    const jsonOutput = args.includes('--json');
    const filePath = args.find(arg => arg !== '--json');
    if (!filePath) {
        console.error('Error: No gamebook file specified');
        process.exit(1);
    }
    if (!fs.existsSync(filePath)) {
        console.error(`Error: File not found: ${filePath}`);
        process.exit(1);
    }
    try {
        const fileContent = fs.readFileSync(filePath, 'utf-8');
        const gamebook = JSON.parse(fileContent);
        const result = (0, validation_1.validateGamebook)(gamebook);
        // Output as JSON if requested
        if (jsonOutput) {
            console.log(JSON.stringify(result, null, 2));
            process.exit(result.valid ? 0 : 1);
            return;
        }
        // Human-readable output
        if (result.valid) {
            console.log('✓ Gamebook is valid!');
            // Show summary statistics
            if (result.summary) {
                console.log('\nSummary:');
                console.log(`  Total sections: ${result.summary.totalSections}`);
                console.log(`  Gameplay sections: ${result.summary.gameplaySections}`);
                console.log(`  Reachable sections: ${result.summary.reachableSections}`);
                if (result.summary.unreachableSections > 0) {
                    console.log(`  Unreachable sections: ${result.summary.unreachableSections}`);
                }
            }
            if (result.warnings.length > 0) {
                console.log(`\n⚠ Found ${result.warnings.length} warning(s):`);
                result.warnings.forEach(warning => {
                    console.log(`  ${warning.path}: ${warning.message}`);
                });
            }
            process.exit(0);
        }
        else {
            console.error('✗ Gamebook validation failed!');
            console.error(`\nFound ${result.errors.length} error(s):`);
            result.errors.forEach(error => {
                console.error(`  ${error.path}: ${error.message}`);
                if (error.expected && error.received) {
                    console.error(`    Expected: ${error.expected}`);
                    console.error(`    Received: ${error.received}`);
                }
            });
            // Show summary statistics
            if (result.summary) {
                console.error('\nSummary:');
                console.error(`  Total sections: ${result.summary.totalSections}`);
                console.error(`  Gameplay sections: ${result.summary.gameplaySections}`);
                console.error(`  Reachable sections: ${result.summary.reachableSections}`);
                if (result.summary.unreachableSections > 0) {
                    console.error(`  Unreachable sections: ${result.summary.unreachableSections}`);
                }
                console.error(`  Errors: ${result.summary.totalErrors}`);
                if (result.summary.totalWarnings > 0) {
                    console.error(`  Warnings: ${result.summary.totalWarnings}`);
                }
            }
            if (result.warnings.length > 0) {
                console.error(`\n⚠ Found ${result.warnings.length} warning(s):`);
                result.warnings.forEach(warning => {
                    console.error(`  ${warning.path}: ${warning.message}`);
                });
            }
            process.exit(1);
        }
    }
    catch (error) {
        if (error instanceof SyntaxError) {
            console.error(`Error: Invalid JSON in ${filePath}`);
            console.error(error.message);
            process.exit(1);
        }
        else {
            console.error(`Error: ${error instanceof Error ? error.message : String(error)}`);
            process.exit(1);
        }
    }
}
if (require.main === module) {
    main();
}
//# sourceMappingURL=cli-validator.js.map