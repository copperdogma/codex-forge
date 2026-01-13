#!/usr/bin/env node
"use strict";

// Test extractFunction - copy the function directly to avoid eval issues
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

// Test cases
function runTests() {
  let passed = 0;
  let failed = 0;
  const failures = [];

  function test(name, fn) {
    try {
      fn();
      passed++;
      console.log(`✓ ${name}`);
    } catch (error) {
      failed++;
      failures.push({ name, error: error.message });
      console.error(`✗ ${name}: ${error.message}`);
    }
  }

  // Test 1: Extract simple function
  test("Extract simple function", () => {
    const source = `
function testFunc() {
  return "hello";
}
function nextFunc() {
  return "world";
}
`;
    const result = extractFunction(source, "testFunc", "nextFunc");
    if (!result.includes('return "hello"')) {
      throw new Error("Function not extracted correctly");
    }
    if (result.includes('return "world"')) {
      throw new Error("Next function included in result");
    }
    if (!result.includes("function testFunc")) {
      throw new Error("Function signature not included");
    }
  });

  // Test 2: Extract function with nested braces
  test("Extract function with nested braces", () => {
    const source = `
function testFunc() {
  if (true) {
    return { value: "test" };
  }
}
function nextFunc() {}
`;
    const result = extractFunction(source, "testFunc", "nextFunc");
    if (!result.includes('return { value: "test" }')) {
      throw new Error("Nested braces not handled correctly");
    }
  });

  // Test 3: Extract function at end of file
  test("Extract function at end of file", () => {
    const source = `
function testFunc() {
  return "end";
}
`;
    const result = extractFunction(source, "testFunc", null);
    if (!result.includes('return "end"')) {
      throw new Error("End-of-file function not extracted");
    }
  });

  // Test 4: Error on missing function
  test("Error on missing function", () => {
    const source = `function otherFunc() {}`;
    try {
      extractFunction(source, "missingFunc", null);
      throw new Error("Should have thrown error for missing function");
    } catch (error) {
      if (!error.message.includes("Could not find function")) {
        throw new Error(`Wrong error message: ${error.message}`);
      }
    }
  });

  // Test 5: Extract function with complex nested structures
  test("Extract function with complex nesting", () => {
    const source = `
function testFunc() {
  const obj = {
    nested: {
      deep: {
        value: 42
      }
    }
  };
  if (true) {
    return obj;
  }
}
function nextFunc() {}
`;
    const result = extractFunction(source, "testFunc", "nextFunc");
    if (!result.includes("value: 42")) {
      throw new Error("Complex nesting not handled");
    }
  });

  // Test 6: Extract function with multiple nested levels
  test("Extract function with multiple nested levels", () => {
    const source = `
function testFunc() {
  for (let i = 0; i < 10; i++) {
    if (i > 5) {
      while (true) {
        break;
      }
    }
  }
}
function nextFunc() {}
`;
    const result = extractFunction(source, "testFunc", "nextFunc");
    if (!result.includes("for (let i = 0")) {
      throw new Error("Multiple nesting levels not handled");
    }
  });

  // Test 7: Extract function with string literals containing braces
  test("Extract function with string literals containing braces", () => {
    const source = `
function testFunc() {
  const str = "This has { braces } in string";
  return str;
}
function nextFunc() {}
`;
    const result = extractFunction(source, "testFunc", "nextFunc");
    if (!result.includes('"This has { braces } in string"')) {
      throw new Error("String literals with braces not handled");
    }
  });

  // Test 8: Extract function with comments containing function keywords
  test("Extract function with comments", () => {
    const source = `
function testFunc() {
  // This is a comment about function nextFunc()
  return "test";
}
function nextFunc() {}
`;
    const result = extractFunction(source, "testFunc", "nextFunc");
    if (!result.includes('return "test"')) {
      throw new Error("Comments not handled correctly");
    }
  });

  // Summary
  console.log("\n" + "=".repeat(70));
  console.log(`Tests: ${passed} passed, ${failed} failed`);
  if (failures.length > 0) {
    console.log("\nFailures:");
    failures.forEach((f) => console.log(`  - ${f.name}: ${f.error}`));
    process.exit(1);
  } else {
    console.log("All tests passed!");
    process.exit(0);
  }
}

// Run tests
runTests();
