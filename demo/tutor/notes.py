"""Turn a teacher's PDFs and Word files into the plain-text notes retrieval reads.

slice/retrieve.ingest only reads .md and .txt, and rewriting it would move the
line numbers ARCHITECTURE.md points at. So conversion happens first, beside it:
each source file becomes a .md file under <folder>/.converted/, and ingest then
picks those up like any other note. Citations show the source name, e.g.
`week3.pdf.md#2`.

Known limit: PDF text has lost its line breaks by the time we see it, so code
samples inside a PDF come out as running prose. Teachers who want code shown
exactly should keep it in a .md or .docx note.
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

CONVERTED = ".converted"
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_PIECE = 500                    # target characters per paragraph we emit


def _paragraphs(text: str) -> str:
    """Give retrieval paragraph breaks to work with. Its splitter never breaks
    inside a paragraph, and a PDF page is one unbroken block of text, so a page
    would become one enormous chunk that an embedding model then truncates."""
    out = []
    for block in re.split(r"\n\s*\n", text):
        block = " ".join(block.split())
        if not block:
            continue
        piece = ""
        for sentence in re.split(r"(?<=[.!?])\s+", block):
            if piece and len(piece) + len(sentence) > _PIECE:
                out.append(piece)
                piece = ""
            piece = f"{piece} {sentence}".strip()
        if piece:
            out.append(piece)
    return "\n\n".join(out)


def _read_pdf(path: Path) -> str:
    from pypdf import PdfReader
    return "\n\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)


def _read_docx(path: Path) -> str:
    """A .docx is a zip of XML. Paragraph text is in <w:t> runs; heading styles
    become markdown headings so they survive as structure."""
    with zipfile.ZipFile(path) as z:
        root = ElementTree.fromstring(z.read("word/document.xml"))
    lines = []
    for para in root.iter(f"{_W}p"):
        text = "".join(t.text or "" for t in para.iter(f"{_W}t")).strip()
        if not text:
            continue
        style = para.find(f"{_W}pPr/{_W}pStyle")
        name = style.get(f"{_W}val", "") if style is not None else ""
        level = re.fullmatch(r"Heading([1-6])", name)
        lines.append(("#" * int(level.group(1)) + " " if level else "") + text)
    return "\n\n".join(lines)


_READERS = {".pdf": _read_pdf, ".docx": _read_docx}


def prepare(folder: str | Path) -> dict:
    """Convert every PDF and Word file under `folder` that has not been
    converted since it last changed. Never raises for a bad file: a teacher's
    upload that will not open is reported, and the rest still get taught.

    Returns {"converted": [...], "unchanged": [...], "unreadable": {name: why}}.
    """
    folder = Path(folder)
    out_dir = folder / CONVERTED
    report = {"converted": [], "unchanged": [], "unreadable": {}}
    sources = sorted(f for f in folder.rglob("*")
                     if f.suffix.lower() in _READERS and CONVERTED not in f.parts)
    for src in sources:
        dest = out_dir / f"{src.name}.md"
        if dest.exists() and dest.stat().st_mtime >= src.stat().st_mtime:
            report["unchanged"].append(src.name)
            continue
        try:
            text = _paragraphs(_READERS[src.suffix.lower()](src))
        except Exception as e:                     # corrupt, encrypted, wrong type...
            report["unreadable"][src.name] = f"{type(e).__name__}: {str(e)[:120]}"
            continue
        if not text.strip():
            report["unreadable"][src.name] = ("no text found - a scanned PDF? "
                                              "Convert it with OCR, or supply the notes as .md")
            continue
        out_dir.mkdir(exist_ok=True)
        dest.write_text(text + "\n", encoding="utf-8")
        report["converted"].append(src.name)
    return report
