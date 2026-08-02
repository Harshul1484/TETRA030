"""Split multi-course curriculum PDFs into per-course syllabus files.

Universities publish a whole degree as one document: the NIT Instrumentation
and Control curriculum is 280 pages covering four years. Feeding that in as a
single "course" produces a gap report averaged across unrelated subjects and
tells a dean nothing.

Course codes differ by institution, so the pattern is detected per document
rather than hardcoded. A page introducing a new code starts a new course.

Usage, from the repository root:

    python scripts/split_curriculum.py curriculum/ data/syllabi/
"""

import re
import sys
from collections import Counter
from pathlib import Path

import pdfplumber

# Codes look like CE209, MA202, EC15001. Two to four letters then three to
# five digits, optionally with a space or trailing letter.
CODE_PATTERN = re.compile(r"\b([A-Z]{2,4}\s?\d{3,5}[A-Z]?)\b")

# Below this a "course" is a fragment: a table of contents entry or a page
# header that happened to mention a code.
MIN_COURSE_CHARS = 900

# A code appearing this often across the document is probably a running
# header or a programme code rather than an individual course.
MAX_CODE_FREQUENCY = 0.4


def clean(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text.replace("�", "")).strip()


def detect_codes(pages: list[str]) -> set[str]:
    """Which codes in this document actually denote courses.

    Codes appearing on nearly every page are page furniture. Codes appearing
    exactly once are usually cross-references in a prerequisite table. Real
    course codes sit in between.
    """
    counts: Counter[str] = Counter()
    for text in pages:
        for code in set(CODE_PATTERN.findall(text)):
            counts[code.replace(" ", "")] += 1

    if not counts:
        return set()

    ceiling = max(2, int(len(pages) * MAX_CODE_FREQUENCY))
    return {code for code, n in counts.items() if 1 <= n <= ceiling}


def split_document(path: Path) -> dict[str, str]:
    with pdfplumber.open(path) as pdf:
        pages = [clean(page.extract_text() or "") for page in pdf.pages]

    valid = detect_codes(pages)
    if not valid:
        return {}

    courses: dict[str, list[str]] = {}
    current: str | None = None

    for text in pages:
        if not text:
            continue

        found = [
            c.replace(" ", "")
            for c in CODE_PATTERN.findall(text[:900])
            if c.replace(" ", "") in valid
        ]
        if found and found[0] != current:
            current = found[0]
            courses.setdefault(current, [])

        if current:
            courses[current].append(text)

    return {
        code: "\n".join(chunks)
        for code, chunks in courses.items()
        if len("\n".join(chunks)) >= MIN_COURSE_CHARS
    }


def extract_title(body: str, code: str) -> str:
    """The course name usually follows the code on its first appearance."""
    for line in body.split("\n")[:30]:
        if code in line.replace(" ", ""):
            candidate = re.sub(re.escape(code), " ", line.replace(" ", " "))
            candidate = re.sub(r"[^A-Za-z0-9 &-]", " ", candidate)
            words = [w for w in candidate.split() if not w.isdigit() and len(w) > 1]
            if 1 < len(words) <= 8:
                return " ".join(words)
    return "Course"


def main() -> int:
    source = Path(sys.argv[1] if len(sys.argv) > 1 else "curriculum")
    output = Path(sys.argv[2] if len(sys.argv) > 2 else "data/syllabi")
    output.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(source.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {source}")
        return 1

    written = 0
    for pdf in pdfs:
        prefix = re.sub(r"[^A-Za-z0-9]+", "-", pdf.stem).strip("-")[:24]
        try:
            courses = split_document(pdf)
        except Exception as exc:
            print(f"{pdf.name}: FAILED ({type(exc).__name__}: {exc})")
            continue

        if not courses:
            print(f"{pdf.name}: no course codes detected, skipped")
            continue

        for code, body in courses.items():
            title = extract_title(body, code)
            slug = re.sub(r"[^A-Za-z0-9]+", "_", f"{prefix}_{code}_{title}")
            path = output / f"{slug.strip('_')[:78]}.txt"
            path.write_text(body, encoding="utf-8")
            written += 1

        print(f"{pdf.name}: {len(courses)} courses extracted")

    print()
    print(f"{written} course files written to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
