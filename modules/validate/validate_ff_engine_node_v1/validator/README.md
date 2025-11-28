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
- `*.d.ts` - TypeScript definitions (optional)

**Total size: ~32KB**

## What It Validates

✅ JSON Schema compliance (types, required fields, enums)  
✅ Navigation targets exist (all links point to real sections)  
✅ Combat targets exist (win/lose/escape sections)  
✅ Test Your Luck targets exist  
✅ Item check targets exist  
✅ Section IDs match keys  
✅ Start section exists  
✅ Reachability (warns about unreachable sections)  
✅ Allows extra data (won't error on additional properties)

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

