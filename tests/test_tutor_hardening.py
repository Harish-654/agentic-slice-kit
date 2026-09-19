"""Phase 2: the tutor remembers, forgets, and reads the teacher's own files."""
import time
import zipfile

from demo.tutor import learner, learners, notes, session
from demo.tutor.flow import build_flow
from demo.tutor.schema import LearnerModel
from demo.tutor.stub import Stub, grade, lesson, open_lesson
from slice import runner
from slice.records import RunState
from slice.retrieve import Chunk, split
from slice.store import Store
from tests.test_tutor import NOTES, S, answer, drive, find

DAY = 86400.0


def test_a_belief_from_an_earlier_session_shapes_the_first_lesson(tmp_path):
    store = Store(tmp_path / "r.db")
    old = session.start_session(store, "s1", ["mutable-defaults"])
    stub = Stub({"teach": [lesson("a"), lesson("b")]})
    drive(store, old, stub)
    answer(store, old, 0)                                   # default-is-copied
    drive(store, old, stub)

    new = session.start_session(store, "s1", ["mutable-defaults", "is-vs-equals"])
    fresh = Stub({"teach": [lesson("c")]})
    drive(store, new, fresh)

    first = store.history(new, "lesson")[0].payload
    assert first["concept"] == "mutable-defaults" and first["style"] == "analogy"
    prompt = fresh.messages[0][1]["content"]
    assert "held in an earlier session" in prompt and "default-is-copied" in prompt


def test_a_belief_chosen_this_session_is_worded_as_just_chosen(tmp_path):
    store = Store(tmp_path / "r.db")
    run = session.start_session(store, "s1", ["mutable-defaults"])
    stub = Stub({"teach": [lesson("a"), lesson("b")]})
    drive(store, run, stub)
    answer(store, run, 0)
    drive(store, run, stub)
    assert "the student just chose: default-is-copied" in stub.messages[1][1]["content"]


def test_a_concept_with_no_history_still_starts_plain(tmp_path):
    store = Store(tmp_path / "r.db")
    run = session.start_session(store, "new-student", ["mutable-defaults"])
    drive(store, run, Stub({"teach": [lesson("a")]}))
    assert store.history(run, "lesson")[0].payload["style"] == "plain"


def test_a_wrong_answer_the_grader_could_not_name_still_counts(tmp_path):
    store = Store(tmp_path / "r.db")
    run = session.start_session(store, "s1", ["mutable-defaults"])
    session.set_answer_mode(store, run, "text")
    stub = Stub({"teach": [open_lesson("a"), open_lesson("b")], "grade": [grade(False, None, "no")]})
    drive(store, run, stub)
    session.submit_text(store, session.open_quiz(store, run).id, "dunno")
    drive(store, run, stub)
    assert store.history(run, "lesson")[1].payload["style"] == "analogy"


def test_each_student_has_their_own_row_however_many_runs_pile_up(tmp_path):
    store = Store(tmp_path / "r.db")
    session.start_session(store, "asha", ["x"], interests=["football"])
    for i in range(250):                                   # more than the old 200-run scan saw
        session.start_session(store, f"other-{i}", ["x"])
    session.start_session(store, "ravi", ["x"], interests=["chess"])

    assert session.previous_model(store, "asha").interests == ["football"]
    assert session.previous_model(store, "ravi").interests == ["chess"]


def test_a_database_from_before_the_table_still_loads(tmp_path):
    store = Store(tmp_path / "r.db")
    run = store.create_run(session.DOMAIN, {"student_id": "old-timer"})
    m = LearnerModel(student_id="old-timer", interests=["cricket"])
    store.append(run, "learner_model", m.model_dump(), "system")
    assert learners.load(store, "old-timer") is None       # no row yet
    assert session.previous_model(store, "old-timer").interests == ["cricket"]


def test_a_mastered_concept_comes_due_for_review_but_stored_mastery_is_untouched():
    now = 1_000_000_000.0
    m = LearnerModel(student_id="s", mastery={"a": 0.9}, last_seen={"a": now - 1 * DAY})
    assert learner.pick_concept(m, ["a"], now) is None                     # fresh: mastered

    later = now + 30 * DAY
    assert learner.effective_mastery(m, "a", later) < learner.MASTERY
    assert learner.pick_concept(m, ["a"], later) == "a"                    # due for review
    assert learner.effective_mastery(m, "a", later) > learner.START        # still above zero
    assert m.mastery["a"] == 0.9                                           # nothing rewritten


def test_a_review_starts_from_what_they_know_now_not_their_peak():
    now = 1_000_000_000.0
    m = LearnerModel(student_id="s", mastery={"a": 0.9}, last_seen={"a": now - 60 * DAY})
    after = learner.apply_check(m, "a", correct=False, misconception=None, now=now)
    assert after.mastery["a"] < 0.2                        # halved from ~0.3, not from 0.9


# ------------------------------------------------------------ teacher's files

def _docx(path, paragraphs):
    ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    body = "".join(
        f'<w:p>{"<w:pPr><w:pStyle w:val=\"Heading1\"/></w:pPr>" if h else ""}'
        f'<w:r><w:t>{t}</w:t></w:r></w:p>' for h, t in paragraphs)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", f"<w:document {ns}><w:body>{body}</w:body></w:document>")


def _pdf(path, text):
    stream = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET"
    path.write_bytes((
        "%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        "2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        "3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 200]/Contents 4 0 R"
        "/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
        f"4 0 obj<</Length {len(stream)}>>stream\n{stream}\nendstream endobj\n"
        "5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
        "trailer<</Root 1 0 R/Size 6>>\nstartxref\n0\n%%EOF\n").encode())


def test_a_word_file_becomes_a_note_with_its_headings(tmp_path):
    _docx(tmp_path / "week1.docx", [(True, "Loops"), (False, "A for loop repeats a block.")])
    report = notes.prepare(tmp_path)
    assert report["converted"] == ["week1.docx"]
    text = (tmp_path / ".converted" / "week1.docx.md").read_text()
    assert text.startswith("# Loops") and "A for loop repeats a block." in text


def test_a_pdf_becomes_a_note(tmp_path):
    _pdf(tmp_path / "week2.pdf", "Slices exclude the stop index.")
    report = notes.prepare(tmp_path)
    assert report["converted"] == ["week2.pdf"], report
    assert "Slices exclude the stop index." in (tmp_path / ".converted" / "week2.pdf.md").read_text()


def test_unchanged_files_are_not_converted_again_and_bad_ones_do_not_stop_the_rest(tmp_path):
    _docx(tmp_path / "ok.docx", [(False, "Fine.")])
    (tmp_path / "broken.docx").write_bytes(b"not a zip at all")
    (tmp_path / "broken.pdf").write_bytes(b"%PDF-1.4 garbage")

    first = notes.prepare(tmp_path)
    assert first["converted"] == ["ok.docx"]
    assert set(first["unreadable"]) == {"broken.docx", "broken.pdf"}

    second = notes.prepare(tmp_path)
    assert second["converted"] == [] and second["unchanged"] == ["ok.docx"]


def test_a_pdf_page_is_regrouped_so_retrieval_gets_real_chunks(tmp_path):
    long_page = " ".join(f"Sentence number {i} explains something about lists." for i in range(60))
    assert len(split(long_page)) == 1                       # what retrieval alone would do
    regrouped = notes._paragraphs(long_page)
    assert len(split(regrouped)) > 2
