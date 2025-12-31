# Fighting Fantasy Gamebook Validator

**Standalone validation tool for Fighting Fantasy gamebook JSON files**

## Quick Start

### Prerequisites
- Node.js >= 18.0.0
- npm >= 9.0.0

### Installation

```bash
# Install the only required dependency
npm install ajv
```

### Usage

**CLI:**
```bash
node cli-validator.js <gamebook.json>
node cli-validator.js <gamebook.json> --json  # JSON output
```

**Portable bundle (single file, no deps):**
```bash
node gamebook-validator.bundle.js <gamebook.json>
node gamebook-validator.bundle.js <gamebook.json> --json
```

**Library:**
```javascript
const { validateGamebook } = require('./validation');
const result = validateGamebook(gamebookData);
```

## What's Included

This folder contains everything needed for validation:

- `cli-validator.js` - Command-line tool
- `validation.js` - Core validation logic
- `types.js` - Type definitions
- `gamebook-schema.json` - JSON Schema
- `gamebook-validator.bundle.js` - Single-file portable validator (schema embedded)
- `*.d.ts` - TypeScript definitions (optional)

**Total size:** core validator is small; the portable bundle includes embedded schema and compiled validation logic.

## Portable Bundle

`gamebook-validator.bundle.js` is a single-file validator with the schema embedded. It has no npm/runtime dependencies and can be copied next to `gamebook.json` in the game engine.

To regenerate the bundle:
```bash
node build_bundle.js
```

## What It Validates

✅ JSON Schema compliance (types, required fields, enums)  
✅ Sequence targets exist (all targets point to real sections)  
✅ Section IDs match keys  
✅ Missing/duplicate section detection  
✅ Empty text + no-choice warnings  
✅ Start section exists  
✅ Reachability (warns about unreachable sections)  
✅ Allows extra data (won't error on additional properties)

Missing section checks use `gamebook.provenance.expected_range` when available (defaults to `1-400`).

## Expected Section Payload

Each section must include **`presentation_html`** (cleaned HTML for display). The validator does **not** require the older `text` field and treats any additional fields as optional extras.
Gameplay sections must include an ordered **`sequence`** array. Outcomes may omit `targetSection` when terminal (e.g., death), using a `terminal` object.
Gamebooks should include `metadata.validatorVersion` so the validator can warn on version mismatch.

## Output Format

**Human-readable:**
```
✓ Gamebook is valid!

Summary:
  Total sections: 100
  Gameplay sections: 95
  Reachable sections: 90
  Unreachable sections: 5
```

**JSON (with --json flag):**
```json
{
  "valid": true,
  "errors": [],
  "warnings": [...],
  "summary": {
    "totalSections": 100,
    "gameplaySections": 95,
    "reachableSections": 90,
    "unreachableSections": 5,
    "totalErrors": 0,
    "totalWarnings": 5
  }
}
```

## Library Usage

```javascript
const { validateGamebook } = require('./validation');
const fs = require('fs');

const gamebook = JSON.parse(fs.readFileSync('gamebook.json', 'utf-8'));
const result = validateGamebook(gamebook);

if (result.valid) {
  console.log('✓ Valid!');
} else {
  console.error('✗ Invalid!');
  result.errors.forEach(e => {
    console.error(`  ${e.path}: ${e.message}`);
  });
}
```

## Validation Result Structure

```typescript
interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
  summary?: {
    totalSections: number;
    gameplaySections: number;
    reachableSections: number;
    unreachableSections: number;
    totalErrors: number;
    totalWarnings: number;
  };
}
```

## Common Commands

```bash
# Validate a file
node cli-validator.js gamebook.json

# Get JSON output
node cli-validator.js gamebook.json --json

# Check exit code (0 = valid, 1 = invalid)
node cli-validator.js gamebook.json && echo "Valid!" || echo "Invalid!"
```

## Troubleshooting

**"Cannot find module 'ajv'"**
→ Run: `npm install ajv`

**"JSON Schema file not found"**
→ Ensure `gamebook-schema.json` is in this folder

**"Cannot find module './validation'"**
→ Ensure you're running from the validator folder

## For More Details

See `USAGE.md` in this folder for comprehensive usage examples and integration patterns.
