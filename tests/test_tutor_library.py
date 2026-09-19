"""A student's own documents: saved, scoped to them, searched, removed. Real retrieval."""
import zipfile

import pytest

from demo.tutor import library
from slice.store import Store


@pytest.fixture
def lib(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "ROOT", tmp_path / "uploads")
    return Store(tmp_path / "r.db")


SLICES = b"# List slicing\n\nAn index starts at 0. A slice items[1:3] excludes the stop index.\n"
BAKING = b"# Bread\n\nMix flour, water, yeast and salt. Let the dough rise before baking the loaf.\n"


def test_a_student_only_ever_finds_their_own_documents(lib):
    library.save(lib, "Asha", "slicing.md", SLICES)
    library.save(lib, "Ravi", "bread.md", BAKING)

    assert library.docs("Asha") == ["slicing.md"] and library.docs("Ravi") == ["bread.md"]
    mine = library.search(lib, "Asha", "list slicing")
    assert mine and {c.doc for c in mine} == {"asha__slicing.md"}
    assert library.search(lib, "Ravi", "list slicing") == []          # Asha's notes never reach Ravi
    assert library.search(lib, "Asha", "how to bake bread") == []     # and are not stretched to fit


def test_a_topic_the_documents_do_not_cover_finds_nothing(lib):
    library.add_sample(lib, "Asha")
    assert library.search(lib, "Asha", "mutable default arguments")
    assert library.search(lib, "Asha", "photosynthesis") == []        # the cutoff at work


def test_the_sample_notes_are_added_in_one_call(lib):
    assert library.add_sample(lib, "Asha") == ["is-vs-equals.md", "list-slicing.md", "mutable-defaults.md"]


def test_removing_a_document_removes_what_was_indexed_from_it(lib):
    library.save(lib, "Asha", "slicing.md", SLICES)
    assert library.search(lib, "Asha", "list slicing")
    library.delete(lib, "Asha", "slicing.md")
    assert library.docs("Asha") == [] and library.search(lib, "Asha", "list slicing") == []


def test_only_readable_kinds_of_file_are_accepted(lib):
    with pytest.raises(library.Rejected, match="only"):
        library.save(lib, "Asha", "malware.exe", b"MZ")
    with pytest.raises(library.Rejected, match="MB"):
        library.save(lib, "Asha", "big.md", b"x" * (library.MAX_BYTES + 1))
    assert library.docs("Asha") == []


def test_a_student_can_keep_a_limited_number_of_documents(lib, monkeypatch):
    monkeypatch.setattr(library, "MAX_FILES", 2)
    library.save(lib, "Asha", "a.md", SLICES)
    library.save(lib, "Asha", "b.md", BAKING)
    with pytest.raises(library.Rejected, match="up to 2"):
        library.save(lib, "Asha", "c.md", SLICES)
    library.save(lib, "Asha", "a.md", SLICES)                          # replacing one is fine


def test_a_filename_cannot_reach_outside_the_students_folder(lib, tmp_path):
    for evil in ("../../escape.md", "..\\..\\escape.md", "/etc/cron.d/x.md", ".hidden.md"):
        name = library.save(lib, "Asha", evil, SLICES)
        assert "/" not in name and "\\" not in name and not name.startswith(".")
    written = {p for p in (tmp_path / "uploads").rglob("*") if p.is_file()}
    assert all((tmp_path / "uploads" / "asha") in p.parents for p in written)
    assert not (tmp_path / "escape.md").exists()


def test_a_word_document_is_converted_and_searchable(lib, tmp_path):
    ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    docx = tmp_path / "d.docx"
    with zipfile.ZipFile(docx, "w") as z:
        z.writestr("word/document.xml", f"<w:document {ns}><w:body><w:p><w:r><w:t>"
                   "A slice items[1:3] excludes the stop index of a list.</w:t></w:r></w:p></w:body></w:document>")
    library.save(lib, "Asha", "week1.docx", docx.read_bytes())
    assert library.docs("Asha") == ["week1.docx"]
    assert library.search(lib, "Asha", "list slicing")
    library.delete(lib, "Asha", "week1.docx")
    assert library.search(lib, "Asha", "list slicing") == []          # the converted copy went too


def test_a_file_that_cannot_be_read_is_refused_and_not_left_behind(lib):
    with pytest.raises(library.Rejected, match="could not be read"):
        library.save(lib, "Asha", "broken.docx", b"not a zip at all")
    assert library.docs("Asha") == []


def test_an_unpacked_word_file_that_is_absurdly_large_is_refused(lib, tmp_path, monkeypatch):
    from demo.tutor import notes
    monkeypatch.setattr(notes, "_MAX_XML", 50)
    docx = tmp_path / "bomb.docx"
    with zipfile.ZipFile(docx, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", "<w:document xmlns:w='x'>" + "a" * 500 + "</w:document>")
    with pytest.raises(library.Rejected, match="too large"):
        library.save(lib, "Asha", "bomb.docx", docx.read_bytes())
