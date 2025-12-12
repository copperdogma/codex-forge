import os
from typing import List, Tuple, Optional, Dict, Any
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
from .utils import ensure_dir


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


def run_ocr_with_word_data(
    image_path: str,
    lang: str = "eng",
    psm: int = 4,
    oem: int = 3,
    tesseract_cmd: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Run Tesseract OCR and return both text and word-level data (incl. confidences).

    Notes:
    - `pytesseract.image_to_data` returns confidences in 0..100 (or -1 for non-words).
    - Returned `data` is the raw `Output.DICT` payload from pytesseract.
    """
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    config = f"--psm {psm} --oem {oem}"
    with Image.open(image_path) as img:
        text = pytesseract.image_to_string(img, lang=lang, config=config)
        try:
            from pytesseract import Output
            data = pytesseract.image_to_data(img, lang=lang, config=config, output_type=Output.DICT)
        except Exception:
            data = {}
    return text, data
