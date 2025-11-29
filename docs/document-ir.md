

# Document IR (Intermediate Representation)

**Status:** v0 (Initial implementation - Unstructured-native)
**Schema Version:** `unstructured_element_v1`
**Created:** 2025-11-28

---

## Overview

The **Document IR** is the canonical intermediate representation for all document content in codex-forge. It is based on **Unstructured's native element format**, serialized to JSON with minimal wrapping to add codex-forge provenance metadata.

Document IR is:
- **Unstructured-native:** Preserves Unstructured's rich element types and metadata
- **Structured:** Captures document elements (Title, NarrativeText, Table, Image, etc.) with layout and hierarchy
- **Provenance-rich:** Adds _codex namespace for run tracking without polluting Unstructured fields
- **Future-proof:** Evolves automatically as Unstructured adds features

Think of Document IR as **Unstructured elements serialized to JSONL** — the core "bytecode for content" that flows unchanged through the pipeline.

---

## Pipeline Architecture

Codex-forge follows a 5-stage model:

1. **Intake → IR (generic)**: PDF → Unstructured elements (elements.jsonl)
2. **Verify IR (generic)**: QA on completeness, page coverage
3. **Portionize (domain-specific)**: Identify portions (sections, chapters) that reference elements by ID
4. **Augment (domain-specific)**: Add domain data (choices for CYOA, relationships for genealogy)
5. **Export (format-specific)**: Build output (FF Engine JSON, HTML, Markdown) using elements + portions

**The IR (elements.jsonl) remains unchanged throughout the pipeline.** Portionization and augmentation create separate artifacts that reference elements by ID rather than transforming them.

---

## Why Unstructured-Native?

### The Original Plan (Abandoned)

Initially, we considered creating a normalized schema (`DocumentBlock`) that mapped Unstructured types to simplified types:
- `Title` → `heading`
- `NarrativeText` → `paragraph`
- `Table` → `table`

This would create an abstraction layer between Unstructured and downstream code.

### Why We Changed Our Mind

**Problem:** Unnecessary abstraction layer that adds complexity without clear benefit.

Since Unstructured is our primary (likely only) intake source, creating a normalized layer:
- ❌ Loses metadata (detection scores, emphasis, hierarchy)
- ❌ Requires maintaining a type mapping
- ❌ Doesn't evolve as Unstructured adds features
- ❌ Makes debugging harder (can't compare with Unstructured directly)

**Solution:** Use Unstructured's format directly with minimal wrapping.

**Benefits:**
- ✅ Preserves all metadata (coordinates, table HTML, parent_id, emphasis, scores)
- ✅ Richer IR for downstream use
- ✅ Simpler (no normalization code)
- ✅ Future-proof (new Unstructured features flow through automatically)
- ✅ Easier debugging (can inspect raw Unstructured output)

---

## Schema

### UnstructuredElement

The core IR unit (defined in `schemas.py`):

```python
class UnstructuredElement(BaseModel):
    # Core Unstructured fields
    id: str  # Element ID from Unstructured
    type: str  # Unstructured type (Title, NarrativeText, Table, ListItem, etc.)
    text: str = ""  # Plain text content

    # Unstructured metadata (all fields preserved)
    metadata: Dict[str, Any] = {}

    # Codex-forge namespace (serialized as '_codex' in JSON)
    codex: CodexMetadata = Field(alias="_codex")
```

### CodexMetadata

Our provenance namespace:

```python
class CodexMetadata(BaseModel):
    run_id: Optional[str]
    module_id: Optional[str]
    sequence: Optional[int]  # For stable sorting
    created_at: Optional[str]  # ISO 8601 timestamp
```

### JSON Serialization

Elements are serialized to JSON with `by_alias=True` to get `_codex` in the output:

```json
{
  "id": "abc-123",
  "type": "Title",
  "text": "Chapter 1: The Beginning",
  "metadata": {
    "page_number": 5,
    "coordinates": {"points": [[100, 200], [500, 250]]},
    "text_as_html": null,
    "parent_id": null,
    "emphasized_text_contents": [],
    "detection_class_prob": 0.98
  },
  "_codex": {
    "run_id": "my-run-123",
    "module_id": "unstructured_pdf_intake_v1",
    "sequence": 42,
    "created_at": "2025-11-28T22:30:00Z"
  }
}
```

---

## Unstructured Element Types

Unstructured provides a rich type vocabulary. Common types include:

| Type | Description | Use in Codex-forge |
|------|-------------|-------------------|
| `Title` | Document/section titles | Main headings |
| `NarrativeText` | Body paragraphs | Main content |
| `Text` | Generic text | Fallback for text |
| `ListItem` | List items | Bullet/numbered lists |
| `Table` | Tables with structure | Genealogy data, stats |
| `Image` | Images/figures | Photos, diagrams |
| `Header` | Page headers | Usually skipped in output |
| `Footer` | Page footers | Usually skipped in output |
| `FigureCaption` | Image captions | Figure descriptions |
| `PageBreak` | Page boundaries | Usually ignored |

**We preserve these types exactly as Unstructured provides them.** No normalization or mapping.

---

## Metadata Fields

Unstructured elements include rich metadata. Key fields:

### Core Metadata
- `page_number` (int): 1-based page number
- `coordinates` (dict): Bounding box as `{"points": [[x1,y1], [x2,y2], ...]}`
- `text_as_html` (str): HTML rendering (especially for tables)
- `parent_id` (str): Parent element for hierarchy

### Additional Metadata
- `emphasized_text_contents` (list): Bold/italic text spans
- `emphasized_text_tags` (list): Emphasis types (bold, italic)
- `detection_class_prob` (float): Confidence score from detection model
- `category` (str): Element category
- `filename` (str): Source filename
- `filetype` (str): Source file type

**All metadata is preserved in the `metadata` dict.** Downstream modules can access any field they need.

---

## Output Format

Document IR is written as **JSONL** (JSON Lines):

**File:** `elements.jsonl` (one element per line)

```jsonl
{"id": "elem-1", "type": "Title", "text": "Chapter 1", "metadata": {...}, "_codex": {...}}
{"id": "elem-2", "type": "NarrativeText", "text": "Once upon a time...", "metadata": {...}, "_codex": {...}}
{"id": "elem-3", "type": "Table", "text": "...", "metadata": {"text_as_html": "<table>...</table>", ...}, "_codex": {...}}
```

---

## Using Document IR in Recipes

### Example 1: Genealogy HTML Rendering

Direct consumption of elements for layout-faithful output:

```yaml
stages:
  - id: unstructured_intake
    module: unstructured_pdf_intake_v1
    params:
      strategy: hi_res
      infer_table_structure: true

  - id: render_html
    module: render_html_from_elements_v1
    needs: [unstructured_intake]
    params:
      elements: output/.../elements.jsonl
      output_filename: genealogy.html
```

### Example 2: Fighting Fantasy Pipeline (Future)

Portions reference elements by ID:

```yaml
stages:
  - id: unstructured_intake
    module: unstructured_pdf_intake_v1

  - id: portionize
    module: portionize_sliding_v1
    needs: [unstructured_intake]
    # Reads elements.jsonl, creates portions that reference element IDs

  - id: export_ff
    module: build_ff_engine_v1
    needs: [portionize]
    # Reads both elements.jsonl (for text) and portions.jsonl (for structure)
```

**Note:** The FF pipeline updates are TODO; current portionize modules still use pages_raw.jsonl.

---

## Creating Modules That Consume Elements

### Reading Elements

```python
from modules.common.utils import read_jsonl
from schemas import UnstructuredElement

# Read and validate
elements_raw = list(read_jsonl("elements.jsonl"))
elements = [UnstructuredElement(**e) for e in elements_raw]

# Or just use dicts (no validation)
elements = list(read_jsonl("elements.jsonl"))
```

### Grouping by Page

```python
from collections import defaultdict

pages = defaultdict(list)
for elem in elements:
    page_num = elem.get("metadata", {}).get("page_number", 1)
    pages[page_num].append(elem)
```

### Sorting for Reading Order

```python
def sort_key(elem):
    # Try _codex.sequence first
    sequence = elem.get("_codex", {}).get("sequence")
    if sequence is not None:
        return (0, sequence)

    # Try coordinates (y-coordinate, then x)
    coords = elem.get("metadata", {}).get("coordinates", {})
    points = coords.get("points", [])
    if points:
        ys = [p[1] for p in points]
        xs = [p[0] for p in points]
        return (1, min(ys), min(xs))

    return (2, 0)

sorted_elems = sorted(page_elements, key=sort_key)
```

### Handling Unstructured Types

```python
def render_element(elem):
    elem_type = elem.get("type")
    text = elem.get("text", "")
    metadata = elem.get("metadata", {})

    if elem_type == "Title":
        return f"<h1>{text}</h1>"
    elif elem_type == "NarrativeText":
        return f"<p>{text}</p>"
    elif elem_type == "Table":
        table_html = metadata.get("text_as_html")
        return table_html if table_html else f"<pre>{text}</pre>"
    # ... handle other types
```

---

## Portionization Pattern (Future)

When portions reference elements by ID instead of embedding text:

**elements.jsonl** (unchanged):
```json
{"id": "elem-1", "type": "Title", "text": "1", ...}
{"id": "elem-2", "type": "NarrativeText", "text": "You enter a dark room...", ...}
```

**portions.jsonl** (references elements):
```json
{
  "portion_id": "section-1",
  "element_ids": ["elem-1", "elem-2"],
  "page_start": 5,
  "page_end": 5,
  "choices": [{"target": "45", "text": "Go left"}]
}
```

**Export module** reads both files to build output.

---

## API Stability

**IMPORTANT:** Codex-forge is greenfield with no external users.

- ❌ **No stability guarantees** for element schema or format
- ✅ **Free to change** as we learn what works
- ✅ **Unstructured updates** may change metadata fields
- ✅ **Acceptable to break** old pipelines between stories

Schema versioning (`unstructured_element_v1`) tracks changes for future migrations if needed.

---

## Migration from Old IR

**Old IR:** `pages_raw.jsonl` with `{page, text, image}`

**New IR:** `elements.jsonl` with Unstructured elements

**Migration path:**
1. Use `unstructured_pdf_intake_v1` instead of `extract_ocr_v1` or `extract_text_v1`
2. Update downstream modules to read `elements.jsonl` and group/filter as needed
3. For FF pipeline: update portionize to read elements; update export to read elements + portions

**No adapter provided** — this is a one-way migration to the new architecture.

---

## FAQ

### Q: What if I need fields not in Unstructured metadata?

A: Add them to the `_codex` namespace or create a parallel annotation file that references element IDs.

### Q: Can I use Document IR without Unstructured?

A: Yes, but you'd need to create elements in the same format. For example, an OCR-based intake could create `NarrativeText` elements from detected text regions.

### Q: How do I access table HTML?

A: Check `element["metadata"]["text_as_html"]`. If present, it contains the table as HTML. Otherwise, fall back to `element["text"]` (plain text).

### Q: What if Unstructured changes its metadata format?

A: Since we preserve the full metadata dict, old elements still work. New fields appear automatically. If Unstructured removes fields, update consuming code to handle gracefully.

### Q: Why JSONL instead of JSON?

A: **JSONL** (one element per line) is:
- Streamable (process block-by-block)
- Works for large documents (1000s of pages)
- Easier to debug (grep, head, tail, wc -l)

### Q: How do I filter elements by type?

A: ```python
titles = [e for e in elements if e["type"] == "Title"]
no_headers = [e for e in elements if e["type"] not in ("Header", "Footer")]
```

---

## References

- **Schema definition:** `schemas.py:334-400` (UnstructuredElement, CodexMetadata)
- **Intake module:** `modules/intake/unstructured_pdf_intake_v1/`
- **Render module:** `modules/render/render_html_from_elements_v1/`
- **Genealogy recipe:** `configs/recipes/recipe-genealogy-html.yaml`
- **FF recipe (TODO):** `configs/recipes/recipe-ff-unstructured.yaml`
- **Story:** `docs/stories/story-032-unstructured-intake-and-document-ir-adoption.md`
- **Unstructured library:** https://unstructured.io/

---

## Changelog

### 2025-11-28 — Initial version (v0, Unstructured-native)

- Adopted Unstructured's element format as core IR
- Created `UnstructuredElement` and `CodexMetadata` schemas
- Implemented `unstructured_pdf_intake_v1` module (elements.jsonl output)
- Implemented `render_html_from_elements_v1` module
- Documented element format, _codex namespace, and consumption patterns
- Explicitly noted greenfield status (no API stability)
- Decided against normalization layer (preserves all Unstructured metadata)
