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

# Some departments label the code explicitly rather than using it as a
# heading, and use a shape CODE_PATTERN does not match: NIT's Instrumentation
# curriculum runs ICIR19 and ICPC18 where Civil runs CE303. Where this label
# is present it is authoritative, since it cannot collide with a citation.
LABELLED_CODE = re.compile(
    r"^\s*Course\s+Code\s*[:\-]\s*([A-Z]{2,6}\s?\d{2,5}[A-Z]?)\b",
    re.IGNORECASE,
)

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
    # Where a document labels its codes, that is the whole answer: the label
    # cannot appear inside a reference list, so no frequency heuristic is
    # needed to tell headings from citations.
    labelled = {
        match.group(1).replace(" ", "").upper()
        for text in pages
        for line in text.split("\n")
        if (match := LABELLED_CODE.match(line))
    }
    if labelled:
        return labelled

    counts: Counter[str] = Counter()
    for text in pages:
        seen = {
            match.group(1).replace(" ", "")
            for line in text.split("\n")
            if not _is_citation(line)
            for match in CODE_PATTERN.finditer(line)
        }
        for code in seen:
            counts[code] += 1

    if not counts:
        return set()

    ceiling = max(2, int(len(pages) * MAX_CODE_FREQUENCY))
    return {code for code, n in counts.items() if 1 <= n <= ceiling}


# Lines that mention a code but are bibliography entries or standards
# references, not course headings. Left unchecked, "1. Moritz Hardt's Berkeley
# EE 227C course note" opened a course that swallowed the rest of the
# document, and IEEE1451, RS232 and MSP430 each did the same.
CITATION_MARKERS = re.compile(
    r"(^\s*\d+\s*[.)]\s)"  # numbered reference list entry
    r"|(\b(?:ed|edn|edition|vol|pp|press|publish|wiley|elsevier|springer"
    r"|mcgraw|pearson|newnes|prentice|phi|oxford|cambridge)\b)"
    r"|(\b(?:19|20)\d{2}\b\s*[.,)]?\s*$)",  # trailing year, as citations end
    re.IGNORECASE,
)

# Standards bodies and part numbers that look like course codes.
STANDARD_PREFIXES = ("IEEE", "IEC", "ISO", "RS", "ANSI", "ASTM", "BS", "EN")

LABELLED_TITLE = re.compile(r"^\s*Course\s+Title\s*[:\-]\s*(.+)$", re.IGNORECASE)


def _is_citation(line: str) -> bool:
    stripped = line.strip()
    if CITATION_MARKERS.search(stripped):
        return True
    match = CODE_PATTERN.search(stripped[:40])
    return bool(match and match.group(1).replace(" ", "").startswith(STANDARD_PREFIXES))


def _segment_page(text: str, valid: set[str]) -> list[tuple[str, str | None]]:
    """Cut a page at each course-code heading.

    Returns (segment, code) pairs in order. The first segment carries None
    when the page opens with text belonging to whichever course was already
    in progress.
    """
    lines = text.split("\n")

    # Which lines begin a new course. A heading names a known code near the
    # start of the line; a code mentioned mid-sentence is a cross-reference.
    starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        labelled = LABELLED_CODE.match(line)
        if labelled:
            code = labelled.group(1).replace(" ", "").upper()
            if code in valid:
                starts.append((index, code))
            continue

        if _is_citation(line):
            continue
        for match in CODE_PATTERN.finditer(line[:40]):
            code = match.group(1).replace(" ", "")
            if code in valid:
                starts.append((index, code))
                break

    if not starts:
        return [(text, None)]

    segments: list[tuple[str, str | None]] = []
    if starts[0][0] > 0:
        segments.append(("\n".join(lines[: starts[0][0]]), None))

    for position, (line_index, code) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        segments.append(("\n".join(lines[line_index:end]), code))

    return segments


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

        # A page that introduces a new course rarely starts with it: the
        # previous course's outcomes usually run on above the heading.
        # Assigning the whole page to the new code gave CE303 Structural
        # Analysis the sewage treatment outcomes of the course before it, so
        # the page is cut at the heading and each part filed separately.
        for segment, code in _segment_page(text, valid):
            if code and code != current:
                current = code
                courses.setdefault(current, [])

            if current and segment.strip():
                courses[current].append(segment.strip())

    return {
        code: "\n".join(chunks)
        for code, chunks in courses.items()
        if len("\n".join(chunks)) >= MIN_COURSE_CHARS
    }


def extract_title(body: str, code: str) -> str:
    """The course name usually follows the code on its first appearance."""
    # Documents that label the code label the title too. Without this the
    # label line itself matched below and every ECE course was named
    # "Course Code".
    for line in body.split("\n")[:30]:
        labelled = LABELLED_TITLE.match(line)
        if labelled:
            name = labelled.group(1).strip()
            if len(name) > 2:
                return re.sub(r"\s+", " ", name)[:70]

    for line in body.split("\n")[:30]:
        if LABELLED_CODE.match(line):
            continue
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
