import os
from typing import List, Tuple, Optional
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
from utils import ensure_dir


def render_pdf(pdf_path: str, out_dir: str, dpi: int = 300,
               start_page: int = 1, end_page: Optional[int] = None) -> List[str]:
    ensure_dir(out_dir)
    images = convert_from_path(pdf_path, dpi=dpi,
                               first_page=start_page,
                               last_page=end_page)
    paths = []
    for idx, img in enumerate(images, start=start_page):
        out_path = os.path.join(out_dir, f"page-{idx:03d}.jpg")
        img.save(out_path, "JPEG")
        paths.append(out_path)
    return paths


def run_ocr(image_path: str, lang: str = "eng",
            psm: int = 4, oem: int = 3,
            tesseract_cmd: Optional[str] = None) -> str:
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    config = f"--psm {psm} --oem {oem}"
    with Image.open(image_path) as img:
        text = pytesseract.image_to_string(img, lang=lang, config=config)
    return text
