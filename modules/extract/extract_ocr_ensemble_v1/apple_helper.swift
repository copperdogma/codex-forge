import Foundation
import Vision
import PDFKit

struct Line: Codable {
    let text: String
    let confidence: Float
    let bbox: [Float]          // normalized to full page
    let column: Int
}

struct PageOut: Codable {
    let page: Int
    let columns: [[Float]]     // [[x0, x1]]
    let lines: [Line]
}

/// Gap-based two-column detector using a fast recognition pass.
/// Returns normalized x spans (x0, x1). Falls back to single column on uncertainty.
func detectColumns(for image: CGImage, lang: String) throws -> [[Float]] {
    let quickReq = VNRecognizeTextRequest()
    quickReq.recognitionLevel = .fast
    quickReq.recognitionLanguages = [lang]
    quickReq.usesLanguageCorrection = false
    let handler = VNImageRequestHandler(cgImage: image, options: [:])
    try handler.perform([quickReq])
    guard let observations = quickReq.results, observations.count >= 6 else {
        return [[0, 1]]
    }

    let centers = observations.map { ($0.boundingBox.minX + $0.boundingBox.maxX) / 2.0 }
    let sorted = centers.sorted()
    var maxGap: CGFloat = 0.0
    var gapIndex = -1
    for i in 0..<(sorted.count - 1) {
        let gap = sorted[i + 1] - sorted[i]
        if gap > maxGap {
            maxGap = gap
            gapIndex = i
        }
    }

    // Require a meaningful central-ish gap and enough items on each side
    if maxGap < 0.12 { // ~12% of page width
        return [[0, 1]]
    }
    let leftCount = gapIndex + 1
    let rightCount = sorted.count - leftCount
    if leftCount < 4 || rightCount < 4 {
        return [[0, 1]]
    }

    // Split at midpoint of the biggest gap
    let split = (sorted[gapIndex] + sorted[gapIndex + 1]) / 2.0
    if split < 0.2 || split > 0.8 {
        return [[0, 1]]
    }
    return [[0, Float(split)], [Float(split), 1]]
}

func run(pdfPath: String, start: Int, end: Int?, lang: String, fast: Bool, columns: Bool) throws {
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

    let encoder = JSONEncoder()
    for pageIndex in max(0, start-1)..<min(lastPage, pageCount) {
        guard let page = doc.page(at: pageIndex) else { continue }
        let box = page.bounds(for: .mediaBox)
        let targetSize = CGSize(width: box.width, height: box.height)
        guard let img = page.thumbnail(of: targetSize, for: .mediaBox).cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }

        var columnSpans: [[Float]] = [[0, 1]]
        if columns {
            do {
                columnSpans = try detectColumns(for: img, lang: lang)
            } catch {
                columnSpans = [[0, 1]]
            }
        }

        var lines: [Line] = []
        for (colIdx, span) in columnSpans.enumerated() {
            let roi = CGRect(x: CGFloat(span[0]), y: 0, width: CGFloat(span[1] - span[0]), height: 1.0)
            recogReq.regionOfInterest = roi
            let handler = VNImageRequestHandler(cgImage: img, options: [:])
            try handler.perform([recogReq])
            if let results = recogReq.results {
                for r in results {
                    guard let cand = r.topCandidates(1).first else { continue }
                    let bb = r.boundingBox
                    // Map ROI-relative box back to full page normalized coords
                    let mapped = CGRect(
                        x: roi.origin.x + bb.origin.x * roi.size.width,
                        y: roi.origin.y + bb.origin.y * roi.size.height,
                        width: bb.size.width * roi.size.width,
                        height: bb.size.height * roi.size.height
                    )
                    let line = Line(
                        text: cand.string,
                        confidence: cand.confidence,
                        bbox: [Float(mapped.minX), Float(mapped.minY), Float(mapped.maxX), Float(mapped.maxY)],
                        column: colIdx
                    )
                    lines.append(line)
                }
            }
        }

        let pageOut = PageOut(page: pageIndex + 1, columns: columnSpans, lines: lines)
        let data = try encoder.encode(pageOut)
        if let jsonStr = String(data: data, encoding: .utf8) {
            print(jsonStr)
        }
    }
}

let args = CommandLine.arguments
guard args.count >= 4 else {
    fputs("usage: apple_helper <pdf> <start> <end_or_0> <lang> <fast 0|1> <columns 0|1>\n", stderr)
    exit(2)
}
let pdf = args[1]
let start = Int(args[2]) ?? 1
let endVal = Int(args[3]) ?? 0
let lang = args.count > 4 ? args[4] : "en-US"
let fast = args.count > 5 ? (Int(args[5]) ?? 0) != 0 : false
let columns = args.count > 6 ? (Int(args[6]) ?? 0) != 0 : false
do {
    try run(pdfPath: pdf, start: start, end: endVal == 0 ? nil : endVal, lang: lang, fast: fast, columns: columns)
} catch {
    fputs("error: \(error)\n", stderr)
    exit(1)
}
