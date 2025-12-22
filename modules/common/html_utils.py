from html.parser import HTMLParser
from typing import List


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"p", "h1", "h2", "h3", "li", "tr", "dt", "dd", "caption"}:
            self.parts.append("\n")
        if tag == "img":
            alt = ""
            for k, v in attrs:
                if k == "alt":
                    alt = v or ""
                    break
            if alt:
                self.parts.append(f"\n[image: {alt}]\n")
            else:
                self.parts.append("\n[image]\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "h1", "h2", "h3", "li", "tr", "dt", "dd", "caption"}:
            self.parts.append("\n")
        if tag in {"td", "th"}:
            self.parts.append("\t")

    def handle_data(self, data: str) -> None:
        if data:
            self.parts.append(data)

    def get_text(self) -> str:
        return "".join(self.parts)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html or "")
    text = parser.get_text()
    text = text.replace("\r", "")
    lines = []
    for line in text.split("\n"):
        line = " ".join(line.split())
        if line:
            lines.append(line)
    return "\n".join(lines).strip()
