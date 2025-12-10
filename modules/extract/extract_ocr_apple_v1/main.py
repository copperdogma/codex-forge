#!/usr/bin/env python3
"""
macOS Vision OCR wrapper (VNRecognizeTextRequest) producing pagelines_v1.

Requirements: macOS with Xcode command-line tools (swiftc), Vision + PDFKit frameworks.
This module compiles a small Swift helper on first run and reuses it thereafter.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from modules.common.utils import ensure_dir, save_jsonl, ProgressLogger
from schemas import PageLines


SWIFT_SOURCE = r'''
import Foundation
import Vision
import PDFKit

struct Line: Codable {
    let text: String
    let confidence: Float
    let bbox: [Float]  // [x0,y0,x1,y1] normalized 0..1 within page
}

struct PageOut: Codable {
    let page: Int
    let lines: [Line]
}

func run(pdfPath: String, start: Int, end: Int?, lang: String, fast: Bool) throws {
    guard let doc = PDFDocument(url: URL(fileURLWithPath: pdfPath)) else {
        throw NSError(domain: "apple_vision_ocr", code: 1, userInfo: [NSLocalizedDescriptionKey: "Failed to open PDF"])
    }
    let pageCount = doc.pageCount
    let lastPage = end ?? pageCount
    let recogLevel: VNRequestTextRecognitionLevel = fast ? .fast : .accurate
    let recogReq = VNRecognizeTextRequest()
    recogReq.recognitionLevel = recogLevel
    recogReq.recognitionLanguages = [lang]
    recogReq.usesLanguageCorrection = true
    recogReq.usesCPUOnly = false

    let outEncoder = JSONEncoder()
    for pageIndex in max(0, start-1)..<min(lastPage, pageCount) {
        guard let page = doc.page(at: pageIndex) else { continue }
        let box = page.bounds(for: .mediaBox)
        let targetSize = CGSize(width: box.width, height: box.height)
        guard let img = page.thumbnail(of: targetSize, for: .mediaBox).cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
        let handler = VNImageRequestHandler(cgImage: img, options: [:])
        try handler.perform([recogReq])
        var lines: [Line] = []
        if let results = recogReq.results {
            for r in results {
                guard let cand = r.topCandidates(1).first else { continue }
                // VNRectangleObservation bbox normalized (x,y,width,height)
                let bbox = r.boundingBox
                let line = Line(text: cand.string,
                                confidence: cand.confidence,
                                bbox: [Float(bbox.minX), Float(bbox.minY), Float(bbox.maxX), Float(bbox.maxY)])
                lines.append(line)
            }
        }
        let pageOut = PageOut(page: pageIndex + 1, lines: lines)
        let data = try outEncoder.encode(pageOut)
        if let jsonStr = String(data: data, encoding: .utf8) {
            print(jsonStr)
        }
        recogReq.results = nil
    }
}

let args = CommandLine.arguments
guard args.count >= 4 else {
    fputs("usage: vision_ocr <pdf> <start> <end_or_0> <lang> <fast 0|1>\\n", stderr)
    exit(2)
}
let pdf = args[1]
let start = Int(args[2]) ?? 1
let endVal = Int(args[3]) ?? 0
let lang = args.count > 4 ? args[4] : "en-US"
let fast = args.count > 5 ? (Int(args[5]) ?? 0) != 0 : false
do {
    try run(pdfPath: pdf, start: start, end: endVal == 0 ? nil : endVal, lang: lang, fast: fast)
} catch {
    fputs("error: \\(error)\\n", stderr)
    exit(1)
}
'''


def build_swift_helper(bin_path: Path):
    src_path = bin_path.with_suffix(".swift")
    src_path.write_text(SWIFT_SOURCE)
    cmd = ["swiftc", "-O", "-o", str(bin_path), str(src_path)]
    subprocess.check_call(cmd)


def parse_swift_output(lines):
    for line in lines:
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        yield obj


def main():
    parser = argparse.ArgumentParser(description="Apple Vision OCR (VNRecognizeTextRequest) to pagelines_v1")
    parser.add_argument("--pdf", required=True, help="Input PDF path")
    parser.add_argument("--outdir", required=True, help="Output directory")
    parser.add_argument("--start", type=int, default=1, help="First page (1-based)")
    parser.add_argument("--end", type=int, help="Last page (inclusive)")
    parser.add_argument("--lang", default="en-US", help="Language code for recognizer")
    parser.add_argument("--fast", action="store_true", help="Use .fast recognitionLevel (less accurate)")
    parser.add_argument("--progress-file", help="Path to pipeline_events.jsonl")
    parser.add_argument("--state-file", help="Path to pipeline_state.json")
    parser.add_argument("--run-id", help="Run identifier for logging")
    args = parser.parse_args()

    logger = ProgressLogger(state_path=args.state_file, progress_path=args.progress_file, run_id=args.run_id)

    ensure_dir(args.outdir)
    out_index = os.path.join(args.outdir, "ocr_apple")
    ensure_dir(out_index)
    pagelines_path = os.path.join(out_index, "pagelines.jsonl")

    bin_path = Path(out_index) / "vision_ocr"
    if not bin_path.exists():
        logger.log("extract", "running", current=0, total=1,
                   message="Compiling Vision OCR helper", artifact=str(bin_path),
                   module_id="extract_ocr_apple_v1")
        build_swift_helper(bin_path)

    cmd = [str(bin_path), args.pdf, str(args.start), str(args.end or 0), args.lang, "1" if args.fast else "0"]
    logger.log("extract", "running", current=args.start, total=args.end or 0,
               message="Running Vision OCR", artifact=pagelines_path, module_id="extract_ocr_apple_v1")

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    out_lines, err = proc.communicate()
    if proc.returncode != 0:
        sys.stderr.write(err)
        raise SystemExit(f"Vision OCR failed with code {proc.returncode}")

    page_objs = list(parse_swift_output(out_lines.splitlines()))
    pages = []
    for obj in page_objs:
        lines = []
        for ln in obj.get("lines", []):
            lines.append({
                "text": ln.get("text", ""),
                "confidence": ln.get("confidence", 0.0),
                "bbox": ln.get("bbox", []),
            })
        pages.append(PageLines(
            page=obj["page"],
            lines=lines,
            schema_version="pagelines_v1",
            module_id="extract_ocr_apple_v1",
            run_id=args.run_id
        ).model_dump())

    save_jsonl(pagelines_path, pages)
    logger.log("extract", "done", current=len(pages), total=len(pages),
               message=f"Wrote {len(pages)} pagelines", artifact=pagelines_path,
               module_id="extract_ocr_apple_v1", schema_version="pagelines_v1")
    print(f"[apple-ocr] wrote {len(pages)} pages to {pagelines_path}")


if __name__ == "__main__":
    main()
