import re


def extract_text(image_path):
    """Korean OCR using local Tesseract. Returns '' when OCR is unavailable."""
    try:
        import pytesseract
        from PIL import Image

        text = pytesseract.image_to_string(Image.open(image_path), lang="kor+eng")
        return re.sub(r"\s+", " ", text).strip()
    except Exception as exc:
        print(f"[OCR] skipped: {exc}")
        return ""


def match_animal(ocr_text, animals):
    """Exact animal-name inclusion is intentionally conservative to avoid wrong assignments."""
    normalized = re.sub(r"\s+", "", (ocr_text or "")).lower()
    for animal in animals:
        name = re.sub(r"\s+", "", animal["name"]).lower()
        if name and name in normalized:
            return animal["id"], f"OCR에서 '{animal['name']}' 이름 발견", 0.95
    return None, "이름을 찾지 못해 미분류", 0.0
