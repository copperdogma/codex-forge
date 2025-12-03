# Test Data Fixtures

- `tbotb-mini.md` / `tbotb-mini.pdf`: 8-section micro branch adapted from **To Be or Not To Be** by Ryan North (2013). Licensed **CC BY-NC 3.0**; used here for non-commercial smoke testing. Source PDF: `input/Ryan North - To Be or Not To Be.pdf` (not modified).

Regeneration:
- PDF (requires `fpdf2`: `python -m pip install fpdf2` or use vendored `testdata/vendor`):  
  `python - <<'PY'\nimport sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path('testdata/vendor').resolve()))\nfrom fpdf import FPDF\nsrc = Path('testdata/tbotb-mini.md').read_text().splitlines()\npdf = FPDF(); pdf.set_auto_page_break(auto=True, margin=15); pdf.add_page()\npdf.set_font('Helvetica','B',14); pdf.cell(0,10,text='To Be or Not To Be -- Mini FF Branch',ln=1)\npdf.set_font('Helvetica','',9); pdf.multi_cell(0,5,text='Adapted from To Be or Not To Be by Ryan North (2013). Licensed CC BY-NC 3.0. For non-commercial smoke testing.'); pdf.ln(4)\nfor line in src:\n    if line.startswith('## '):\n        pdf.set_font('Helvetica','B',12); pdf.cell(0,8,line.replace('## ','').strip(),ln=1); pdf.set_font('Helvetica','',11)\n    elif line.startswith('#'):\n        continue\n    else:\n        pdf.multi_cell(0,6,line.strip()); pdf.ln(1)\nPath('testdata/tbotb-mini.pdf').write_bytes(pdf.output(dest='S'))\nPY`\n+- Optional images: `pdftoppm -png testdata/tbotb-mini.pdf testdata/tbotb-mini`.
