import sqlite3

from creativesignal.ingest.build_corpus import build_corpus
from creativesignal.schema import Annotation, Creative


def test_creative_round_trip(sample_creative):
    creative = Creative(
        **sample_creative,
        source_type="tier3",
        category="skincare",
        date_observed="2026-01-01",
        rights_note="ad-library metadata + copy only",
    )
    assert Creative.model_validate(creative.model_dump()) == creative


def test_annotation_round_trip():
    annotation = Annotation(
        annotation_id="a_001",
        creative_id="t3_001",
        hook_type="testimonial",
        tone="aspirational",
        confidence=0.87,
        annotator="logreg",
    )
    assert Annotation.model_validate(annotation.model_dump()) == annotation


def test_build_corpus_creates_two_tables(tmp_path):
    db_path = tmp_path / "corpus.sqlite"
    build_corpus(db_path)
    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert {"creatives", "annotations"}.issubset(tables)
