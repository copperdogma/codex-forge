#!/usr/bin/env python3
import argparse
import json
import os
from datetime import datetime

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Validation Forensic Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 1200px; margin: 0 auto; padding: 20px; background-color: #f5f5f7; }}
        h1, h2, h3 {{ color: #1d1d1f; }}
        .card {{ background: #fff; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        .status-valid {{ color: #28a745; font-weight: bold; }}
        .status-invalid {{ color: #dc3545; font-weight: bold; }}
        .stats {{ display: flex; gap: 20px; margin-bottom: 20px; }}
        .stat-item {{ flex: 1; text-align: center; padding: 15px; background: #f0f0f5; border-radius: 8px; }}
        .stat-value {{ display: block; font-size: 24px; font-weight: bold; }}
        .stat-label {{ font-size: 12px; color: #666; text-transform: uppercase; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ text-align: left; padding: 12px; border-bottom: 1px solid #eee; vertical-align: top; }}
        th {{ background-color: #f8f8f8; font-weight: 600; }}
        .trace-sid {{ font-weight: bold; font-size: 1.1em; color: #007aff; }}
        .suggested-action {{ font-style: italic; color: #8e8e93; margin-top: 4px; }}
        .snippet {{ font-family: "SF Mono", "Monaco", "Inconsolata", monospace; font-size: 12px; background: #f8f8f8; padding: 8px; border-radius: 4px; white-space: pre-wrap; word-break: break-all; }}
        .meta-list {{ list-style: none; padding: 0; margin: 0; font-size: 13px; }}
        .meta-list li {{ margin-bottom: 4px; }}
        .meta-label {{ color: #666; font-weight: 500; min-width: 120px; display: inline-block; }}
        .tag {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; text-transform: uppercase; margin-right: 4px; }}
        .tag-error {{ background: #ffd7d7; color: #d00; }}
        .tag-warning {{ background: #fff3cd; color: #856404; }}
        .tag-info {{ background: #d1ecf1; color: #0c5460; }}
        .collapsible {{ cursor: pointer; user-select: none; }}
        .collapsible:after {{ content: ' \u25BC'; font-size: 10px; }}
        .active:after {{ content: ' \u25B2'; }}
        .content {{ display: none; overflow: hidden; }}
    </style>
</head>
<body>
    <h1>Validation Forensic Report</h1>
    <div class="card">
        <div class="stats">
            <div class="stat-item">
                <span class="stat-label">Status</span>
                <span class="stat-value {status_class}">{status_text}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Total Sections</span>
                <span class="stat-value">{total_sections}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Missing</span>
                <span class="stat-value">{missing_count}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">No Text</span>
                <span class="stat-value">{no_text_count}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">No Choices</span>
                <span class="stat-value">{no_choices_count}</span>
            </div>
        </div>
        <div>
            <strong>Run ID:</strong> {run_id}<br>
            <strong>Generated:</strong> {timestamp}
        </div>
    </div>

    {content_html}

    <script>
        document.querySelectorAll('.collapsible').forEach(button => {{
            button.addEventListener('click', () => {{
                button.classList.toggle('active');
                const content = button.nextElementSibling;
                if (content.style.display === "block") {{
                    content.style.display = "none";
                }} else {{
                    content.style.display = "block";
                }}
            }});
        }});
    </script>
</body>
</html>
"""

def generate_html(report_path: str, out_path: str):
    with open(report_path, 'r', encoding='utf-8') as f:
        report = json.load(f)

    status_text = "VALID" if report.get("is_valid") else "INVALID"
    status_class = "status-valid" if report.get("is_valid") else "status-invalid"
    
    missing_sections = report.get("missing_sections", [])
    no_text = report.get("sections_with_no_text", [])
    no_choices = report.get("sections_with_no_choices", [])
    forensics = report.get("forensics", {})

    content_parts = []

    def render_trace_table(title, section_ids, forensic_category):
        if not section_ids:
            return ""
        
        parts = [f"<h2>{title} ({len(section_ids)})</h2>", "<div class='card'><table>"]
        parts.append("<thead><tr><th>Section</th><th>Diagnostic Trace</th><th>Evidence & Hits</th></tr></thead><tbody>")
        
        category_traces = forensics.get(forensic_category, {})
        
        for sid in section_ids:
            trace = category_traces.get(sid, {})
            
            # Column 1: Section ID + Basic Info
            parts.append("<tr>")
            parts.append(f"<td><span class='trace-sid'>{sid}</span>")
            
            ending = trace.get("ending_info")
            if ending:
                etype = ending.get("ending_type", "unknown")
                parts.append(f"<br><span class='tag tag-info'>{etype}</span>")
            
            parts.append("</td>")
            
            # Column 2: Diagnostic Trace
            parts.append("<td>")
            if trace.get("suggested_action"):
                parts.append(f"<div class='suggested-action'><strong>Action:</strong> {trace['suggested_action']}</div>")
            
            meta = trace.get("span") or {}
            parts.append("<ul class='meta-list'>")
            if trace.get("boundary_source"):
                parts.append(f"<li><span class='meta-label'>Boundary Source:</span> {trace['boundary_source']} (conf: {trace.get('boundary_confidence', 'N/A')})</li>")
            if meta.get("start_page"):
                parts.append(f"<li><span class='meta-label'>Pages:</span> {meta.get('start_page')} to {meta.get('end_page')}</li>")
            if meta.get("span_length") is not None:
                parts.append(f"<li><span class='meta-label'>Element Span:</span> {meta.get('span_length')} units</li>")
            if trace.get("portion_length") is not None:
                parts.append(f"<li><span class='meta-label'>Text Length:</span> {trace.get('portion_length')} chars</li>")
            parts.append("</ul>")
            
            if trace.get("portion_html"):
                import html
                escaped_html = html.escape(trace["portion_html"])
                parts.append("<div style='margin-top:12px;'><strong>Portion HTML Source:</strong></div>")
                parts.append(f"<div class='snippet' style='max-height: 400px; overflow-y: auto;'>{escaped_html}</div>")
            
            parts.append("</td>")
            
            # Column 3: Evidence & Hits
            parts.append("<td>")
            if trace.get("evidence"):
                parts.append("<strong>Boundary Evidence:</strong>")
                parts.append(f"<div class='snippet'>{json.dumps(trace['evidence'], indent=2)}</div>")
            
            core_hits = trace.get("elements_core_hits", [])
            if core_hits:
                parts.append("<div class='collapsible'>Search Hits (elements_core)</div>")
                parts.append("<div class='content'>")
                for hit in core_hits:
                    parts.append(f"<div style='margin-bottom:8px;'><small>ID: {hit.get('id')} | Page: {hit.get('page')}</small>")
                    parts.append(f"<div class='snippet'>{hit.get('text')}</div></div>")
                parts.append("</div>")
            
            parts.append("</td></tr>")
            
        parts.append("</tbody></table></div>")
        return "".join(parts)

    content_parts.append(render_trace_table("Missing Sections", missing_sections, "missing_sections"))
    content_parts.append(render_trace_table("Sections with No Text", no_text, "no_text"))
    content_parts.append(render_trace_table("Gameplay Sections with No Choices", no_choices, "no_choices"))

    # Errors and Warnings
    if report.get("errors") or report.get("warnings"):
        parts = ["<h2>Summary Messages</h2>", "<div class='card'>"]
        for err in report.get("errors", []):
            parts.append(f"<div style='color:#d00; margin-bottom:8px;'><strong>Error:</strong> {err}</div>")
        for warn in report.get("warnings", []):
            parts.append(f"<div style='color:#856404; margin-bottom:8px;'><strong>Warning:</strong> {warn}</div>")
        parts.append("</div>")
        content_parts.append("".join(parts))

    final_html = HTML_TEMPLATE.format(
        status_text=status_text,
        status_class=status_class,
        total_sections=report.get("total_sections", 0),
        missing_count=len(missing_sections),
        no_text_count=len(no_text),
        no_choices_count=len(no_choices),
        run_id=report.get("run_id", "N/A"),
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        content_html="".join(content_parts)
    )

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(final_html)
    print(f"Generated forensic HTML report → {out_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate human-readable forensic report from validation_report.json")
    parser.add_argument("report", help="Path to validation_report.json")
    parser.add_argument("--out", help="Output HTML path (default: sibling to report)")
    args = parser.parse_args()

    out_path = args.out
    if not out_path:
        out_path = args.report.replace(".json", ".html")
    
    generate_html(args.report, out_path)
