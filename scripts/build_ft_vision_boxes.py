"""Create GPT-4o vision fine-tune training file from GT boxes.

Input: GT JSONL with fields page,image,boxes (configs/groundtruth/image_boxes_eval.jsonl)
Output: JSONL for FT where each example has messages: system prompt + user image + expected JSON boxes.
"""
import argparse, json
from pathlib import Path

import base64

SYSTEM = "You are an expert illustration detector. Return JSON boxes for illustrations only."

USER_PROMPT = "Find all illustrations in this page image and return bounding boxes as JSON: {\"boxes\": [{\"x0\":int,\"y0\":int,\"x1\":int,\"y1\":int}]}"


def encode_image(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gt', default='configs/groundtruth/image_boxes_eval.jsonl')
    ap.add_argument('--out', default='output/ft/image_boxes_train.jsonl')
    ap.add_argument('--images-root', default='input/images')
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(args.gt) as f, open(out_path, 'w') as out:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            boxes = rec.get('boxes', [])
            expected = {"boxes": [{"x0": b['x0'], "y0": b['y0'], "x1": b['x1'], "y1": b['y1']} for b in boxes]}
            image_b64 = encode_image(Path(args.images_root)/rec['image'])
            example = {
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": USER_PROMPT},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}", "detail": "low"}},
                        ],
                    },
                    {"role": "assistant", "content": json.dumps(expected)},
                ]
            }
            out.write(json.dumps(example) + "\n")
    print(f"Wrote FT file {out_path}")


if __name__ == '__main__':
    main()
