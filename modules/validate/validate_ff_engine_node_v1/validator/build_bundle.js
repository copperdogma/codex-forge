#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const Ajv = require("ajv");
const standaloneCode = require("ajv/dist/standalone").default;

const validatorDir = __dirname;
const schemaPath = path.join(validatorDir, "gamebook-schema.json");
const validationPath = path.join(validatorDir, "validation.js");
const pkgPath = path.join(validatorDir, "package.json");
const outPath = path.join(validatorDir, "gamebook-validator.bundle.js");

if (!fs.existsSync(schemaPath)) {
  throw new Error(`Schema not found at ${schemaPath}`);
}
if (!fs.existsSync(validationPath)) {
  throw new Error(`Validation source not found at ${validationPath}`);
}

const schema = JSON.parse(fs.readFileSync(schemaPath, "utf-8"));
const validationSource = fs.readFileSync(validationPath, "utf-8");
const pkg = fs.existsSync(pkgPath) ? JSON.parse(fs.readFileSync(pkgPath, "utf-8")) : {};
const validatorVersion = pkg.name && pkg.version ? `${pkg.name}@${pkg.version}` : (pkg.version || "");

// Extract findReachableSections and findUnreachableSections from validation.js
// This ensures the bundle always uses the same logic as the source
function extractFunction(source, functionName, nextFunctionName) {
  // Find the start of the function
  const startPattern = new RegExp(`function\\s+${functionName}\\s*\\([^)]*\\)\\s*\\{`, "m");
  const startMatch = source.match(startPattern);
  if (!startMatch) {
    throw new Error(`Could not find function ${functionName} in validation.js`);
  }
  const startIndex = startMatch.index;
  
  // Find the end - either the next function or end of file
  let endIndex = source.length;
  if (nextFunctionName) {
    const nextPattern = new RegExp(`function\\s+${nextFunctionName}\\s*\\([^)]*\\)\\s*\\{`, "m");
    const nextMatch = source.substring(startIndex).match(nextPattern);
    if (nextMatch) {
      endIndex = startIndex + nextMatch.index;
    }
  }
  
  // Extract the function with proper brace matching
  let braceCount = 0;
  let inFunction = false;
  let functionEnd = startIndex;
  
  for (let i = startIndex; i < endIndex; i++) {
    if (source[i] === '{') {
      braceCount++;
      inFunction = true;
    } else if (source[i] === '}') {
      braceCount--;
      if (inFunction && braceCount === 0) {
        functionEnd = i + 1;
        break;
      }
    }
  }
  
  if (!inFunction || braceCount !== 0) {
    throw new Error(`Could not properly extract function ${functionName} from validation.js (unmatched braces)`);
  }
  
  return source.substring(startIndex, functionEnd);
}

const findReachableSectionsSource = extractFunction(validationSource, "findReachableSections", "findUnreachableSections");
const findUnreachableSectionsSource = extractFunction(validationSource, "findUnreachableSections", null);

const ajv = new Ajv({
  allErrors: true,
  strict: false,
  allowUnionTypes: true,
  code: { source: true, esm: false },
});
const validate = ajv.compile(schema);
let code = standaloneCode(ajv, validate);

const exportMatch = code.match(/module\.exports = (validate\d+);module\.exports\.default = \1;/);
if (!exportMatch) {
  throw new Error("Unable to locate standalone validator export");
}
const fnName = exportMatch[1];
code = code.replace(/module\.exports = .*?;module\.exports\.default = .*?;/, "");

const validateSchemaBlock = [
  "const validateSchema = (() => {",
  code,
  `return ${fnName};`,
  "})();",
].join("\n");

const bundle = `#!/usr/bin/env node
"use strict";
${validateSchemaBlock}

const VALIDATOR_VERSION = ${JSON.stringify(validatorVersion)};

function ajvErrorToValidationError(error) {
  const path = error.instancePath || error.schemaPath || '';
  let message = error.message || 'Validation error';
  if (error.keyword === 'required') {
    message = \`Missing required field: \${error.params.missingProperty}\`;
  } else if (error.keyword === 'type') {
    message = \`Expected \${error.params.type}, got \${typeof error.data}\`;
  } else if (error.keyword === 'enum') {
    message = \`Invalid value. Expected one of: \${error.params.allowedValues?.join(', ')}\`;
  }
  return {
    path,
    message,
    expected: error.params?.type || error.params?.allowedValues?.join(', '),
    received: String(error.data),
  };
}

function stripHtmlToText(html) {
  if (!html) return '';
  return html
    .replace(/<script[\\s\\S]*?<\\/script>/gi, ' ')
    .replace(/<style[\\s\\S]*?<\\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\\s+/g, ' ')
    .trim();
}

function parseExpectedRange(gamebook) {
  const metaCount = gamebook?.metadata?.sectionCount;
  if (Number.isFinite(metaCount) && metaCount > 0) {
    return { min: 1, max: Math.floor(metaCount) };
  }
  const fromProvenance = gamebook?.provenance?.expected_range || gamebook?.provenance?.expectedRange;
  const raw = typeof fromProvenance === 'string' && fromProvenance ? fromProvenance : '1-400';
  const match = raw.match(/^\\s*(\\d+)\\s*-\\s*(\\d+)\\s*$/);
  if (!match) return { min: 1, max: 400 };
  const min = Number(match[1]);
  const max = Number(match[2]);
  if (!Number.isFinite(min) || !Number.isFinite(max) || min <= 0 || max <= 0 || min > max) {
    return { min: 1, max: 400 };
  }
  return { min, max };
}

function validateWithSchema(gamebook) {
  const valid = validateSchema(gamebook);
  if (!valid && validateSchema.errors) {
    return validateSchema.errors.map(ajvErrorToValidationError);
  }
  return [];
}

function validateSectionIds(gamebook) {
  const errors = [];
  for (const [key, section] of Object.entries(gamebook.sections || {})) {
    if (section.id !== key) {
      errors.push({
        path: \`/sections/\${key}/id\`,
        message: \`Section ID "\${section.id}" does not match its key "\${key}"\`,
        expected: key,
        received: section.id,
      });
    }
  }
  return errors;
}

function validateMissingSections(gamebook) {
  const errors = [];
  const sectionIds = Object.keys(gamebook.sections || {});
  const numericIds = new Set(sectionIds.filter(id => /^\\d+$/.test(id)));
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
    let msg = \`Missing \${missing.length} sections in range \${min}-\${max}: \${sample.join(', ')}\`;
    if (missing.length > 10) {
      msg += \` (and \${missing.length - 10} more)\`;
    }
    errors.push({
      path: '/sections',
      message: msg,
      expected: \`all sections in range \${min}-\${max}\`,
      received: \`missing \${missing.length} sections\`,
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
    } else {
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
      message: \`Duplicate section IDs detected: \${duplicates
        .map(d => \`\${d.id} (keys: \${d.keys.join(', ')})\`)
        .join('; ')}\`,
      expected: 'unique section IDs',
      received: 'duplicates',
    });
  }
  return errors;
}

function validateSequenceTargets(gamebook) {
  const errors = [];
  const sectionIds = new Set(Object.keys(gamebook.sections || {}));
  for (const [sectionKey, section] of Object.entries(gamebook.sections || {})) {
    if (!section.isGameplaySection) continue;
    const sequence = section.sequence || [];
    sequence.forEach((event, index) => {
      const kind = event.kind;
      const checkOutcome = (outcome, pathSuffix) => {
        if (!outcome) return;
        if (outcome.targetSection) {
          if (!sectionIds.has(outcome.targetSection)) {
            errors.push({
              path: \`/sections/\${sectionKey}/sequence/\${index}/\${pathSuffix}/targetSection\`,
              message: \`Sequence target section "\${outcome.targetSection}" does not exist\`,
              expected: 'existing section ID',
              received: outcome.targetSection,
            });
          }
        } else if (!outcome.terminal) {
          errors.push({
            path: \`/sections/\${sectionKey}/sequence/\${index}/\${pathSuffix}\`,
            message: 'Outcome missing targetSection or terminal outcome',
            expected: 'targetSection or terminal',
            received: 'none',
          });
        }
      };
      if (kind === 'choice') {
        if (!event.targetSection) {
          errors.push({
            path: \`/sections/\${sectionKey}/sequence/\${index}/targetSection\`,
            message: 'Choice event missing targetSection',
            expected: 'targetSection',
            received: 'none',
          });
        } else if (!sectionIds.has(event.targetSection)) {
          errors.push({
            path: \`/sections/\${sectionKey}/sequence/\${index}/targetSection\`,
            message: \`Sequence target section "\${event.targetSection}" does not exist\`,
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
      if (kind === 'item_check') {
        checkOutcome(event.has, 'has');
        checkOutcome(event.missing, 'missing');
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
        path: \`/sections/\${key}/presentation_html\`,
        message: \`Section "\${key}" has no text\`,
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
    if (!section?.isGameplaySection) continue;
    if (section?.end_game) continue;
    if (section?.provenance?.stub) continue;
    const sequence = section?.sequence || [];
    if (!hasNavigation(sequence)) {
      warnings.push({
        path: \`/sections/\${key}/sequence\`,
        message: \`Gameplay section "\${key}" has no choices (potential dead end)\`,
      });
    }
  }
  return warnings;
}

${findReachableSectionsSource}

${findUnreachableSectionsSource}

function validateGamebook(gamebook) {
  const errors = [];
  const warnings = [];
  errors.push(...validateWithSchema(gamebook));
  const hasBasicStructure = gamebook.metadata && gamebook.sections;
  if (hasBasicStructure) {
    if (gamebook.metadata.startSection && !(gamebook.metadata.startSection in gamebook.sections)) {
      errors.push({
        path: '/metadata/startSection',
        message: \`startSection "\${gamebook.metadata.startSection}" does not exist in sections\`,
        expected: 'existing section ID',
        received: gamebook.metadata.startSection,
      });
    }
    errors.push(...validateSectionIds(gamebook));
    errors.push(...validateMissingSections(gamebook));
    errors.push(...validateDuplicateSections(gamebook));
    errors.push(...validateSequenceTargets(gamebook));
    warnings.push(...validateEmptyText(gamebook));
    warnings.push(...validateNoChoices(gamebook));
    if (gamebook.metadata.startSection && gamebook.sections[gamebook.metadata.startSection]) {
      warnings.push(...findUnreachableSections(gamebook));
    }
    if (VALIDATOR_VERSION) {
      const expectedVersion = gamebook.metadata.validatorVersion;
      if (!expectedVersion) {
        warnings.push({
          path: '/metadata/validatorVersion',
          message: 'metadata.validatorVersion missing; version mismatch checks disabled',
        });
      } else if (expectedVersion !== VALIDATOR_VERSION) {
        warnings.push({
          path: '/metadata/validatorVersion',
          message: \`Validator version mismatch (gamebook expects \${expectedVersion}, validator is \${VALIDATOR_VERSION})\`,
        });
      }
    }
  }

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
    validatorVersion: VALIDATOR_VERSION || undefined,
    versionMismatch: Boolean(VALIDATOR_VERSION && gamebook?.metadata?.validatorVersion && gamebook.metadata.validatorVersion !== VALIDATOR_VERSION),
  };
}

module.exports = {
  validateGamebook,
};
module.exports.default = validateGamebook;

if (require.main === module) {
  const fs = require('fs');
  const args = process.argv.slice(2);
  if (args.length === 0) {
    console.error('Usage: node gamebook-validator.bundle.js <gamebook.json> [--json]');
    process.exit(1);
  }
  const jsonOutput = args.includes('--json');
  const filePath = args.find(arg => arg !== '--json');
  if (!filePath) {
    console.error('Error: No gamebook file specified');
    process.exit(1);
  }
  if (!fs.existsSync(filePath)) {
    console.error(\`Error: File not found: \${filePath}\`);
    process.exit(1);
  }
  try {
    const fileContent = fs.readFileSync(filePath, 'utf-8');
    const gamebook = JSON.parse(fileContent);
    const result = validateGamebook(gamebook);
    if (jsonOutput) {
      console.log(JSON.stringify(result, null, 2));
      process.exit(result.valid ? 0 : 1);
      return;
    }
    if (result.valid) {
      console.log('✓ Gamebook is valid!');
      if (result.summary) {
        console.log('\\nSummary:');
        console.log(\`  Total sections: \${result.summary.totalSections}\`);
        console.log(\`  Gameplay sections: \${result.summary.gameplaySections}\`);
        console.log(\`  Reachable sections: \${result.summary.reachableSections}\`);
        if (result.summary.unreachableSections > 0) {
          console.log(\`  Unreachable sections: \${result.summary.unreachableSections}\`);
        }
      }
      if (result.warnings.length > 0) {
        console.log(\`\\n⚠ Found \${result.warnings.length} warning(s):\`);
        result.warnings.forEach(warning => {
          console.log(\`  \${warning.path}: \${warning.message}\`);
        });
      }
      process.exit(0);
    } else {
      console.error('✗ Gamebook validation failed!');
      console.error(\`\\nFound \${result.errors.length} error(s):\`);
      result.errors.forEach(error => {
        console.error(\`  \${error.path}: \${error.message}\`);
        if (error.expected && error.received) {
          console.error(\`    Expected: \${error.expected}\`);
          console.error(\`    Received: \${error.received}\`);
        }
      });
      if (result.summary) {
        console.error('\\nSummary:');
        console.error(\`  Total sections: \${result.summary.totalSections}\`);
        console.error(\`  Gameplay sections: \${result.summary.gameplaySections}\`);
        console.error(\`  Reachable sections: \${result.summary.reachableSections}\`);
        if (result.summary.unreachableSections > 0) {
          console.error(\`  Unreachable sections: \${result.summary.unreachableSections}\`);
        }
        console.error(\`  Errors: \${result.summary.totalErrors}\`);
        if (result.summary.totalWarnings > 0) {
          console.error(\`  Warnings: \${result.summary.totalWarnings}\`);
        }
      }
      if (result.warnings.length > 0) {
        console.error(\`\\n⚠ Found \${result.warnings.length} warning(s):\`);
        result.warnings.forEach(warning => {
          console.error(\`  \${warning.path}: \${warning.message}\`);
        });
      }
      process.exit(1);
    }
  } catch (error) {
    if (error instanceof SyntaxError) {
      console.error(\`Error: Invalid JSON in \${filePath}\`);
      console.error(error.message);
      process.exit(1);
    } else {
      console.error(\`Error: \${error instanceof Error ? error.message : String(error)}\`);
      process.exit(1);
    }
  }
}
`;

fs.writeFileSync(outPath, bundle, "utf-8");
fs.chmodSync(outPath, 0o755);
console.log(`Wrote bundle -> ${outPath}`);
