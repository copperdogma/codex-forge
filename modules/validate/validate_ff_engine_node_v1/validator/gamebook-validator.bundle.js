#!/usr/bin/env node
"use strict";
const validateSchema = (() => {
"use strict";const schema11 = {"$schema":"http://json-schema.org/draft-07/schema#","$id":"https://fighting-fantasy-engine.github.io/schema/gamebook.json","title":"Fighting Fantasy Gamebook JSON Schema","description":"Schema specification for Fighting Fantasy gamebook JSON format. This is the required format that the PDF-to-JSON parser must produce.","type":"object","required":["metadata","sections"],"additionalProperties":true,"properties":{"metadata":{"type":"object","required":["title","startSection","formatVersion"],"additionalProperties":true,"properties":{"title":{"type":"string","description":"Book title"},"author":{"type":"string","description":"Book author (optional)"},"startSection":{"type":"string","description":"Starting section ID (usually '1')"},"formatVersion":{"type":"string","description":"Format version (e.g., '1.0.0')"},"validatorVersion":{"type":"string","description":"Validator version expected to validate this gamebook"}}},"sections":{"type":"object","description":"All sections in the gamebook, keyed by section ID","patternProperties":{"^.+$":{"$ref":"#/definitions/GamebookSection"}}}},"definitions":{"SectionId":{"type":"string","description":"Unique section identifier (e.g., '1', '270', 'S003')"},"GamebookSection":{"type":"object","required":["id","presentation_html","isGameplaySection","type"],"additionalProperties":true,"properties":{"id":{"$ref":"#/definitions/SectionId"},"presentation_html":{"type":"string","description":"Cleaned HTML content for display (final narrative payload)"},"pageStart":{"type":"number","description":"Starting page number (optional, for citation)"},"pageEnd":{"type":"number","description":"Ending page number (optional, for citation)"},"isGameplaySection":{"type":"boolean","description":"true = gameplay section (has sequence), false = non-gameplay content (cover, rules, etc.)"},"type":{"type":"string","enum":["section","front_cover","back_cover","title_page","publishing_info","toc","intro","rules","adventure_sheet","template","background"],"description":"Section type categorizing the content"},"status":{"type":"string","enum":["death","victory","defeat"],"description":"Optional ending status for the section"},"end_game":{"type":"boolean","description":"Optional end-game marker (suppresses no-choice warnings)"},"sequence":{"type":"array","description":"Ordered gameplay sequence events for this section","items":{"$ref":"#/definitions/SequenceEvent"}},"metadata":{"type":"object","description":"Additional section metadata","properties":{"title":{"type":"string","description":"Section title if available"}}}},"allOf":[{"if":{"properties":{"isGameplaySection":{"const":true}}},"then":{"required":["sequence"]}},{"not":{"required":["navigation"]}},{"not":{"required":["combat"]}},{"not":{"required":["items"]}},{"not":{"required":["statModifications"]}},{"not":{"required":["statChanges"]}},{"not":{"required":["diceChecks"]}},{"not":{"required":["deathConditions"]}}]},"SequenceEvent":{"oneOf":[{"$ref":"#/definitions/ChoiceEvent"},{"$ref":"#/definitions/StatChangeEvent"},{"$ref":"#/definitions/StatCheckEvent"},{"$ref":"#/definitions/TestLuckEvent"},{"$ref":"#/definitions/ItemEvent"},{"$ref":"#/definitions/ItemCheckEvent"},{"$ref":"#/definitions/StateCheckEvent"},{"$ref":"#/definitions/ConditionalEvent"},{"$ref":"#/definitions/CombatEvent"},{"$ref":"#/definitions/DeathEvent"},{"$ref":"#/definitions/CustomEvent"}]},"Condition":{"oneOf":[{"$ref":"#/definitions/ItemCondition"}]},"ItemCondition":{"type":"object","required":["kind","itemName"],"properties":{"kind":{"const":"item"},"itemName":{"type":"string"},"operator":{"type":"string","enum":["has","missing"]}}},"ConditionalEvent":{"type":"object","required":["kind","condition","then"],"properties":{"kind":{"const":"conditional"},"condition":{"$ref":"#/definitions/Condition"},"then":{"type":"array","items":{"$ref":"#/definitions/SequenceEvent"}},"else":{"type":"array","items":{"$ref":"#/definitions/SequenceEvent"}}}},"OutcomeRef":{"type":"object","properties":{"targetSection":{"$ref":"#/definitions/SectionId"},"terminal":{"$ref":"#/definitions/TerminalOutcome"}},"oneOf":[{"required":["targetSection"]},{"required":["terminal"]}]},"ChoiceEvent":{"type":"object","required":["kind","targetSection"],"properties":{"kind":{"const":"choice"},"targetSection":{"$ref":"#/definitions/SectionId"},"choiceText":{"type":"string"},"effects":{"type":"array","items":{"$ref":"#/definitions/ItemEvent"}}}},"StatChangeEvent":{"type":"object","required":["kind","stat","amount"],"properties":{"kind":{"const":"stat_change"},"stat":{"oneOf":[{"type":"string"},{"type":"array","items":{"type":"string"}}]},"amount":{"type":["number","string"]},"permanent":{"type":"boolean"}}},"StatCheckEvent":{"type":"object","required":["kind","stat"],"properties":{"kind":{"const":"stat_check"},"stat":{"oneOf":[{"type":"string"},{"type":"array","items":{"type":"string"}}]},"diceRoll":{"type":"string"},"passCondition":{"type":"string"},"failCondition":{"type":"string"},"pass":{"$ref":"#/definitions/OutcomeRef"},"fail":{"$ref":"#/definitions/OutcomeRef"}}},"TestLuckEvent":{"type":"object","required":["kind"],"properties":{"kind":{"const":"test_luck"},"lucky":{"$ref":"#/definitions/OutcomeRef"},"unlucky":{"$ref":"#/definitions/OutcomeRef"}}},"ItemEvent":{"type":"object","required":["kind","action","name"],"properties":{"kind":{"const":"item"},"action":{"type":"string","enum":["add","remove","reference"]},"name":{"type":"string"}}},"ItemCheckEvent":{"type":"object","required":["kind"],"properties":{"kind":{"const":"item_check"},"itemName":{"type":"string"},"has":{"$ref":"#/definitions/OutcomeRef"},"missing":{"$ref":"#/definitions/OutcomeRef"},"itemsAll":{"type":"array","items":{"type":"string"},"minItems":2}}},"CombatEvent":{"type":"object","required":["kind","enemies"],"properties":{"kind":{"const":"combat"},"enemies":{"type":"array","items":{"$ref":"#/definitions/CombatEncounter"}},"outcomes":{"type":"object","properties":{"win":{"$ref":"#/definitions/OutcomeRef"},"lose":{"$ref":"#/definitions/OutcomeRef"},"escape":{"$ref":"#/definitions/OutcomeRef"}},"additionalProperties":false}}},"DeathEvent":{"type":"object","required":["kind","outcome"],"properties":{"kind":{"const":"death"},"outcome":{"$ref":"#/definitions/OutcomeRef"},"description":{"type":"string"}}},"CustomEvent":{"type":"object","required":["kind"],"properties":{"kind":{"const":"custom"},"data":{"type":"object","additionalProperties":true}},"additionalProperties":true},"TerminalOutcome":{"type":"object","required":["kind"],"properties":{"kind":{"type":"string","enum":["death","victory","defeat","end"],"description":"Terminal outcome type"},"message":{"type":"string","description":"Optional narrative message"}}},"CombatEncounter":{"type":"object","required":["enemy","skill","stamina"],"properties":{"enemy":{"type":"string","description":"Creature name"},"skill":{"type":"number","description":"Combat Skill value"},"stamina":{"type":"number","description":"Stamina (hit points)"},"special_rules":{"type":"string","description":"Optional special combat rules"},"allow_escape":{"type":"boolean","description":"Whether escape is allowed from this combat"}}},"CreatureStats":{"type":"object","required":["name","skill","stamina"],"properties":{"name":{"type":"string","description":"Creature name"},"skill":{"type":"number","description":"Combat Skill value"},"stamina":{"type":"number","description":"Stamina (hit points)"},"specialRules":{"type":"array","description":"Optional special combat rules","items":{"type":"string"}},"allowEscape":{"type":"boolean","description":"Whether escape is allowed from this combat"},"escapeSection":{"$ref":"#/definitions/SectionId","description":"Section to navigate to if player escapes"}}},"ItemReference":{"type":"object","required":["name","action"],"properties":{"name":{"type":"string","description":"Item name (as it appears in text)"},"action":{"type":"string","enum":["add","remove","check","reference"],"description":"Item action: add to inventory, remove from inventory, check if player has, or just reference"}}},"StatModification":{"type":"object","required":["stat","amount"],"properties":{"stat":{"type":"string","enum":["skill","stamina","luck"],"description":"Stat name: 'skill', 'stamina', or 'luck'"},"amount":{"type":"number","description":"Amount to change (can be negative)"},"permanent":{"type":"boolean","description":"Whether this is a permanent modification (affects initial value)","default":false}}},"DeathCondition":{"type":"object","required":["trigger"],"properties":{"trigger":{"type":"string","enum":["stamina_zero","instant_death","conditional"],"description":"Death trigger type"},"message":{"type":"string","description":"Death message/reason"}}},"StateCheckEvent":{"type":"object","required":["kind"],"properties":{"kind":{"const":"state_check"},"conditionText":{"type":"string"},"has":{"$ref":"#/definitions/OutcomeRef"},"missing":{"$ref":"#/definitions/OutcomeRef"}}}}};const pattern0 = new RegExp("^.+$", "u");const schema12 = {"type":"object","required":["id","presentation_html","isGameplaySection","type"],"additionalProperties":true,"properties":{"id":{"$ref":"#/definitions/SectionId"},"presentation_html":{"type":"string","description":"Cleaned HTML content for display (final narrative payload)"},"pageStart":{"type":"number","description":"Starting page number (optional, for citation)"},"pageEnd":{"type":"number","description":"Ending page number (optional, for citation)"},"isGameplaySection":{"type":"boolean","description":"true = gameplay section (has sequence), false = non-gameplay content (cover, rules, etc.)"},"type":{"type":"string","enum":["section","front_cover","back_cover","title_page","publishing_info","toc","intro","rules","adventure_sheet","template","background"],"description":"Section type categorizing the content"},"status":{"type":"string","enum":["death","victory","defeat"],"description":"Optional ending status for the section"},"end_game":{"type":"boolean","description":"Optional end-game marker (suppresses no-choice warnings)"},"sequence":{"type":"array","description":"Ordered gameplay sequence events for this section","items":{"$ref":"#/definitions/SequenceEvent"}},"metadata":{"type":"object","description":"Additional section metadata","properties":{"title":{"type":"string","description":"Section title if available"}}}},"allOf":[{"if":{"properties":{"isGameplaySection":{"const":true}}},"then":{"required":["sequence"]}},{"not":{"required":["navigation"]}},{"not":{"required":["combat"]}},{"not":{"required":["items"]}},{"not":{"required":["statModifications"]}},{"not":{"required":["statChanges"]}},{"not":{"required":["diceChecks"]}},{"not":{"required":["deathConditions"]}}]};const schema13 = {"type":"string","description":"Unique section identifier (e.g., '1', '270', 'S003')"};const schema14 = {"oneOf":[{"$ref":"#/definitions/ChoiceEvent"},{"$ref":"#/definitions/StatChangeEvent"},{"$ref":"#/definitions/StatCheckEvent"},{"$ref":"#/definitions/TestLuckEvent"},{"$ref":"#/definitions/ItemEvent"},{"$ref":"#/definitions/ItemCheckEvent"},{"$ref":"#/definitions/StateCheckEvent"},{"$ref":"#/definitions/ConditionalEvent"},{"$ref":"#/definitions/CombatEvent"},{"$ref":"#/definitions/DeathEvent"},{"$ref":"#/definitions/CustomEvent"}]};const schema18 = {"type":"object","required":["kind","stat","amount"],"properties":{"kind":{"const":"stat_change"},"stat":{"oneOf":[{"type":"string"},{"type":"array","items":{"type":"string"}}]},"amount":{"type":["number","string"]},"permanent":{"type":"boolean"}}};const schema17 = {"type":"object","required":["kind","action","name"],"properties":{"kind":{"const":"item"},"action":{"type":"string","enum":["add","remove","reference"]},"name":{"type":"string"}}};const schema33 = {"type":"object","required":["kind"],"properties":{"kind":{"const":"custom"},"data":{"type":"object","additionalProperties":true}},"additionalProperties":true};const schema15 = {"type":"object","required":["kind","targetSection"],"properties":{"kind":{"const":"choice"},"targetSection":{"$ref":"#/definitions/SectionId"},"choiceText":{"type":"string"},"effects":{"type":"array","items":{"$ref":"#/definitions/ItemEvent"}}}};function validate13(data, {instancePath="", parentData, parentDataProperty, rootData=data}={}){let vErrors = null;let errors = 0;if(data && typeof data == "object" && !Array.isArray(data)){if(data.kind === undefined){const err0 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "kind"},message:"must have required property '"+"kind"+"'"};if(vErrors === null){vErrors = [err0];}else {vErrors.push(err0);}errors++;}if(data.targetSection === undefined){const err1 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "targetSection"},message:"must have required property '"+"targetSection"+"'"};if(vErrors === null){vErrors = [err1];}else {vErrors.push(err1);}errors++;}if(data.kind !== undefined){if("choice" !== data.kind){const err2 = {instancePath:instancePath+"/kind",schemaPath:"#/properties/kind/const",keyword:"const",params:{allowedValue: "choice"},message:"must be equal to constant"};if(vErrors === null){vErrors = [err2];}else {vErrors.push(err2);}errors++;}}if(data.targetSection !== undefined){if(typeof data.targetSection !== "string"){const err3 = {instancePath:instancePath+"/targetSection",schemaPath:"#/definitions/SectionId/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err3];}else {vErrors.push(err3);}errors++;}}if(data.choiceText !== undefined){if(typeof data.choiceText !== "string"){const err4 = {instancePath:instancePath+"/choiceText",schemaPath:"#/properties/choiceText/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err4];}else {vErrors.push(err4);}errors++;}}if(data.effects !== undefined){let data3 = data.effects;if(Array.isArray(data3)){const len0 = data3.length;for(let i0=0; i0<len0; i0++){let data4 = data3[i0];if(data4 && typeof data4 == "object" && !Array.isArray(data4)){if(data4.kind === undefined){const err5 = {instancePath:instancePath+"/effects/" + i0,schemaPath:"#/definitions/ItemEvent/required",keyword:"required",params:{missingProperty: "kind"},message:"must have required property '"+"kind"+"'"};if(vErrors === null){vErrors = [err5];}else {vErrors.push(err5);}errors++;}if(data4.action === undefined){const err6 = {instancePath:instancePath+"/effects/" + i0,schemaPath:"#/definitions/ItemEvent/required",keyword:"required",params:{missingProperty: "action"},message:"must have required property '"+"action"+"'"};if(vErrors === null){vErrors = [err6];}else {vErrors.push(err6);}errors++;}if(data4.name === undefined){const err7 = {instancePath:instancePath+"/effects/" + i0,schemaPath:"#/definitions/ItemEvent/required",keyword:"required",params:{missingProperty: "name"},message:"must have required property '"+"name"+"'"};if(vErrors === null){vErrors = [err7];}else {vErrors.push(err7);}errors++;}if(data4.kind !== undefined){if("item" !== data4.kind){const err8 = {instancePath:instancePath+"/effects/" + i0+"/kind",schemaPath:"#/definitions/ItemEvent/properties/kind/const",keyword:"const",params:{allowedValue: "item"},message:"must be equal to constant"};if(vErrors === null){vErrors = [err8];}else {vErrors.push(err8);}errors++;}}if(data4.action !== undefined){let data6 = data4.action;if(typeof data6 !== "string"){const err9 = {instancePath:instancePath+"/effects/" + i0+"/action",schemaPath:"#/definitions/ItemEvent/properties/action/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err9];}else {vErrors.push(err9);}errors++;}if(!(((data6 === "add") || (data6 === "remove")) || (data6 === "reference"))){const err10 = {instancePath:instancePath+"/effects/" + i0+"/action",schemaPath:"#/definitions/ItemEvent/properties/action/enum",keyword:"enum",params:{allowedValues: schema17.properties.action.enum},message:"must be equal to one of the allowed values"};if(vErrors === null){vErrors = [err10];}else {vErrors.push(err10);}errors++;}}if(data4.name !== undefined){if(typeof data4.name !== "string"){const err11 = {instancePath:instancePath+"/effects/" + i0+"/name",schemaPath:"#/definitions/ItemEvent/properties/name/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err11];}else {vErrors.push(err11);}errors++;}}}else {const err12 = {instancePath:instancePath+"/effects/" + i0,schemaPath:"#/definitions/ItemEvent/type",keyword:"type",params:{type: "object"},message:"must be object"};if(vErrors === null){vErrors = [err12];}else {vErrors.push(err12);}errors++;}}}else {const err13 = {instancePath:instancePath+"/effects",schemaPath:"#/properties/effects/type",keyword:"type",params:{type: "array"},message:"must be array"};if(vErrors === null){vErrors = [err13];}else {vErrors.push(err13);}errors++;}}}else {const err14 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};if(vErrors === null){vErrors = [err14];}else {vErrors.push(err14);}errors++;}validate13.errors = vErrors;return errors === 0;}const schema19 = {"type":"object","required":["kind","stat"],"properties":{"kind":{"const":"stat_check"},"stat":{"oneOf":[{"type":"string"},{"type":"array","items":{"type":"string"}}]},"diceRoll":{"type":"string"},"passCondition":{"type":"string"},"failCondition":{"type":"string"},"pass":{"$ref":"#/definitions/OutcomeRef"},"fail":{"$ref":"#/definitions/OutcomeRef"}}};const schema20 = {"type":"object","properties":{"targetSection":{"$ref":"#/definitions/SectionId"},"terminal":{"$ref":"#/definitions/TerminalOutcome"}},"oneOf":[{"required":["targetSection"]},{"required":["terminal"]}]};const schema22 = {"type":"object","required":["kind"],"properties":{"kind":{"type":"string","enum":["death","victory","defeat","end"],"description":"Terminal outcome type"},"message":{"type":"string","description":"Optional narrative message"}}};function validate16(data, {instancePath="", parentData, parentDataProperty, rootData=data}={}){let vErrors = null;let errors = 0;const _errs1 = errors;let valid0 = false;let passing0 = null;const _errs2 = errors;if(data && typeof data == "object" && !Array.isArray(data)){if(data.targetSection === undefined){const err0 = {instancePath,schemaPath:"#/oneOf/0/required",keyword:"required",params:{missingProperty: "targetSection"},message:"must have required property '"+"targetSection"+"'"};if(vErrors === null){vErrors = [err0];}else {vErrors.push(err0);}errors++;}}var _valid0 = _errs2 === errors;if(_valid0){valid0 = true;passing0 = 0;}const _errs3 = errors;if(data && typeof data == "object" && !Array.isArray(data)){if(data.terminal === undefined){const err1 = {instancePath,schemaPath:"#/oneOf/1/required",keyword:"required",params:{missingProperty: "terminal"},message:"must have required property '"+"terminal"+"'"};if(vErrors === null){vErrors = [err1];}else {vErrors.push(err1);}errors++;}}var _valid0 = _errs3 === errors;if(_valid0 && valid0){valid0 = false;passing0 = [passing0, 1];}else {if(_valid0){valid0 = true;passing0 = 1;}}if(!valid0){const err2 = {instancePath,schemaPath:"#/oneOf",keyword:"oneOf",params:{passingSchemas: passing0},message:"must match exactly one schema in oneOf"};if(vErrors === null){vErrors = [err2];}else {vErrors.push(err2);}errors++;}else {errors = _errs1;if(vErrors !== null){if(_errs1){vErrors.length = _errs1;}else {vErrors = null;}}}if(data && typeof data == "object" && !Array.isArray(data)){if(data.targetSection !== undefined){if(typeof data.targetSection !== "string"){const err3 = {instancePath:instancePath+"/targetSection",schemaPath:"#/definitions/SectionId/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err3];}else {vErrors.push(err3);}errors++;}}if(data.terminal !== undefined){let data1 = data.terminal;if(data1 && typeof data1 == "object" && !Array.isArray(data1)){if(data1.kind === undefined){const err4 = {instancePath:instancePath+"/terminal",schemaPath:"#/definitions/TerminalOutcome/required",keyword:"required",params:{missingProperty: "kind"},message:"must have required property '"+"kind"+"'"};if(vErrors === null){vErrors = [err4];}else {vErrors.push(err4);}errors++;}if(data1.kind !== undefined){let data2 = data1.kind;if(typeof data2 !== "string"){const err5 = {instancePath:instancePath+"/terminal/kind",schemaPath:"#/definitions/TerminalOutcome/properties/kind/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err5];}else {vErrors.push(err5);}errors++;}if(!((((data2 === "death") || (data2 === "victory")) || (data2 === "defeat")) || (data2 === "end"))){const err6 = {instancePath:instancePath+"/terminal/kind",schemaPath:"#/definitions/TerminalOutcome/properties/kind/enum",keyword:"enum",params:{allowedValues: schema22.properties.kind.enum},message:"must be equal to one of the allowed values"};if(vErrors === null){vErrors = [err6];}else {vErrors.push(err6);}errors++;}}if(data1.message !== undefined){if(typeof data1.message !== "string"){const err7 = {instancePath:instancePath+"/terminal/message",schemaPath:"#/definitions/TerminalOutcome/properties/message/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err7];}else {vErrors.push(err7);}errors++;}}}else {const err8 = {instancePath:instancePath+"/terminal",schemaPath:"#/definitions/TerminalOutcome/type",keyword:"type",params:{type: "object"},message:"must be object"};if(vErrors === null){vErrors = [err8];}else {vErrors.push(err8);}errors++;}}}else {const err9 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};if(vErrors === null){vErrors = [err9];}else {vErrors.push(err9);}errors++;}validate16.errors = vErrors;return errors === 0;}function validate15(data, {instancePath="", parentData, parentDataProperty, rootData=data}={}){let vErrors = null;let errors = 0;if(data && typeof data == "object" && !Array.isArray(data)){if(data.kind === undefined){const err0 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "kind"},message:"must have required property '"+"kind"+"'"};if(vErrors === null){vErrors = [err0];}else {vErrors.push(err0);}errors++;}if(data.stat === undefined){const err1 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "stat"},message:"must have required property '"+"stat"+"'"};if(vErrors === null){vErrors = [err1];}else {vErrors.push(err1);}errors++;}if(data.kind !== undefined){if("stat_check" !== data.kind){const err2 = {instancePath:instancePath+"/kind",schemaPath:"#/properties/kind/const",keyword:"const",params:{allowedValue: "stat_check"},message:"must be equal to constant"};if(vErrors === null){vErrors = [err2];}else {vErrors.push(err2);}errors++;}}if(data.stat !== undefined){let data1 = data.stat;const _errs3 = errors;let valid1 = false;let passing0 = null;const _errs4 = errors;if(typeof data1 !== "string"){const err3 = {instancePath:instancePath+"/stat",schemaPath:"#/properties/stat/oneOf/0/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err3];}else {vErrors.push(err3);}errors++;}var _valid0 = _errs4 === errors;if(_valid0){valid1 = true;passing0 = 0;}const _errs6 = errors;if(Array.isArray(data1)){const len0 = data1.length;for(let i0=0; i0<len0; i0++){if(typeof data1[i0] !== "string"){const err4 = {instancePath:instancePath+"/stat/" + i0,schemaPath:"#/properties/stat/oneOf/1/items/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err4];}else {vErrors.push(err4);}errors++;}}}else {const err5 = {instancePath:instancePath+"/stat",schemaPath:"#/properties/stat/oneOf/1/type",keyword:"type",params:{type: "array"},message:"must be array"};if(vErrors === null){vErrors = [err5];}else {vErrors.push(err5);}errors++;}var _valid0 = _errs6 === errors;if(_valid0 && valid1){valid1 = false;passing0 = [passing0, 1];}else {if(_valid0){valid1 = true;passing0 = 1;}}if(!valid1){const err6 = {instancePath:instancePath+"/stat",schemaPath:"#/properties/stat/oneOf",keyword:"oneOf",params:{passingSchemas: passing0},message:"must match exactly one schema in oneOf"};if(vErrors === null){vErrors = [err6];}else {vErrors.push(err6);}errors++;}else {errors = _errs3;if(vErrors !== null){if(_errs3){vErrors.length = _errs3;}else {vErrors = null;}}}}if(data.diceRoll !== undefined){if(typeof data.diceRoll !== "string"){const err7 = {instancePath:instancePath+"/diceRoll",schemaPath:"#/properties/diceRoll/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err7];}else {vErrors.push(err7);}errors++;}}if(data.passCondition !== undefined){if(typeof data.passCondition !== "string"){const err8 = {instancePath:instancePath+"/passCondition",schemaPath:"#/properties/passCondition/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err8];}else {vErrors.push(err8);}errors++;}}if(data.failCondition !== undefined){if(typeof data.failCondition !== "string"){const err9 = {instancePath:instancePath+"/failCondition",schemaPath:"#/properties/failCondition/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err9];}else {vErrors.push(err9);}errors++;}}if(data.pass !== undefined){if(!(validate16(data.pass, {instancePath:instancePath+"/pass",parentData:data,parentDataProperty:"pass",rootData}))){vErrors = vErrors === null ? validate16.errors : vErrors.concat(validate16.errors);errors = vErrors.length;}}if(data.fail !== undefined){if(!(validate16(data.fail, {instancePath:instancePath+"/fail",parentData:data,parentDataProperty:"fail",rootData}))){vErrors = vErrors === null ? validate16.errors : vErrors.concat(validate16.errors);errors = vErrors.length;}}}else {const err10 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};if(vErrors === null){vErrors = [err10];}else {vErrors.push(err10);}errors++;}validate15.errors = vErrors;return errors === 0;}const schema23 = {"type":"object","required":["kind"],"properties":{"kind":{"const":"test_luck"},"lucky":{"$ref":"#/definitions/OutcomeRef"},"unlucky":{"$ref":"#/definitions/OutcomeRef"}}};function validate20(data, {instancePath="", parentData, parentDataProperty, rootData=data}={}){let vErrors = null;let errors = 0;if(data && typeof data == "object" && !Array.isArray(data)){if(data.kind === undefined){const err0 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "kind"},message:"must have required property '"+"kind"+"'"};if(vErrors === null){vErrors = [err0];}else {vErrors.push(err0);}errors++;}if(data.kind !== undefined){if("test_luck" !== data.kind){const err1 = {instancePath:instancePath+"/kind",schemaPath:"#/properties/kind/const",keyword:"const",params:{allowedValue: "test_luck"},message:"must be equal to constant"};if(vErrors === null){vErrors = [err1];}else {vErrors.push(err1);}errors++;}}if(data.lucky !== undefined){if(!(validate16(data.lucky, {instancePath:instancePath+"/lucky",parentData:data,parentDataProperty:"lucky",rootData}))){vErrors = vErrors === null ? validate16.errors : vErrors.concat(validate16.errors);errors = vErrors.length;}}if(data.unlucky !== undefined){if(!(validate16(data.unlucky, {instancePath:instancePath+"/unlucky",parentData:data,parentDataProperty:"unlucky",rootData}))){vErrors = vErrors === null ? validate16.errors : vErrors.concat(validate16.errors);errors = vErrors.length;}}}else {const err2 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};if(vErrors === null){vErrors = [err2];}else {vErrors.push(err2);}errors++;}validate20.errors = vErrors;return errors === 0;}const schema25 = {"type":"object","required":["kind"],"properties":{"kind":{"const":"item_check"},"itemName":{"type":"string"},"has":{"$ref":"#/definitions/OutcomeRef"},"missing":{"$ref":"#/definitions/OutcomeRef"},"itemsAll":{"type":"array","items":{"type":"string"},"minItems":2}}};function validate24(data, {instancePath="", parentData, parentDataProperty, rootData=data}={}){let vErrors = null;let errors = 0;if(data && typeof data == "object" && !Array.isArray(data)){if(data.kind === undefined){const err0 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "kind"},message:"must have required property '"+"kind"+"'"};if(vErrors === null){vErrors = [err0];}else {vErrors.push(err0);}errors++;}if(data.kind !== undefined){if("item_check" !== data.kind){const err1 = {instancePath:instancePath+"/kind",schemaPath:"#/properties/kind/const",keyword:"const",params:{allowedValue: "item_check"},message:"must be equal to constant"};if(vErrors === null){vErrors = [err1];}else {vErrors.push(err1);}errors++;}}if(data.itemName !== undefined){if(typeof data.itemName !== "string"){const err2 = {instancePath:instancePath+"/itemName",schemaPath:"#/properties/itemName/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err2];}else {vErrors.push(err2);}errors++;}}if(data.has !== undefined){if(!(validate16(data.has, {instancePath:instancePath+"/has",parentData:data,parentDataProperty:"has",rootData}))){vErrors = vErrors === null ? validate16.errors : vErrors.concat(validate16.errors);errors = vErrors.length;}}if(data.missing !== undefined){if(!(validate16(data.missing, {instancePath:instancePath+"/missing",parentData:data,parentDataProperty:"missing",rootData}))){vErrors = vErrors === null ? validate16.errors : vErrors.concat(validate16.errors);errors = vErrors.length;}}if(data.itemsAll !== undefined){let data4 = data.itemsAll;if(Array.isArray(data4)){if(data4.length < 2){const err3 = {instancePath:instancePath+"/itemsAll",schemaPath:"#/properties/itemsAll/minItems",keyword:"minItems",params:{limit: 2},message:"must NOT have fewer than 2 items"};if(vErrors === null){vErrors = [err3];}else {vErrors.push(err3);}errors++;}const len0 = data4.length;for(let i0=0; i0<len0; i0++){if(typeof data4[i0] !== "string"){const err4 = {instancePath:instancePath+"/itemsAll/" + i0,schemaPath:"#/properties/itemsAll/items/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err4];}else {vErrors.push(err4);}errors++;}}}else {const err5 = {instancePath:instancePath+"/itemsAll",schemaPath:"#/properties/itemsAll/type",keyword:"type",params:{type: "array"},message:"must be array"};if(vErrors === null){vErrors = [err5];}else {vErrors.push(err5);}errors++;}}}else {const err6 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};if(vErrors === null){vErrors = [err6];}else {vErrors.push(err6);}errors++;}validate24.errors = vErrors;return errors === 0;}const schema26 = {"type":"object","required":["kind"],"properties":{"kind":{"const":"state_check"},"conditionText":{"type":"string"},"has":{"$ref":"#/definitions/OutcomeRef"},"missing":{"$ref":"#/definitions/OutcomeRef"}}};function validate28(data, {instancePath="", parentData, parentDataProperty, rootData=data}={}){let vErrors = null;let errors = 0;if(data && typeof data == "object" && !Array.isArray(data)){if(data.kind === undefined){const err0 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "kind"},message:"must have required property '"+"kind"+"'"};if(vErrors === null){vErrors = [err0];}else {vErrors.push(err0);}errors++;}if(data.kind !== undefined){if("state_check" !== data.kind){const err1 = {instancePath:instancePath+"/kind",schemaPath:"#/properties/kind/const",keyword:"const",params:{allowedValue: "state_check"},message:"must be equal to constant"};if(vErrors === null){vErrors = [err1];}else {vErrors.push(err1);}errors++;}}if(data.conditionText !== undefined){if(typeof data.conditionText !== "string"){const err2 = {instancePath:instancePath+"/conditionText",schemaPath:"#/properties/conditionText/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err2];}else {vErrors.push(err2);}errors++;}}if(data.has !== undefined){if(!(validate16(data.has, {instancePath:instancePath+"/has",parentData:data,parentDataProperty:"has",rootData}))){vErrors = vErrors === null ? validate16.errors : vErrors.concat(validate16.errors);errors = vErrors.length;}}if(data.missing !== undefined){if(!(validate16(data.missing, {instancePath:instancePath+"/missing",parentData:data,parentDataProperty:"missing",rootData}))){vErrors = vErrors === null ? validate16.errors : vErrors.concat(validate16.errors);errors = vErrors.length;}}}else {const err3 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};if(vErrors === null){vErrors = [err3];}else {vErrors.push(err3);}errors++;}validate28.errors = vErrors;return errors === 0;}const schema27 = {"type":"object","required":["kind","condition","then"],"properties":{"kind":{"const":"conditional"},"condition":{"$ref":"#/definitions/Condition"},"then":{"type":"array","items":{"$ref":"#/definitions/SequenceEvent"}},"else":{"type":"array","items":{"$ref":"#/definitions/SequenceEvent"}}}};const schema28 = {"oneOf":[{"$ref":"#/definitions/ItemCondition"}]};const schema29 = {"type":"object","required":["kind","itemName"],"properties":{"kind":{"const":"item"},"itemName":{"type":"string"},"operator":{"type":"string","enum":["has","missing"]}}};function validate33(data, {instancePath="", parentData, parentDataProperty, rootData=data}={}){let vErrors = null;let errors = 0;const _errs0 = errors;let valid0 = false;let passing0 = null;const _errs1 = errors;if(data && typeof data == "object" && !Array.isArray(data)){if(data.kind === undefined){const err0 = {instancePath,schemaPath:"#/definitions/ItemCondition/required",keyword:"required",params:{missingProperty: "kind"},message:"must have required property '"+"kind"+"'"};if(vErrors === null){vErrors = [err0];}else {vErrors.push(err0);}errors++;}if(data.itemName === undefined){const err1 = {instancePath,schemaPath:"#/definitions/ItemCondition/required",keyword:"required",params:{missingProperty: "itemName"},message:"must have required property '"+"itemName"+"'"};if(vErrors === null){vErrors = [err1];}else {vErrors.push(err1);}errors++;}if(data.kind !== undefined){if("item" !== data.kind){const err2 = {instancePath:instancePath+"/kind",schemaPath:"#/definitions/ItemCondition/properties/kind/const",keyword:"const",params:{allowedValue: "item"},message:"must be equal to constant"};if(vErrors === null){vErrors = [err2];}else {vErrors.push(err2);}errors++;}}if(data.itemName !== undefined){if(typeof data.itemName !== "string"){const err3 = {instancePath:instancePath+"/itemName",schemaPath:"#/definitions/ItemCondition/properties/itemName/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err3];}else {vErrors.push(err3);}errors++;}}if(data.operator !== undefined){let data2 = data.operator;if(typeof data2 !== "string"){const err4 = {instancePath:instancePath+"/operator",schemaPath:"#/definitions/ItemCondition/properties/operator/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err4];}else {vErrors.push(err4);}errors++;}if(!((data2 === "has") || (data2 === "missing"))){const err5 = {instancePath:instancePath+"/operator",schemaPath:"#/definitions/ItemCondition/properties/operator/enum",keyword:"enum",params:{allowedValues: schema29.properties.operator.enum},message:"must be equal to one of the allowed values"};if(vErrors === null){vErrors = [err5];}else {vErrors.push(err5);}errors++;}}}else {const err6 = {instancePath,schemaPath:"#/definitions/ItemCondition/type",keyword:"type",params:{type: "object"},message:"must be object"};if(vErrors === null){vErrors = [err6];}else {vErrors.push(err6);}errors++;}var _valid0 = _errs1 === errors;if(_valid0){valid0 = true;passing0 = 0;}if(!valid0){const err7 = {instancePath,schemaPath:"#/oneOf",keyword:"oneOf",params:{passingSchemas: passing0},message:"must match exactly one schema in oneOf"};if(vErrors === null){vErrors = [err7];}else {vErrors.push(err7);}errors++;}else {errors = _errs0;if(vErrors !== null){if(_errs0){vErrors.length = _errs0;}else {vErrors = null;}}}validate33.errors = vErrors;return errors === 0;}const wrapper0 = {validate: validate12};function validate32(data, {instancePath="", parentData, parentDataProperty, rootData=data}={}){let vErrors = null;let errors = 0;if(data && typeof data == "object" && !Array.isArray(data)){if(data.kind === undefined){const err0 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "kind"},message:"must have required property '"+"kind"+"'"};if(vErrors === null){vErrors = [err0];}else {vErrors.push(err0);}errors++;}if(data.condition === undefined){const err1 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "condition"},message:"must have required property '"+"condition"+"'"};if(vErrors === null){vErrors = [err1];}else {vErrors.push(err1);}errors++;}if(data.then === undefined){const err2 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "then"},message:"must have required property '"+"then"+"'"};if(vErrors === null){vErrors = [err2];}else {vErrors.push(err2);}errors++;}if(data.kind !== undefined){if("conditional" !== data.kind){const err3 = {instancePath:instancePath+"/kind",schemaPath:"#/properties/kind/const",keyword:"const",params:{allowedValue: "conditional"},message:"must be equal to constant"};if(vErrors === null){vErrors = [err3];}else {vErrors.push(err3);}errors++;}}if(data.condition !== undefined){if(!(validate33(data.condition, {instancePath:instancePath+"/condition",parentData:data,parentDataProperty:"condition",rootData}))){vErrors = vErrors === null ? validate33.errors : vErrors.concat(validate33.errors);errors = vErrors.length;}}if(data.then !== undefined){let data2 = data.then;if(Array.isArray(data2)){const len0 = data2.length;for(let i0=0; i0<len0; i0++){if(!(wrapper0.validate(data2[i0], {instancePath:instancePath+"/then/" + i0,parentData:data2,parentDataProperty:i0,rootData}))){vErrors = vErrors === null ? wrapper0.validate.errors : vErrors.concat(wrapper0.validate.errors);errors = vErrors.length;}}}else {const err4 = {instancePath:instancePath+"/then",schemaPath:"#/properties/then/type",keyword:"type",params:{type: "array"},message:"must be array"};if(vErrors === null){vErrors = [err4];}else {vErrors.push(err4);}errors++;}}if(data.else !== undefined){let data4 = data.else;if(Array.isArray(data4)){const len1 = data4.length;for(let i1=0; i1<len1; i1++){if(!(wrapper0.validate(data4[i1], {instancePath:instancePath+"/else/" + i1,parentData:data4,parentDataProperty:i1,rootData}))){vErrors = vErrors === null ? wrapper0.validate.errors : vErrors.concat(wrapper0.validate.errors);errors = vErrors.length;}}}else {const err5 = {instancePath:instancePath+"/else",schemaPath:"#/properties/else/type",keyword:"type",params:{type: "array"},message:"must be array"};if(vErrors === null){vErrors = [err5];}else {vErrors.push(err5);}errors++;}}}else {const err6 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};if(vErrors === null){vErrors = [err6];}else {vErrors.push(err6);}errors++;}validate32.errors = vErrors;return errors === 0;}const schema30 = {"type":"object","required":["kind","enemies"],"properties":{"kind":{"const":"combat"},"enemies":{"type":"array","items":{"$ref":"#/definitions/CombatEncounter"}},"outcomes":{"type":"object","properties":{"win":{"$ref":"#/definitions/OutcomeRef"},"lose":{"$ref":"#/definitions/OutcomeRef"},"escape":{"$ref":"#/definitions/OutcomeRef"}},"additionalProperties":false}}};const schema31 = {"type":"object","required":["enemy","skill","stamina"],"properties":{"enemy":{"type":"string","description":"Creature name"},"skill":{"type":"number","description":"Combat Skill value"},"stamina":{"type":"number","description":"Stamina (hit points)"},"special_rules":{"type":"string","description":"Optional special combat rules"},"allow_escape":{"type":"boolean","description":"Whether escape is allowed from this combat"}}};function validate36(data, {instancePath="", parentData, parentDataProperty, rootData=data}={}){let vErrors = null;let errors = 0;if(data && typeof data == "object" && !Array.isArray(data)){if(data.kind === undefined){const err0 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "kind"},message:"must have required property '"+"kind"+"'"};if(vErrors === null){vErrors = [err0];}else {vErrors.push(err0);}errors++;}if(data.enemies === undefined){const err1 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "enemies"},message:"must have required property '"+"enemies"+"'"};if(vErrors === null){vErrors = [err1];}else {vErrors.push(err1);}errors++;}if(data.kind !== undefined){if("combat" !== data.kind){const err2 = {instancePath:instancePath+"/kind",schemaPath:"#/properties/kind/const",keyword:"const",params:{allowedValue: "combat"},message:"must be equal to constant"};if(vErrors === null){vErrors = [err2];}else {vErrors.push(err2);}errors++;}}if(data.enemies !== undefined){let data1 = data.enemies;if(Array.isArray(data1)){const len0 = data1.length;for(let i0=0; i0<len0; i0++){let data2 = data1[i0];if(data2 && typeof data2 == "object" && !Array.isArray(data2)){if(data2.enemy === undefined){const err3 = {instancePath:instancePath+"/enemies/" + i0,schemaPath:"#/definitions/CombatEncounter/required",keyword:"required",params:{missingProperty: "enemy"},message:"must have required property '"+"enemy"+"'"};if(vErrors === null){vErrors = [err3];}else {vErrors.push(err3);}errors++;}if(data2.skill === undefined){const err4 = {instancePath:instancePath+"/enemies/" + i0,schemaPath:"#/definitions/CombatEncounter/required",keyword:"required",params:{missingProperty: "skill"},message:"must have required property '"+"skill"+"'"};if(vErrors === null){vErrors = [err4];}else {vErrors.push(err4);}errors++;}if(data2.stamina === undefined){const err5 = {instancePath:instancePath+"/enemies/" + i0,schemaPath:"#/definitions/CombatEncounter/required",keyword:"required",params:{missingProperty: "stamina"},message:"must have required property '"+"stamina"+"'"};if(vErrors === null){vErrors = [err5];}else {vErrors.push(err5);}errors++;}if(data2.enemy !== undefined){if(typeof data2.enemy !== "string"){const err6 = {instancePath:instancePath+"/enemies/" + i0+"/enemy",schemaPath:"#/definitions/CombatEncounter/properties/enemy/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err6];}else {vErrors.push(err6);}errors++;}}if(data2.skill !== undefined){if(!(typeof data2.skill == "number")){const err7 = {instancePath:instancePath+"/enemies/" + i0+"/skill",schemaPath:"#/definitions/CombatEncounter/properties/skill/type",keyword:"type",params:{type: "number"},message:"must be number"};if(vErrors === null){vErrors = [err7];}else {vErrors.push(err7);}errors++;}}if(data2.stamina !== undefined){if(!(typeof data2.stamina == "number")){const err8 = {instancePath:instancePath+"/enemies/" + i0+"/stamina",schemaPath:"#/definitions/CombatEncounter/properties/stamina/type",keyword:"type",params:{type: "number"},message:"must be number"};if(vErrors === null){vErrors = [err8];}else {vErrors.push(err8);}errors++;}}if(data2.special_rules !== undefined){if(typeof data2.special_rules !== "string"){const err9 = {instancePath:instancePath+"/enemies/" + i0+"/special_rules",schemaPath:"#/definitions/CombatEncounter/properties/special_rules/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err9];}else {vErrors.push(err9);}errors++;}}if(data2.allow_escape !== undefined){if(typeof data2.allow_escape !== "boolean"){const err10 = {instancePath:instancePath+"/enemies/" + i0+"/allow_escape",schemaPath:"#/definitions/CombatEncounter/properties/allow_escape/type",keyword:"type",params:{type: "boolean"},message:"must be boolean"};if(vErrors === null){vErrors = [err10];}else {vErrors.push(err10);}errors++;}}}else {const err11 = {instancePath:instancePath+"/enemies/" + i0,schemaPath:"#/definitions/CombatEncounter/type",keyword:"type",params:{type: "object"},message:"must be object"};if(vErrors === null){vErrors = [err11];}else {vErrors.push(err11);}errors++;}}}else {const err12 = {instancePath:instancePath+"/enemies",schemaPath:"#/properties/enemies/type",keyword:"type",params:{type: "array"},message:"must be array"};if(vErrors === null){vErrors = [err12];}else {vErrors.push(err12);}errors++;}}if(data.outcomes !== undefined){let data8 = data.outcomes;if(data8 && typeof data8 == "object" && !Array.isArray(data8)){for(const key0 in data8){if(!(((key0 === "win") || (key0 === "lose")) || (key0 === "escape"))){const err13 = {instancePath:instancePath+"/outcomes",schemaPath:"#/properties/outcomes/additionalProperties",keyword:"additionalProperties",params:{additionalProperty: key0},message:"must NOT have additional properties"};if(vErrors === null){vErrors = [err13];}else {vErrors.push(err13);}errors++;}}if(data8.win !== undefined){if(!(validate16(data8.win, {instancePath:instancePath+"/outcomes/win",parentData:data8,parentDataProperty:"win",rootData}))){vErrors = vErrors === null ? validate16.errors : vErrors.concat(validate16.errors);errors = vErrors.length;}}if(data8.lose !== undefined){if(!(validate16(data8.lose, {instancePath:instancePath+"/outcomes/lose",parentData:data8,parentDataProperty:"lose",rootData}))){vErrors = vErrors === null ? validate16.errors : vErrors.concat(validate16.errors);errors = vErrors.length;}}if(data8.escape !== undefined){if(!(validate16(data8.escape, {instancePath:instancePath+"/outcomes/escape",parentData:data8,parentDataProperty:"escape",rootData}))){vErrors = vErrors === null ? validate16.errors : vErrors.concat(validate16.errors);errors = vErrors.length;}}}else {const err14 = {instancePath:instancePath+"/outcomes",schemaPath:"#/properties/outcomes/type",keyword:"type",params:{type: "object"},message:"must be object"};if(vErrors === null){vErrors = [err14];}else {vErrors.push(err14);}errors++;}}}else {const err15 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};if(vErrors === null){vErrors = [err15];}else {vErrors.push(err15);}errors++;}validate36.errors = vErrors;return errors === 0;}const schema32 = {"type":"object","required":["kind","outcome"],"properties":{"kind":{"const":"death"},"outcome":{"$ref":"#/definitions/OutcomeRef"},"description":{"type":"string"}}};function validate41(data, {instancePath="", parentData, parentDataProperty, rootData=data}={}){let vErrors = null;let errors = 0;if(data && typeof data == "object" && !Array.isArray(data)){if(data.kind === undefined){const err0 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "kind"},message:"must have required property '"+"kind"+"'"};if(vErrors === null){vErrors = [err0];}else {vErrors.push(err0);}errors++;}if(data.outcome === undefined){const err1 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "outcome"},message:"must have required property '"+"outcome"+"'"};if(vErrors === null){vErrors = [err1];}else {vErrors.push(err1);}errors++;}if(data.kind !== undefined){if("death" !== data.kind){const err2 = {instancePath:instancePath+"/kind",schemaPath:"#/properties/kind/const",keyword:"const",params:{allowedValue: "death"},message:"must be equal to constant"};if(vErrors === null){vErrors = [err2];}else {vErrors.push(err2);}errors++;}}if(data.outcome !== undefined){if(!(validate16(data.outcome, {instancePath:instancePath+"/outcome",parentData:data,parentDataProperty:"outcome",rootData}))){vErrors = vErrors === null ? validate16.errors : vErrors.concat(validate16.errors);errors = vErrors.length;}}if(data.description !== undefined){if(typeof data.description !== "string"){const err3 = {instancePath:instancePath+"/description",schemaPath:"#/properties/description/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err3];}else {vErrors.push(err3);}errors++;}}}else {const err4 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};if(vErrors === null){vErrors = [err4];}else {vErrors.push(err4);}errors++;}validate41.errors = vErrors;return errors === 0;}function validate12(data, {instancePath="", parentData, parentDataProperty, rootData=data}={}){let vErrors = null;let errors = 0;const _errs0 = errors;let valid0 = false;let passing0 = null;const _errs1 = errors;if(!(validate13(data, {instancePath,parentData,parentDataProperty,rootData}))){vErrors = vErrors === null ? validate13.errors : vErrors.concat(validate13.errors);errors = vErrors.length;}var _valid0 = _errs1 === errors;if(_valid0){valid0 = true;passing0 = 0;}const _errs2 = errors;if(data && typeof data == "object" && !Array.isArray(data)){if(data.kind === undefined){const err0 = {instancePath,schemaPath:"#/definitions/StatChangeEvent/required",keyword:"required",params:{missingProperty: "kind"},message:"must have required property '"+"kind"+"'"};if(vErrors === null){vErrors = [err0];}else {vErrors.push(err0);}errors++;}if(data.stat === undefined){const err1 = {instancePath,schemaPath:"#/definitions/StatChangeEvent/required",keyword:"required",params:{missingProperty: "stat"},message:"must have required property '"+"stat"+"'"};if(vErrors === null){vErrors = [err1];}else {vErrors.push(err1);}errors++;}if(data.amount === undefined){const err2 = {instancePath,schemaPath:"#/definitions/StatChangeEvent/required",keyword:"required",params:{missingProperty: "amount"},message:"must have required property '"+"amount"+"'"};if(vErrors === null){vErrors = [err2];}else {vErrors.push(err2);}errors++;}if(data.kind !== undefined){if("stat_change" !== data.kind){const err3 = {instancePath:instancePath+"/kind",schemaPath:"#/definitions/StatChangeEvent/properties/kind/const",keyword:"const",params:{allowedValue: "stat_change"},message:"must be equal to constant"};if(vErrors === null){vErrors = [err3];}else {vErrors.push(err3);}errors++;}}if(data.stat !== undefined){let data1 = data.stat;const _errs7 = errors;let valid3 = false;let passing1 = null;const _errs8 = errors;if(typeof data1 !== "string"){const err4 = {instancePath:instancePath+"/stat",schemaPath:"#/definitions/StatChangeEvent/properties/stat/oneOf/0/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err4];}else {vErrors.push(err4);}errors++;}var _valid1 = _errs8 === errors;if(_valid1){valid3 = true;passing1 = 0;}const _errs10 = errors;if(Array.isArray(data1)){const len0 = data1.length;for(let i0=0; i0<len0; i0++){if(typeof data1[i0] !== "string"){const err5 = {instancePath:instancePath+"/stat/" + i0,schemaPath:"#/definitions/StatChangeEvent/properties/stat/oneOf/1/items/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err5];}else {vErrors.push(err5);}errors++;}}}else {const err6 = {instancePath:instancePath+"/stat",schemaPath:"#/definitions/StatChangeEvent/properties/stat/oneOf/1/type",keyword:"type",params:{type: "array"},message:"must be array"};if(vErrors === null){vErrors = [err6];}else {vErrors.push(err6);}errors++;}var _valid1 = _errs10 === errors;if(_valid1 && valid3){valid3 = false;passing1 = [passing1, 1];}else {if(_valid1){valid3 = true;passing1 = 1;}}if(!valid3){const err7 = {instancePath:instancePath+"/stat",schemaPath:"#/definitions/StatChangeEvent/properties/stat/oneOf",keyword:"oneOf",params:{passingSchemas: passing1},message:"must match exactly one schema in oneOf"};if(vErrors === null){vErrors = [err7];}else {vErrors.push(err7);}errors++;}else {errors = _errs7;if(vErrors !== null){if(_errs7){vErrors.length = _errs7;}else {vErrors = null;}}}}if(data.amount !== undefined){let data3 = data.amount;if((!(typeof data3 == "number")) && (typeof data3 !== "string")){const err8 = {instancePath:instancePath+"/amount",schemaPath:"#/definitions/StatChangeEvent/properties/amount/type",keyword:"type",params:{type: schema18.properties.amount.type},message:"must be number,string"};if(vErrors === null){vErrors = [err8];}else {vErrors.push(err8);}errors++;}}if(data.permanent !== undefined){if(typeof data.permanent !== "boolean"){const err9 = {instancePath:instancePath+"/permanent",schemaPath:"#/definitions/StatChangeEvent/properties/permanent/type",keyword:"type",params:{type: "boolean"},message:"must be boolean"};if(vErrors === null){vErrors = [err9];}else {vErrors.push(err9);}errors++;}}}else {const err10 = {instancePath,schemaPath:"#/definitions/StatChangeEvent/type",keyword:"type",params:{type: "object"},message:"must be object"};if(vErrors === null){vErrors = [err10];}else {vErrors.push(err10);}errors++;}var _valid0 = _errs2 === errors;if(_valid0 && valid0){valid0 = false;passing0 = [passing0, 1];}else {if(_valid0){valid0 = true;passing0 = 1;}const _errs18 = errors;if(!(validate15(data, {instancePath,parentData,parentDataProperty,rootData}))){vErrors = vErrors === null ? validate15.errors : vErrors.concat(validate15.errors);errors = vErrors.length;}var _valid0 = _errs18 === errors;if(_valid0 && valid0){valid0 = false;passing0 = [passing0, 2];}else {if(_valid0){valid0 = true;passing0 = 2;}const _errs19 = errors;if(!(validate20(data, {instancePath,parentData,parentDataProperty,rootData}))){vErrors = vErrors === null ? validate20.errors : vErrors.concat(validate20.errors);errors = vErrors.length;}var _valid0 = _errs19 === errors;if(_valid0 && valid0){valid0 = false;passing0 = [passing0, 3];}else {if(_valid0){valid0 = true;passing0 = 3;}const _errs20 = errors;if(data && typeof data == "object" && !Array.isArray(data)){if(data.kind === undefined){const err11 = {instancePath,schemaPath:"#/definitions/ItemEvent/required",keyword:"required",params:{missingProperty: "kind"},message:"must have required property '"+"kind"+"'"};if(vErrors === null){vErrors = [err11];}else {vErrors.push(err11);}errors++;}if(data.action === undefined){const err12 = {instancePath,schemaPath:"#/definitions/ItemEvent/required",keyword:"required",params:{missingProperty: "action"},message:"must have required property '"+"action"+"'"};if(vErrors === null){vErrors = [err12];}else {vErrors.push(err12);}errors++;}if(data.name === undefined){const err13 = {instancePath,schemaPath:"#/definitions/ItemEvent/required",keyword:"required",params:{missingProperty: "name"},message:"must have required property '"+"name"+"'"};if(vErrors === null){vErrors = [err13];}else {vErrors.push(err13);}errors++;}if(data.kind !== undefined){if("item" !== data.kind){const err14 = {instancePath:instancePath+"/kind",schemaPath:"#/definitions/ItemEvent/properties/kind/const",keyword:"const",params:{allowedValue: "item"},message:"must be equal to constant"};if(vErrors === null){vErrors = [err14];}else {vErrors.push(err14);}errors++;}}if(data.action !== undefined){let data6 = data.action;if(typeof data6 !== "string"){const err15 = {instancePath:instancePath+"/action",schemaPath:"#/definitions/ItemEvent/properties/action/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err15];}else {vErrors.push(err15);}errors++;}if(!(((data6 === "add") || (data6 === "remove")) || (data6 === "reference"))){const err16 = {instancePath:instancePath+"/action",schemaPath:"#/definitions/ItemEvent/properties/action/enum",keyword:"enum",params:{allowedValues: schema17.properties.action.enum},message:"must be equal to one of the allowed values"};if(vErrors === null){vErrors = [err16];}else {vErrors.push(err16);}errors++;}}if(data.name !== undefined){if(typeof data.name !== "string"){const err17 = {instancePath:instancePath+"/name",schemaPath:"#/definitions/ItemEvent/properties/name/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err17];}else {vErrors.push(err17);}errors++;}}}else {const err18 = {instancePath,schemaPath:"#/definitions/ItemEvent/type",keyword:"type",params:{type: "object"},message:"must be object"};if(vErrors === null){vErrors = [err18];}else {vErrors.push(err18);}errors++;}var _valid0 = _errs20 === errors;if(_valid0 && valid0){valid0 = false;passing0 = [passing0, 4];}else {if(_valid0){valid0 = true;passing0 = 4;}const _errs28 = errors;if(!(validate24(data, {instancePath,parentData,parentDataProperty,rootData}))){vErrors = vErrors === null ? validate24.errors : vErrors.concat(validate24.errors);errors = vErrors.length;}var _valid0 = _errs28 === errors;if(_valid0 && valid0){valid0 = false;passing0 = [passing0, 5];}else {if(_valid0){valid0 = true;passing0 = 5;}const _errs29 = errors;if(!(validate28(data, {instancePath,parentData,parentDataProperty,rootData}))){vErrors = vErrors === null ? validate28.errors : vErrors.concat(validate28.errors);errors = vErrors.length;}var _valid0 = _errs29 === errors;if(_valid0 && valid0){valid0 = false;passing0 = [passing0, 6];}else {if(_valid0){valid0 = true;passing0 = 6;}const _errs30 = errors;if(!(validate32(data, {instancePath,parentData,parentDataProperty,rootData}))){vErrors = vErrors === null ? validate32.errors : vErrors.concat(validate32.errors);errors = vErrors.length;}var _valid0 = _errs30 === errors;if(_valid0 && valid0){valid0 = false;passing0 = [passing0, 7];}else {if(_valid0){valid0 = true;passing0 = 7;}const _errs31 = errors;if(!(validate36(data, {instancePath,parentData,parentDataProperty,rootData}))){vErrors = vErrors === null ? validate36.errors : vErrors.concat(validate36.errors);errors = vErrors.length;}var _valid0 = _errs31 === errors;if(_valid0 && valid0){valid0 = false;passing0 = [passing0, 8];}else {if(_valid0){valid0 = true;passing0 = 8;}const _errs32 = errors;if(!(validate41(data, {instancePath,parentData,parentDataProperty,rootData}))){vErrors = vErrors === null ? validate41.errors : vErrors.concat(validate41.errors);errors = vErrors.length;}var _valid0 = _errs32 === errors;if(_valid0 && valid0){valid0 = false;passing0 = [passing0, 9];}else {if(_valid0){valid0 = true;passing0 = 9;}const _errs33 = errors;if(data && typeof data == "object" && !Array.isArray(data)){if(data.kind === undefined){const err19 = {instancePath,schemaPath:"#/definitions/CustomEvent/required",keyword:"required",params:{missingProperty: "kind"},message:"must have required property '"+"kind"+"'"};if(vErrors === null){vErrors = [err19];}else {vErrors.push(err19);}errors++;}if(data.kind !== undefined){if("custom" !== data.kind){const err20 = {instancePath:instancePath+"/kind",schemaPath:"#/definitions/CustomEvent/properties/kind/const",keyword:"const",params:{allowedValue: "custom"},message:"must be equal to constant"};if(vErrors === null){vErrors = [err20];}else {vErrors.push(err20);}errors++;}}if(data.data !== undefined){let data9 = data.data;if(data9 && typeof data9 == "object" && !Array.isArray(data9)){}else {const err21 = {instancePath:instancePath+"/data",schemaPath:"#/definitions/CustomEvent/properties/data/type",keyword:"type",params:{type: "object"},message:"must be object"};if(vErrors === null){vErrors = [err21];}else {vErrors.push(err21);}errors++;}}}else {const err22 = {instancePath,schemaPath:"#/definitions/CustomEvent/type",keyword:"type",params:{type: "object"},message:"must be object"};if(vErrors === null){vErrors = [err22];}else {vErrors.push(err22);}errors++;}var _valid0 = _errs33 === errors;if(_valid0 && valid0){valid0 = false;passing0 = [passing0, 10];}else {if(_valid0){valid0 = true;passing0 = 10;}}}}}}}}}}}if(!valid0){const err23 = {instancePath,schemaPath:"#/oneOf",keyword:"oneOf",params:{passingSchemas: passing0},message:"must match exactly one schema in oneOf"};if(vErrors === null){vErrors = [err23];}else {vErrors.push(err23);}errors++;}else {errors = _errs0;if(vErrors !== null){if(_errs0){vErrors.length = _errs0;}else {vErrors = null;}}}validate12.errors = vErrors;return errors === 0;}function validate11(data, {instancePath="", parentData, parentDataProperty, rootData=data}={}){let vErrors = null;let errors = 0;const _errs2 = errors;let valid1 = true;const _errs3 = errors;if(data && typeof data == "object" && !Array.isArray(data)){if(data.isGameplaySection !== undefined){if(true !== data.isGameplaySection){const err0 = {};if(vErrors === null){vErrors = [err0];}else {vErrors.push(err0);}errors++;}}}var _valid0 = _errs3 === errors;errors = _errs2;if(vErrors !== null){if(_errs2){vErrors.length = _errs2;}else {vErrors = null;}}if(_valid0){const _errs5 = errors;if(data && typeof data == "object" && !Array.isArray(data)){if(data.sequence === undefined){const err1 = {instancePath,schemaPath:"#/allOf/0/then/required",keyword:"required",params:{missingProperty: "sequence"},message:"must have required property '"+"sequence"+"'"};if(vErrors === null){vErrors = [err1];}else {vErrors.push(err1);}errors++;}}var _valid0 = _errs5 === errors;valid1 = _valid0;}if(!valid1){const err2 = {instancePath,schemaPath:"#/allOf/0/if",keyword:"if",params:{failingKeyword: "then"},message:"must match \"then\" schema"};if(vErrors === null){vErrors = [err2];}else {vErrors.push(err2);}errors++;}const _errs7 = errors;const _errs8 = errors;if(data && typeof data == "object" && !Array.isArray(data)){let missing0;if((data.navigation === undefined) && (missing0 = "navigation")){const err3 = {};if(vErrors === null){vErrors = [err3];}else {vErrors.push(err3);}errors++;}}var valid3 = _errs8 === errors;if(valid3){const err4 = {instancePath,schemaPath:"#/allOf/1/not",keyword:"not",params:{},message:"must NOT be valid"};if(vErrors === null){vErrors = [err4];}else {vErrors.push(err4);}errors++;}else {errors = _errs7;if(vErrors !== null){if(_errs7){vErrors.length = _errs7;}else {vErrors = null;}}}const _errs10 = errors;const _errs11 = errors;if(data && typeof data == "object" && !Array.isArray(data)){let missing1;if((data.combat === undefined) && (missing1 = "combat")){const err5 = {};if(vErrors === null){vErrors = [err5];}else {vErrors.push(err5);}errors++;}}var valid4 = _errs11 === errors;if(valid4){const err6 = {instancePath,schemaPath:"#/allOf/2/not",keyword:"not",params:{},message:"must NOT be valid"};if(vErrors === null){vErrors = [err6];}else {vErrors.push(err6);}errors++;}else {errors = _errs10;if(vErrors !== null){if(_errs10){vErrors.length = _errs10;}else {vErrors = null;}}}const _errs13 = errors;const _errs14 = errors;if(data && typeof data == "object" && !Array.isArray(data)){let missing2;if((data.items === undefined) && (missing2 = "items")){const err7 = {};if(vErrors === null){vErrors = [err7];}else {vErrors.push(err7);}errors++;}}var valid5 = _errs14 === errors;if(valid5){const err8 = {instancePath,schemaPath:"#/allOf/3/not",keyword:"not",params:{},message:"must NOT be valid"};if(vErrors === null){vErrors = [err8];}else {vErrors.push(err8);}errors++;}else {errors = _errs13;if(vErrors !== null){if(_errs13){vErrors.length = _errs13;}else {vErrors = null;}}}const _errs16 = errors;const _errs17 = errors;if(data && typeof data == "object" && !Array.isArray(data)){let missing3;if((data.statModifications === undefined) && (missing3 = "statModifications")){const err9 = {};if(vErrors === null){vErrors = [err9];}else {vErrors.push(err9);}errors++;}}var valid6 = _errs17 === errors;if(valid6){const err10 = {instancePath,schemaPath:"#/allOf/4/not",keyword:"not",params:{},message:"must NOT be valid"};if(vErrors === null){vErrors = [err10];}else {vErrors.push(err10);}errors++;}else {errors = _errs16;if(vErrors !== null){if(_errs16){vErrors.length = _errs16;}else {vErrors = null;}}}const _errs19 = errors;const _errs20 = errors;if(data && typeof data == "object" && !Array.isArray(data)){let missing4;if((data.statChanges === undefined) && (missing4 = "statChanges")){const err11 = {};if(vErrors === null){vErrors = [err11];}else {vErrors.push(err11);}errors++;}}var valid7 = _errs20 === errors;if(valid7){const err12 = {instancePath,schemaPath:"#/allOf/5/not",keyword:"not",params:{},message:"must NOT be valid"};if(vErrors === null){vErrors = [err12];}else {vErrors.push(err12);}errors++;}else {errors = _errs19;if(vErrors !== null){if(_errs19){vErrors.length = _errs19;}else {vErrors = null;}}}const _errs22 = errors;const _errs23 = errors;if(data && typeof data == "object" && !Array.isArray(data)){let missing5;if((data.diceChecks === undefined) && (missing5 = "diceChecks")){const err13 = {};if(vErrors === null){vErrors = [err13];}else {vErrors.push(err13);}errors++;}}var valid8 = _errs23 === errors;if(valid8){const err14 = {instancePath,schemaPath:"#/allOf/6/not",keyword:"not",params:{},message:"must NOT be valid"};if(vErrors === null){vErrors = [err14];}else {vErrors.push(err14);}errors++;}else {errors = _errs22;if(vErrors !== null){if(_errs22){vErrors.length = _errs22;}else {vErrors = null;}}}const _errs25 = errors;const _errs26 = errors;if(data && typeof data == "object" && !Array.isArray(data)){let missing6;if((data.deathConditions === undefined) && (missing6 = "deathConditions")){const err15 = {};if(vErrors === null){vErrors = [err15];}else {vErrors.push(err15);}errors++;}}var valid9 = _errs26 === errors;if(valid9){const err16 = {instancePath,schemaPath:"#/allOf/7/not",keyword:"not",params:{},message:"must NOT be valid"};if(vErrors === null){vErrors = [err16];}else {vErrors.push(err16);}errors++;}else {errors = _errs25;if(vErrors !== null){if(_errs25){vErrors.length = _errs25;}else {vErrors = null;}}}if(data && typeof data == "object" && !Array.isArray(data)){if(data.id === undefined){const err17 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "id"},message:"must have required property '"+"id"+"'"};if(vErrors === null){vErrors = [err17];}else {vErrors.push(err17);}errors++;}if(data.presentation_html === undefined){const err18 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "presentation_html"},message:"must have required property '"+"presentation_html"+"'"};if(vErrors === null){vErrors = [err18];}else {vErrors.push(err18);}errors++;}if(data.isGameplaySection === undefined){const err19 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "isGameplaySection"},message:"must have required property '"+"isGameplaySection"+"'"};if(vErrors === null){vErrors = [err19];}else {vErrors.push(err19);}errors++;}if(data.type === undefined){const err20 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "type"},message:"must have required property '"+"type"+"'"};if(vErrors === null){vErrors = [err20];}else {vErrors.push(err20);}errors++;}if(data.id !== undefined){if(typeof data.id !== "string"){const err21 = {instancePath:instancePath+"/id",schemaPath:"#/definitions/SectionId/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err21];}else {vErrors.push(err21);}errors++;}}if(data.presentation_html !== undefined){if(typeof data.presentation_html !== "string"){const err22 = {instancePath:instancePath+"/presentation_html",schemaPath:"#/properties/presentation_html/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err22];}else {vErrors.push(err22);}errors++;}}if(data.pageStart !== undefined){if(!(typeof data.pageStart == "number")){const err23 = {instancePath:instancePath+"/pageStart",schemaPath:"#/properties/pageStart/type",keyword:"type",params:{type: "number"},message:"must be number"};if(vErrors === null){vErrors = [err23];}else {vErrors.push(err23);}errors++;}}if(data.pageEnd !== undefined){if(!(typeof data.pageEnd == "number")){const err24 = {instancePath:instancePath+"/pageEnd",schemaPath:"#/properties/pageEnd/type",keyword:"type",params:{type: "number"},message:"must be number"};if(vErrors === null){vErrors = [err24];}else {vErrors.push(err24);}errors++;}}if(data.isGameplaySection !== undefined){if(typeof data.isGameplaySection !== "boolean"){const err25 = {instancePath:instancePath+"/isGameplaySection",schemaPath:"#/properties/isGameplaySection/type",keyword:"type",params:{type: "boolean"},message:"must be boolean"};if(vErrors === null){vErrors = [err25];}else {vErrors.push(err25);}errors++;}}if(data.type !== undefined){let data6 = data.type;if(typeof data6 !== "string"){const err26 = {instancePath:instancePath+"/type",schemaPath:"#/properties/type/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err26];}else {vErrors.push(err26);}errors++;}if(!(((((((((((data6 === "section") || (data6 === "front_cover")) || (data6 === "back_cover")) || (data6 === "title_page")) || (data6 === "publishing_info")) || (data6 === "toc")) || (data6 === "intro")) || (data6 === "rules")) || (data6 === "adventure_sheet")) || (data6 === "template")) || (data6 === "background"))){const err27 = {instancePath:instancePath+"/type",schemaPath:"#/properties/type/enum",keyword:"enum",params:{allowedValues: schema12.properties.type.enum},message:"must be equal to one of the allowed values"};if(vErrors === null){vErrors = [err27];}else {vErrors.push(err27);}errors++;}}if(data.status !== undefined){let data7 = data.status;if(typeof data7 !== "string"){const err28 = {instancePath:instancePath+"/status",schemaPath:"#/properties/status/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err28];}else {vErrors.push(err28);}errors++;}if(!(((data7 === "death") || (data7 === "victory")) || (data7 === "defeat"))){const err29 = {instancePath:instancePath+"/status",schemaPath:"#/properties/status/enum",keyword:"enum",params:{allowedValues: schema12.properties.status.enum},message:"must be equal to one of the allowed values"};if(vErrors === null){vErrors = [err29];}else {vErrors.push(err29);}errors++;}}if(data.end_game !== undefined){if(typeof data.end_game !== "boolean"){const err30 = {instancePath:instancePath+"/end_game",schemaPath:"#/properties/end_game/type",keyword:"type",params:{type: "boolean"},message:"must be boolean"};if(vErrors === null){vErrors = [err30];}else {vErrors.push(err30);}errors++;}}if(data.sequence !== undefined){let data9 = data.sequence;if(Array.isArray(data9)){const len0 = data9.length;for(let i0=0; i0<len0; i0++){if(!(validate12(data9[i0], {instancePath:instancePath+"/sequence/" + i0,parentData:data9,parentDataProperty:i0,rootData}))){vErrors = vErrors === null ? validate12.errors : vErrors.concat(validate12.errors);errors = vErrors.length;}}}else {const err31 = {instancePath:instancePath+"/sequence",schemaPath:"#/properties/sequence/type",keyword:"type",params:{type: "array"},message:"must be array"};if(vErrors === null){vErrors = [err31];}else {vErrors.push(err31);}errors++;}}if(data.metadata !== undefined){let data11 = data.metadata;if(data11 && typeof data11 == "object" && !Array.isArray(data11)){if(data11.title !== undefined){if(typeof data11.title !== "string"){const err32 = {instancePath:instancePath+"/metadata/title",schemaPath:"#/properties/metadata/properties/title/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err32];}else {vErrors.push(err32);}errors++;}}}else {const err33 = {instancePath:instancePath+"/metadata",schemaPath:"#/properties/metadata/type",keyword:"type",params:{type: "object"},message:"must be object"};if(vErrors === null){vErrors = [err33];}else {vErrors.push(err33);}errors++;}}}else {const err34 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};if(vErrors === null){vErrors = [err34];}else {vErrors.push(err34);}errors++;}validate11.errors = vErrors;return errors === 0;}function validate10(data, {instancePath="", parentData, parentDataProperty, rootData=data}={}){/*# sourceURL="https://fighting-fantasy-engine.github.io/schema/gamebook.json" */;let vErrors = null;let errors = 0;if(data && typeof data == "object" && !Array.isArray(data)){if(data.metadata === undefined){const err0 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "metadata"},message:"must have required property '"+"metadata"+"'"};if(vErrors === null){vErrors = [err0];}else {vErrors.push(err0);}errors++;}if(data.sections === undefined){const err1 = {instancePath,schemaPath:"#/required",keyword:"required",params:{missingProperty: "sections"},message:"must have required property '"+"sections"+"'"};if(vErrors === null){vErrors = [err1];}else {vErrors.push(err1);}errors++;}if(data.metadata !== undefined){let data0 = data.metadata;if(data0 && typeof data0 == "object" && !Array.isArray(data0)){if(data0.title === undefined){const err2 = {instancePath:instancePath+"/metadata",schemaPath:"#/properties/metadata/required",keyword:"required",params:{missingProperty: "title"},message:"must have required property '"+"title"+"'"};if(vErrors === null){vErrors = [err2];}else {vErrors.push(err2);}errors++;}if(data0.startSection === undefined){const err3 = {instancePath:instancePath+"/metadata",schemaPath:"#/properties/metadata/required",keyword:"required",params:{missingProperty: "startSection"},message:"must have required property '"+"startSection"+"'"};if(vErrors === null){vErrors = [err3];}else {vErrors.push(err3);}errors++;}if(data0.formatVersion === undefined){const err4 = {instancePath:instancePath+"/metadata",schemaPath:"#/properties/metadata/required",keyword:"required",params:{missingProperty: "formatVersion"},message:"must have required property '"+"formatVersion"+"'"};if(vErrors === null){vErrors = [err4];}else {vErrors.push(err4);}errors++;}if(data0.title !== undefined){if(typeof data0.title !== "string"){const err5 = {instancePath:instancePath+"/metadata/title",schemaPath:"#/properties/metadata/properties/title/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err5];}else {vErrors.push(err5);}errors++;}}if(data0.author !== undefined){if(typeof data0.author !== "string"){const err6 = {instancePath:instancePath+"/metadata/author",schemaPath:"#/properties/metadata/properties/author/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err6];}else {vErrors.push(err6);}errors++;}}if(data0.startSection !== undefined){if(typeof data0.startSection !== "string"){const err7 = {instancePath:instancePath+"/metadata/startSection",schemaPath:"#/properties/metadata/properties/startSection/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err7];}else {vErrors.push(err7);}errors++;}}if(data0.formatVersion !== undefined){if(typeof data0.formatVersion !== "string"){const err8 = {instancePath:instancePath+"/metadata/formatVersion",schemaPath:"#/properties/metadata/properties/formatVersion/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err8];}else {vErrors.push(err8);}errors++;}}if(data0.validatorVersion !== undefined){if(typeof data0.validatorVersion !== "string"){const err9 = {instancePath:instancePath+"/metadata/validatorVersion",schemaPath:"#/properties/metadata/properties/validatorVersion/type",keyword:"type",params:{type: "string"},message:"must be string"};if(vErrors === null){vErrors = [err9];}else {vErrors.push(err9);}errors++;}}}else {const err10 = {instancePath:instancePath+"/metadata",schemaPath:"#/properties/metadata/type",keyword:"type",params:{type: "object"},message:"must be object"};if(vErrors === null){vErrors = [err10];}else {vErrors.push(err10);}errors++;}}if(data.sections !== undefined){let data6 = data.sections;if(data6 && typeof data6 == "object" && !Array.isArray(data6)){for(const key0 in data6){if(pattern0.test(key0)){if(!(validate11(data6[key0], {instancePath:instancePath+"/sections/" + key0.replace(/~/g, "~0").replace(/\//g, "~1"),parentData:data6,parentDataProperty:key0,rootData}))){vErrors = vErrors === null ? validate11.errors : vErrors.concat(validate11.errors);errors = vErrors.length;}}}}else {const err11 = {instancePath:instancePath+"/sections",schemaPath:"#/properties/sections/type",keyword:"type",params:{type: "object"},message:"must be object"};if(vErrors === null){vErrors = [err11];}else {vErrors.push(err11);}errors++;}}}else {const err12 = {instancePath,schemaPath:"#/type",keyword:"type",params:{type: "object"},message:"must be object"};if(vErrors === null){vErrors = [err12];}else {vErrors.push(err12);}errors++;}validate10.errors = vErrors;return errors === 0;}
return validate10;
})();

const VALIDATOR_VERSION = "ff-engine-validator-bundle@1.0.0";

function ajvErrorToValidationError(error) {
  const path = error.instancePath || error.schemaPath || '';
  let message = error.message || 'Validation error';
  if (error.keyword === 'required') {
    message = `Missing required field: ${error.params.missingProperty}`;
  } else if (error.keyword === 'type') {
    message = `Expected ${error.params.type}, got ${typeof error.data}`;
  } else if (error.keyword === 'enum') {
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
  if (!html) return '';
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function parseExpectedRange(gamebook) {
  const fromProvenance = gamebook?.provenance?.expected_range || gamebook?.provenance?.expectedRange;
  const raw = typeof fromProvenance === 'string' && fromProvenance ? fromProvenance : '1-400';
  const match = raw.match(/^\s*(\d+)\s*-\s*(\d+)\s*$/);
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
        path: `/sections/${key}/id`,
        message: `Section ID "${section.id}" does not match its key "${key}"`,
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
      message: `Duplicate section IDs detected: ${duplicates
        .map(d => `${d.id} (keys: ${d.keys.join(', ')})`)
        .join('; ')}`,
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
              path: `/sections/${sectionKey}/sequence/${index}/${pathSuffix}/targetSection`,
              message: `Sequence target section "${outcome.targetSection}" does not exist`,
              expected: 'existing section ID',
              received: outcome.targetSection,
            });
          }
        } else if (!outcome.terminal) {
          errors.push({
            path: `/sections/${sectionKey}/sequence/${index}/${pathSuffix}`,
            message: 'Outcome missing targetSection or terminal outcome',
            expected: 'targetSection or terminal',
            received: 'none',
          });
        }
      };
      if (kind === 'choice') {
        if (!event.targetSection) {
          errors.push({
            path: `/sections/${sectionKey}/sequence/${index}/targetSection`,
            message: 'Choice event missing targetSection',
            expected: 'targetSection',
            received: 'none',
          });
        } else if (!sectionIds.has(event.targetSection)) {
          errors.push({
            path: `/sections/${sectionKey}/sequence/${index}/targetSection`,
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
        path: `/sections/${key}/presentation_html`,
        message: `Section "${key}" has no text`,
      });
    }
  }
  return warnings;
}

function validateNoChoices(gamebook) {
  const warnings = [];
  for (const [key, section] of Object.entries(gamebook.sections || {})) {
    if (!section?.isGameplaySection) continue;
    if (section?.end_game) continue;
    if (section?.provenance?.stub) continue;
    const sequence = section?.sequence || [];
    const hasChoice = sequence.some(event => event && event.kind === 'choice');
    if (!hasChoice) {
      warnings.push({
        path: `/sections/${key}/sequence`,
        message: `Gameplay section "${key}" has no choices (potential dead end)`,
      });
    }
  }
  return warnings;
}

function findReachableSections(gamebook) {
  const reachable = new Set();
  const queue = [gamebook.metadata.startSection];
  const visited = new Set();
  while (queue.length > 0) {
    const currentId = queue.shift();
    if (visited.has(currentId)) continue;
    visited.add(currentId);
    const section = gamebook.sections[currentId];
    if (!section || !section.isGameplaySection) continue;
    reachable.add(currentId);
    const sequence = section.sequence || [];
    sequence.forEach(event => {
      const kind = event.kind;
      const pushTarget = (outcome) => {
        if (outcome && outcome.targetSection && !visited.has(outcome.targetSection)) {
          queue.push(outcome.targetSection);
        }
      };
      if (kind === 'choice' && event.targetSection) {
        pushTarget({ targetSection: event.targetSection });
      } else if (kind === 'stat_check') {
        pushTarget(event.pass);
        pushTarget(event.fail);
      } else if (kind === 'stat_change') {
        pushTarget(event.else);
      } else if (kind === 'test_luck') {
        pushTarget(event.lucky);
        pushTarget(event.unlucky);
      } else if (kind === 'item_check') {
        pushTarget(event.has);
        pushTarget(event.missing);
      } else if (kind === 'combat') {
        const outcomes = event.outcomes || {};
        pushTarget(outcomes.win);
        pushTarget(outcomes.lose);
        pushTarget(outcomes.escape);
      } else if (kind === 'death') {
        pushTarget(event.outcome);
      } else if (event.targetSection) {
        pushTarget({ targetSection: event.targetSection });
      }
    });
  }
  return reachable;
}

function findUnreachableSections(gamebook) {
  const warnings = [];
  const reachable = findReachableSections(gamebook);
  for (const [sectionKey, section] of Object.entries(gamebook.sections || {})) {
    if (section.isGameplaySection && !reachable.has(sectionKey)) {
      warnings.push({
        path: `/sections/${sectionKey}`,
        message: `Gameplay section "${sectionKey}" is unreachable from startSection "${gamebook.metadata.startSection}"`,
      });
    }
  }
  return warnings;
}

function validateGamebook(gamebook) {
  const errors = [];
  const warnings = [];
  errors.push(...validateWithSchema(gamebook));
  const hasBasicStructure = gamebook.metadata && gamebook.sections;
  if (hasBasicStructure) {
    if (gamebook.metadata.startSection && !(gamebook.metadata.startSection in gamebook.sections)) {
      errors.push({
        path: '/metadata/startSection',
        message: `startSection "${gamebook.metadata.startSection}" does not exist in sections`,
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
          message: `Validator version mismatch (gamebook expects ${expectedVersion}, validator is ${VALIDATOR_VERSION})`,
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
    console.error(`Error: File not found: ${filePath}`);
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
    } else {
      console.error('✗ Gamebook validation failed!');
      console.error(`\nFound ${result.errors.length} error(s):`);
      result.errors.forEach(error => {
        console.error(`  ${error.path}: ${error.message}`);
        if (error.expected && error.received) {
          console.error(`    Expected: ${error.expected}`);
          console.error(`    Received: ${error.received}`);
        }
      });
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
  } catch (error) {
    if (error instanceof SyntaxError) {
      console.error(`Error: Invalid JSON in ${filePath}`);
      console.error(error.message);
      process.exit(1);
    } else {
      console.error(`Error: ${error instanceof Error ? error.message : String(error)}`);
      process.exit(1);
    }
  }
}
