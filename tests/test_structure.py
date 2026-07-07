from lit_analyzer import analyzer, segment, structure
from lit_analyzer.schemas import BeatPlan, Beat, Section, Shape, ShapeBeat


def _chaptered(n_words=60):
    body = " ".join(["the light turned and the storm broke over the reef"] * (n_words // 10))
    return f"CHAPTER I\n\n{body}\n\nCHAPTER II\n\n{body}\n\nCHAPTER III\n\n{body}\n"


# ---- schema: nesting is additive & backward compatible ----------------------

def test_beatplan_structure_defaults_none():
    plan = BeatPlan(beats=[Beat(id="eq", shape_function="f", target_words=100, pov="p", required_events=["e"], mood="m")])
    assert plan.structure is None  # flat by default — today's behavior


def test_section_nests_and_roundtrips():
    tree = Section(
        id="book",
        level="book",
        children=[
            Section(id="ch1", level="chapter", beat_ids=["eq", "fall"]),
            Section(id="ch2", level="chapter", beat_ids=["climb"]),
        ],
    )
    restored = Section.model_validate(tree.model_dump())
    assert restored == tree
    assert structure.flat_beat_ids(tree) == ["eq", "fall", "climb"]
    assert [s.id for s in structure.leaves(tree)] == ["ch1", "ch2"]


def test_shape_children_default_empty_and_nest():
    s = Shape(name="man_in_hole", beats=[ShapeBeat(id="eq", valence=0.5, function="f")])
    assert s.children == []
    book = Shape(name="book", beats=[], children=[s])
    assert Shape.model_validate(book.model_dump()) == book


# ---- segmentation -----------------------------------------------------------

def test_chapter_spans_markerless_is_single():
    spans = segment.chapter_spans("Just a plain short story with no chapter headings at all.")
    assert len(spans) == 1
    assert spans[0][0] is None


def test_chapter_spans_detects_headings():
    spans = segment.chapter_spans(_chaptered())
    titles = [t for t, _ in spans]
    assert titles == ["CHAPTER I", "CHAPTER II", "CHAPTER III"]
    assert all(body for _, body in spans)


def test_heading_length_cap_ignores_prose_starting_with_keyword():
    # A long prose line that merely starts with "book" must NOT be a heading.
    long = " ".join(["word"] * 60)
    text = f"CHAPTER I\n\n{long}\n\nbook of that description into this nowhere and studying it and making notes about it\n\n{long}"
    titles = [t for t, _ in segment.chapter_spans(text)]
    assert "CHAPTER I" in titles
    assert not any(t and t.lower().startswith("book of that") for t in titles)


def test_stave_headings_detected():
    long = " ".join(["word"] * 60)
    chs = structure.chapters(f"STAVE I: Marley\n\n{long}\n\nSTAVE II: Spirits\n\n{long}")
    assert [c[0] for c in chs] == ["ch1", "ch2"]


def test_front_matter_dropped_and_ids_sequential():
    # A short preface before the first chapter isn't a chapter; ids stay clean.
    long = " ".join(["word"] * 60)
    text = f"A short preface of only a few words.\n\nCHAPTER I\n\n{long}\n\nCHAPTER II\n\n{long}"
    tree = structure.build_structure(text)
    assert tree.level == "book"
    assert [c.id for c in tree.children] == ["ch1", "ch2"]  # sequential, preface dropped
    assert [c.title for c in tree.children] == ["CHAPTER I", "CHAPTER II"]


def test_build_structure_flat_vs_book():
    flat = structure.build_structure("no headings here, one chapter only.")
    assert flat.level == "chapter" and flat.children == []

    book = structure.build_structure(_chaptered())
    assert book.level == "book"
    assert [c.id for c in book.children] == ["ch1", "ch2", "ch3"]


# ---- analyzer integration ---------------------------------------------------

def test_short_story_is_one_node_no_section_arcs(lantern_text):
    a = analyzer.analyze(lantern_text)
    assert a.structure is not None
    assert a.structure.level == "chapter"  # one-node tree
    assert a.section_arcs == []  # flat -> no per-section arcs
    assert a.shape is not None  # whole-text arc unchanged


def test_chaptered_text_gets_tree_and_per_chapter_arcs():
    a = analyzer.analyze(_chaptered())
    assert a.structure.level == "book"
    assert len(a.structure.children) == 3
    # one arc per chapter, ids aligned with the structure
    assert [sa.section_id for sa in a.section_arcs] == ["ch1", "ch2", "ch3"]
    assert all(sa.shape.best for sa in a.section_arcs)
