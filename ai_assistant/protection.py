import re
from dataclasses import dataclass

from .exceptions import InvalidModelResponse


PLACEHOLDER_RE = re.compile(r"<x\d{4}>")

PROTECTED_PATTERNS = (
    re.compile(r"https?://[^\s<>\]\[()]+(?<![.,;:!?])", re.IGNORECASE),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b"),
    re.compile(
        r"(?<!\w)(?:MAD|DHS?|EUR|USD)\s*[-+]?\d[\d\s.,]*"
        r"|(?<!\w)[-+]?\d[\d\s.,]*\s*(?:MAD|DHS?|EUR|USD)\b"
        r"|[$€£]\s*[-+]?\d[\d\s.,]*",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/.]\d{1,2}[/.]\d{2,4})\b"),
    re.compile(r"\b(?:[A-Z]{2,}[\-_/]?\d[A-Z0-9\-_/]*|[A-Za-z]{1,8}-\d[A-Za-z0-9-]*)\b"),
    re.compile(r"(?<![\w])[-+]?\d+(?:[\s.,]\d+)*(?:\s*%)?"),
)


@dataclass(frozen=True)
class ProtectedText:
    text: str
    replacements: dict[str, str]

    def restore(self, generated_text: str) -> str:
        matches = list(PLACEHOLDER_RE.finditer(generated_text))
        found = [match.group(0) for match in matches]
        expected = set(self.replacements)
        has_marker_junk = any(
            (match.start() > 0 and generated_text[match.start() - 1] in "<>_")
            or (
                match.end() < len(generated_text)
                and generated_text[match.end()] in "<>_"
            )
            for match in matches
        )
        if set(found) != expected or len(found) != len(expected) or has_marker_junk:
            raise InvalidModelResponse(
                "La réponse IA a modifié une valeur protégée. Veuillez réessayer."
            )
        restored = generated_text
        for placeholder, original in self.replacements.items():
            restored = restored.replace(placeholder, original)
        return restored


def protect_text(text: str, known_names=()) -> ProtectedText:
    """Replace structured values and known names without ever exposing their values to edits."""
    spans = []
    for pattern in PROTECTED_PATTERNS:
        spans.extend((match.start(), match.end()) for match in pattern.finditer(text))
    for name in sorted({str(value).strip() for value in known_names if value}, key=len, reverse=True):
        if len(name) < 2:
            continue
        pattern = re.compile(rf"(?<!\w){re.escape(name)}(?!\w)", re.IGNORECASE)
        spans.extend((match.start(), match.end()) for match in pattern.finditer(text))

    selected = []
    for start, end in sorted(spans, key=lambda span: (span[0], -(span[1] - span[0]))):
        if any(start < chosen_end and end > chosen_start for chosen_start, chosen_end in selected):
            continue
        selected.append((start, end))
    selected.sort()

    replacements = {}
    parts = []
    cursor = 0
    for index, (start, end) in enumerate(selected):
        placeholder = f"<x{index:04d}>"
        parts.extend((text[cursor:start], placeholder))
        replacements[placeholder] = text[start:end]
        cursor = end
    parts.append(text[cursor:])
    return ProtectedText("".join(parts), replacements)
