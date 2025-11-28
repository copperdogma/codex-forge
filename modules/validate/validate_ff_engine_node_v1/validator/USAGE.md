# Validation Usage Guide

Complete guide for using the Fighting Fantasy gamebook validator.

## Table of Contents

- [Quick Start](#quick-start)
- [CLI Usage](#cli-usage)
- [Library Usage](#library-usage)
- [Integration Examples](#integration-examples)
- [Error Handling](#error-handling)
- [Validation Result Structure](#validation-result-structure)

## Quick Start

### Installation

```bash
# Install the only required dependency
npm install ajv
```

### Basic Usage

**CLI:**
```bash
node cli-validator.js gamebook.json
node cli-validator.js gamebook.json --json  # JSON output
```

**Library:**
```javascript
const { validateGamebook } = require('./validation');
const result = validateGamebook(gamebookData);
```

---

## CLI Usage

### Basic Validation

```bash
node cli-validator.js gamebook.json
```

### JSON Output

Get machine-readable JSON output:

```bash
node cli-validator.js gamebook.json --json
```

Output:
```json
{
  "valid": false,
  "errors": [
    {
      "path": "/sections/1/navigationLinks/0/targetSection",
      "message": "Navigation target section \"999\" does not exist",
      "expected": "existing section ID",
      "received": "999"
    }
  ],
  "warnings": [
    {
      "path": "/sections/999",
      "message": "Gameplay section \"999\" is unreachable from startSection \"1\""
    }
  ],
  "summary": {
    "totalSections": 10,
    "gameplaySections": 8,
    "reachableSections": 7,
    "unreachableSections": 1,
    "totalErrors": 1,
    "totalWarnings": 1
  }
}
```

### CI/CD Integration

```bash
#!/bin/bash
# Validate gamebook in CI pipeline
if ! node cli-validator.js gamebook.json; then
  echo "Validation failed!"
  exit 1
fi
echo "Validation passed!"
```

---

## Library Usage

### TypeScript/JavaScript

```typescript
import { validateGamebook } from './validation';
import type { GamebookJSON, ValidationResult } from './types';

const gamebook: GamebookJSON = JSON.parse(fs.readFileSync('gamebook.json', 'utf-8'));
const result: ValidationResult = validateGamebook(gamebook);

if (result.valid) {
  console.log('✓ Valid!');
  if (result.summary) {
    console.log(`Total sections: ${result.summary.totalSections}`);
  }
} else {
  console.error('✗ Invalid!');
  result.errors.forEach(error => {
    console.error(`${error.path}: ${error.message}`);
  });
}
```

### JavaScript (CommonJS)

```javascript
const { validateGamebook } = require('./validation');
const fs = require('fs');

const gamebook = JSON.parse(fs.readFileSync('gamebook.json', 'utf-8'));
const result = validateGamebook(gamebook);

if (result.valid) {
  console.log('✓ Valid!');
} else {
  console.error('✗ Invalid!');
  result.errors.forEach(error => {
    console.error(`${error.path}: ${error.message}`);
  });
}
```

---

## Integration Examples

### PDF Parser Integration

```typescript
import { validateGamebook } from './validation';

async function parsePDFToGamebook(pdfPath: string): Promise<GamebookJSON> {
  // ... parse PDF ...
  const gamebook = parsePDF(pdfPath);
  
  // Validate the parsed gamebook
  const validation = validateGamebook(gamebook);
  
  if (!validation.valid) {
    console.error('Parsed gamebook has validation errors:');
    validation.errors.forEach(error => {
      console.error(`  ${error.path}: ${error.message}`);
    });
  }
  
  return gamebook;
}
```

### Batch Validation

```typescript
import { validateGamebook } from './validation';
import { readdirSync, readFileSync } from 'fs';

const gamebooks = readdirSync('./gamebooks').filter(f => f.endsWith('.json'));

for (const file of gamebooks) {
  const gamebook = JSON.parse(readFileSync(`./gamebooks/${file}`, 'utf-8'));
  const result = validateGamebook(gamebook);
  
  console.log(`${file}: ${result.valid ? '✓' : '✗'} (${result.errors.length} errors)`);
}
```

### Editor/IDE Integration

```typescript
import { validateGamebook } from './validation';

function validateOnSave(content: string) {
  try {
    const gamebook = JSON.parse(content);
    const result = validateGamebook(gamebook);
    
    // Show errors/warnings in editor
    return result.errors.map(error => ({
      line: findLineNumber(error.path, content),
      message: error.message,
      severity: 'error'
    }));
  } catch (e) {
    return [{ line: 0, message: 'Invalid JSON', severity: 'error' }];
  }
}
```

---

## Error Handling

### Handling Specific Error Types

```typescript
function categorizeErrors(errors: ValidationError[]) {
  const categories = {
    schema: [] as ValidationError[],
    navigation: [] as ValidationError[],
    combat: [] as ValidationError[],
    other: [] as ValidationError[],
  };
  
  errors.forEach(error => {
    if (error.path.includes('navigationLinks') || error.path.includes('conditionalNavigation')) {
      categories.navigation.push(error);
    } else if (error.path.includes('combat')) {
      categories.combat.push(error);
    } else if (error.path.startsWith('/')) {
      categories.schema.push(error);
    } else {
      categories.other.push(error);
    }
  });
  
  return categories;
}

const result = validateGamebook(gamebook);
if (!result.valid) {
  const categorized = categorizeErrors(result.errors);
  console.error('Schema errors:', categorized.schema.length);
  console.error('Navigation errors:', categorized.navigation.length);
  console.error('Combat errors:', categorized.combat.length);
}
```

### Auto-fixing Common Issues

```typescript
function autoFixCommonIssues(gamebook: GamebookJSON): GamebookJSON {
  const result = validateGamebook(gamebook);
  
  // Fix section ID mismatches
  result.errors.forEach(error => {
    if (error.message.includes('does not match its key')) {
      const match = error.path.match(/\/sections\/([^/]+)\/id/);
      if (match) {
        const sectionKey = match[1];
        if (gamebook.sections[sectionKey]) {
          gamebook.sections[sectionKey].id = sectionKey;
        }
      }
    }
  });
  
  return gamebook;
}
```

---

## Validation Result Structure

```typescript
interface ValidationResult {
  valid: boolean;                    // true if no errors
  errors: ValidationError[];         // Array of validation errors
  warnings: ValidationWarning[];     // Array of warnings (non-fatal)
  summary?: ValidationSummary;       // Statistics about the gamebook
}

interface ValidationError {
  path: string;        // JSON path (e.g., "/sections/1/navigationLinks/0/targetSection")
  message: string;     // Human-readable error message
  expected?: string;   // Expected value
  received?: string;   // Received value
}

interface ValidationWarning {
  path: string;        // JSON path
  message: string;     // Human-readable warning message
}

interface ValidationSummary {
  totalSections: number;           // Total sections in gamebook
  gameplaySections: number;        // Number of gameplay sections
  reachableSections: number;        // Sections reachable from start
  unreachableSections: number;     // Unreachable gameplay sections
  totalErrors: number;              // Total validation errors
  totalWarnings: number;           // Total warnings
}
```

### Using Summary Statistics

```typescript
const result = validateGamebook(gamebook);

if (result.summary) {
  console.log('Validation Summary:');
  console.log(`  Total sections: ${result.summary.totalSections}`);
  console.log(`  Gameplay sections: ${result.summary.gameplaySections}`);
  console.log(`  Reachable sections: ${result.summary.reachableSections}`);
  console.log(`  Unreachable sections: ${result.summary.unreachableSections}`);
  console.log(`  Errors: ${result.summary.totalErrors}`);
  console.log(`  Warnings: ${result.summary.totalWarnings}`);
  
  // Calculate coverage
  const coverage = result.summary.reachableSections / result.summary.gameplaySections * 100;
  console.log(`  Reachability coverage: ${coverage.toFixed(1)}%`);
}
```

---

## What Gets Validated

The validator checks:

1. **JSON Schema Compliance**
   - Required fields present
   - Correct data types
   - Valid enum values
   - Schema structure

2. **Navigation Validation**
   - All navigation link targets exist
   - All conditional navigation targets exist
   - All combat encounter targets exist (win/lose/escape)
   - All Test Your Luck targets exist
   - All item check targets exist

3. **Data Integrity**
   - Section IDs match their keys
   - Start section exists in sections
   - Creature stats are valid
   - Item actions are valid
   - Stat modifications are valid

4. **Reachability Analysis**
   - All gameplay sections reachable from start (warnings only)
   - Unreachable sections identified

5. **Additional Properties**
   - Extra data is allowed (won't cause errors)
   - Useful for parser-specific metadata

---

## Troubleshooting

### "Cannot find module 'ajv'"

Install dependencies:
```bash
npm install ajv
```

### "JSON Schema file not found"

The validator looks for `gamebook-schema.json` in this order:
1. Same directory as `validation.js` (this folder) ✅ **Recommended for standalone**
2. `../../docs/gamebook-schema.json` (relative to engine/dist)
3. `../../../docs/gamebook-schema.json` (relative to docs/)

For standalone use, ensure `gamebook-schema.json` is in this folder.

### "Module not found" errors

Ensure all required files are in this folder:
- `validation.js`
- `types.js`
- `cli-validator.js` (for CLI)
- `gamebook-schema.json`

---

## For AI Assistants

**Quick Reference:**
- CLI: `node cli-validator.js <file> [--json]`
- Library: `const { validateGamebook } = require('./validation')`
- Result: `{ valid: boolean, errors: [], warnings: [], summary?: {...} }`
- Dependencies: Only `ajv` required
- Schema: Must be `gamebook-schema.json` in same folder as `validation.js`

**Common Patterns:**
```javascript
// Validate
const result = validateGamebook(gamebook);

// Check validity
if (!result.valid) { /* handle errors */ }

// Iterate errors
result.errors.forEach(e => console.error(e.message));

// Check warnings
if (result.warnings.length > 0) { /* show warnings */ }

// Use summary
console.log(`Sections: ${result.summary?.totalSections}`);
```

---

## Additional Notes

- **Additional Properties**: The validator allows extra data in JSON without throwing errors. You can include parser-specific metadata, debugging info, or other fields.

- **Standalone**: The validator can be used independently. It only depends on AJV and the JSON Schema file.

- **Performance**: Validation is fast enough for development workflows. For very large gamebooks (1000+ sections), consider caching the compiled schema.

- **Error Messages**: All error messages include JSON paths, making it easy to locate issues in your JSON files.

