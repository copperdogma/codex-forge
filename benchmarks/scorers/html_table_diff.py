from bs4 import BeautifulSoup
import json

def parse_html_table(html):
    soup = BeautifulSoup(html, 'html.parser')
    rows = []
    # Find all tables
    tables = soup.find_all('table')
    for table in tables:
        # Get headers
        headers = [th.get_text(strip=True) for th in table.find_all('th')]
        if headers:
            rows.append(headers)
        
        for tr in table.find_all('tr'):
            cells = tr.find_all(['td', 'th'])
            # Skip if it's just headers we already processed
            if all(c.name == 'th' for c in cells):
                continue
            
            row_data = [c.get_text(strip=True) for c in cells]
            if row_data:
                rows.append(row_data)
    return rows

def get_assert(output, context):
    try:
        # Load Golden
        # promptfoo passes vars via context['vars']
        # We'll assume the golden file path is passed in vars.
        golden_path = context['vars']['golden_path']
        
        # Resolve path relative to promptfoo execution dir (benchmarks/)
        # golden_path in yaml is usually relative to the task file.
        # But here we are calling it from benchmarks/
        with open(golden_path, 'r') as f:
            golden_html = f.read()
            
        golden_rows = parse_html_table(golden_html)
        output_rows = parse_html_table(output)
        
        if not golden_rows:
            return {"pass": False, "score": 0, "reason": "Golden file has no tables"}
        if not output_rows:
            return {"pass": False, "score": 0, "reason": "Output has no tables"}
            
        errors = []
        if len(golden_rows) != len(output_rows):
            errors.append(f"Row count mismatch: Expected {len(golden_rows)}, Got {len(output_rows)}")
        
        # Compare overlapping rows
        for i, (g_row, o_row) in enumerate(zip(golden_rows, output_rows)):
            if len(g_row) != len(o_row):
                errors.append(f"Row {i} column count mismatch: Expected {len(g_row)}, Got {len(o_row)}")
                continue
                
            for j, (g_cell, o_cell) in enumerate(zip(g_row, o_row)):
                if g_cell != o_cell:
                    errors.append(f"Row {i} Col {j} mismatch: Expected '{g_cell}', Got '{o_cell}'")
        
        if errors:
            return {
                "pass": False, 
                "score": max(0, 1.0 - (len(errors) / (sum(len(r) for r in golden_rows) or 1))),
                "reason": "\n".join(errors[:10]) + (f"\n...and {len(errors)-10} more" if len(errors)>10 else "")
            }
            
        return {"pass": True, "score": 1.0, "reason": "Exact match"}
        
    except Exception as e:
        return {"pass": False, "score": 0, "reason": f"Scorer error: {str(e)}"}
