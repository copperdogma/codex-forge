import argparse
import json
from pathlib import Path
from typing import Dict, Type
from pydantic import BaseModel, ValidationError

from modules.common.utils import read_jsonl
from schemas import (
    ChapterHtmlManifestEntry,
    SectionBoundary,
    PortionHypothesis,
    LockedPortion,
    ResolvedPortion,
    EnrichedPortion,
    PageDoc,
    CleanPage,
    RunInstrumentation,
    StageInstrumentation,
    LLMCallUsage,
    ImageCrop,
    ContactSheetTile,
    IntakePlan,
    PageLines,
    PageImage,
    PageHtml,
    PageHtmlBlocks,
    PipelineIssues,
    EdgecaseScanReport,
    EdgecasePatchRecord,
    EdgecasePatchReport,
    TurnToLinksRecord,
    TurnToLinkClaim,
    TurnToUnclaimedReport,
    ElementCore,
    DocWebBundleManifest,
    DocWebProvenanceBlock,
)


SCHEMA_MAP: Dict[str, Type[BaseModel]] = {
    "chapter_html_manifest_v1": ChapterHtmlManifestEntry,
    "page_doc_v1": PageDoc,
    "clean_page_v1": CleanPage,
    "section_boundary_v1": SectionBoundary,
    "portion_hyp_v1": PortionHypothesis,
    "locked_portion_v1": LockedPortion,
    "resolved_portion_v1": ResolvedPortion,
    "enriched_portion_v1": EnrichedPortion,
    "instrumentation_run_v1": RunInstrumentation,
    "instrumentation_stage_v1": StageInstrumentation,
    "instrumentation_call_v1": LLMCallUsage,
    "image_crop_v1": ImageCrop,
    "contact_sheet_manifest_v1": ContactSheetTile,
    "intake_plan_v1": IntakePlan,
    "pagelines_v1": PageLines,
    "page_image_v1": PageImage,
    "page_html_v1": PageHtml,
    "page_html_blocks_v1": PageHtmlBlocks,
    "pipeline_issues_v1": PipelineIssues,
    "edgecase_scan_v1": EdgecaseScanReport,
    "edgecase_patch_v1": EdgecasePatchRecord,
    "edgecase_patch_report_v1": EdgecasePatchReport,
    "turn_to_links_v1": TurnToLinksRecord,
    "turn_to_link_claims_v1": TurnToLinkClaim,
    "turn_to_unclaimed_v1": TurnToUnclaimedReport,
    "element_core_v1": ElementCore,
    "doc_web_bundle_manifest_v1": DocWebBundleManifest,
    "doc_web_provenance_block_v1": DocWebProvenanceBlock,
}


def _iter_artifact_rows(path: str):
    artifact_path = Path(path)
    if artifact_path.suffix.lower() == ".json":
        with artifact_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            for row in data:
                yield row
        else:
            yield data
        return
    yield from read_jsonl(path)


def main():
    parser = argparse.ArgumentParser(description="Validate artifact JSON or JSONL against schema.")
    parser.add_argument("--schema", required=True, choices=SCHEMA_MAP.keys())
    parser.add_argument("--file", required=True, help="Path to JSON or JSONL artifact")
    args = parser.parse_args()

    model_cls = SCHEMA_MAP[args.schema]
    total = 0
    errors = 0
    for row in _iter_artifact_rows(args.file):
        total += 1
        try:
            model_cls(**row)
        except ValidationError as e:
            errors += 1
            print(f"[ERROR] row {total}: {e}")

    if errors:
        print(f"Validation finished with {errors} errors out of {total} rows.")
        raise SystemExit(1)
    else:
        print(f"Validation OK: {total} rows match {args.schema}")


if __name__ == "__main__":
    main()
