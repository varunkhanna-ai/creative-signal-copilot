"""imagegen.py: prompt construction, paths, failure modes (Entry #33).

No test here loads the diffusion model — a 4.8GB download and ~6s per image
has no place in a suite that must stay fast (AGENTS.md: "Keep them fast").
What is tested is everything around the model call: prompt rendering, the
visual_direction fallback, path derivation, logging, and the two distinct
failure types. `generate_image`'s model call itself is verified by hand.
"""

from __future__ import annotations

import csv

import pytest

from creativesignal import imagegen
from creativesignal.imagegen import (
    IMAGE_SIZE,
    GeneratedImage,
    ImageGenerationFailed,
    ImageGenerationUnavailable,
    build_prompt,
    image_path_for,
    is_available,
    log_generation,
)


# --- prompt construction --------------------------------------------------


def test_prompt_uses_visual_direction():
    prompt = build_prompt("a pale stone surface with a ceramide jar")
    assert prompt.startswith("a pale stone surface with a ceramide jar")


def test_prompt_appends_the_versioned_style_suffix():
    """The style suffix lives in prompts/, not inline in code (AGENTS.md)."""
    prompt = build_prompt("a jar")
    assert "advertising product photography" in prompt
    assert "no text" in prompt  # diffusion models render text badly


def test_prompt_falls_back_when_visual_direction_is_absent():
    """Every run persisted before Entry #33 predates the visual_direction
    field, so falling back keeps those runs generatable."""
    prompt = build_prompt("", fallback="Ceramides while you sleep.")
    assert prompt.startswith("Ceramides while you sleep.")


def test_visual_direction_wins_over_the_fallback():
    prompt = build_prompt("a stone surface", fallback="some ad copy")
    assert prompt.startswith("a stone surface")
    assert "some ad copy" not in prompt


def test_whitespace_only_direction_is_treated_as_absent():
    prompt = build_prompt("   ", fallback="real copy")
    assert prompt.startswith("real copy")


def test_prompt_is_truncated_to_stay_inside_the_encoder_limit():
    """CLIP silently truncates past 77 tokens; trimming keeps it legible."""
    prompt = build_prompt("x" * 5000)
    assert len(prompt) < 5000


def test_no_usable_input_raises_a_generation_failure():
    with pytest.raises(ImageGenerationFailed, match="nothing to generate"):
        build_prompt("", fallback="")


# --- path derivation ------------------------------------------------------


def test_image_path_is_deterministic_per_run_and_concept():
    a = image_path_for("run_abc", "Ceramide Night Repair")
    b = image_path_for("run_abc", "Ceramide Night Repair")
    assert a == b, "a replayed run must resolve to the same file"


def test_image_path_slugifies_the_concept_title():
    path = image_path_for("run_abc", "Glow! Serum / 40% Off")
    assert path.suffix == ".png"
    assert "/" not in path.name
    assert "%" not in path.name


def test_image_path_separates_runs():
    assert image_path_for("run_a", "T").parent != image_path_for("run_b", "T").parent


def test_image_path_survives_an_empty_title():
    assert image_path_for("run_a", "").name == "concept.png"


def test_image_path_handles_an_unsaved_run():
    assert "unsaved" in str(image_path_for("", "Some concept"))


# --- availability probe ---------------------------------------------------


def test_is_available_returns_a_reason_either_way():
    """Callers show this string, so it must never be empty."""
    ok, reason = is_available()
    assert isinstance(ok, bool)
    assert reason.strip()


def test_is_available_reports_missing_diffusers(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "diffusers":
            raise ImportError("no diffusers")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    ok, reason = is_available()
    assert ok is False
    assert "diffusers" in reason


# --- logging --------------------------------------------------------------


def test_log_generation_writes_a_header_and_row(tmp_path):
    log = tmp_path / "image_log.csv"
    image = GeneratedImage(
        path=tmp_path / "out.png",
        prompt="a jar",
        model="stabilityai/sd-turbo",
        width=IMAGE_SIZE,
        height=IMAGE_SIZE,
        steps=1,
        latency_s=5.91,
    )
    log_generation(image, run_id="run_abc", concept_title="Ceramide", path=log)
    [row] = list(csv.DictReader(log.open(encoding="utf-8")))
    assert row["run_id"] == "run_abc"
    assert row["model"] == "stabilityai/sd-turbo"
    assert row["latency_s"] == "5.91"
    assert int(row["width"]) == IMAGE_SIZE


def test_log_generation_appends_without_duplicating_the_header(tmp_path):
    log = tmp_path / "image_log.csv"
    image = GeneratedImage(
        path=tmp_path / "o.png", prompt="p", model="m",
        width=8, height=8, steps=1, latency_s=1.0,
    )
    log_generation(image, path=log)
    log_generation(image, path=log)
    assert len(list(csv.DictReader(log.open(encoding="utf-8")))) == 2


# --- failure modes are distinguishable ------------------------------------


def test_unavailable_and_failed_are_distinct_types():
    """Callers disable the feature on one and flag a single concept on the
    other, so these must never be conflated."""
    assert not issubclass(ImageGenerationUnavailable, ImageGenerationFailed)
    assert not issubclass(ImageGenerationFailed, ImageGenerationUnavailable)


def test_generate_image_raises_unavailable_when_the_stack_is_missing(monkeypatch):
    monkeypatch.setattr(imagegen, "is_available", lambda: (False, "no MPS here"))
    imagegen._pipeline.cache_clear()
    with pytest.raises(ImageGenerationUnavailable, match="no MPS here"):
        imagegen.generate_image("a jar", run_id="r", concept_title="c")
    imagegen._pipeline.cache_clear()


def test_generate_image_wraps_a_model_error_as_failed(monkeypatch, tmp_path):
    """A broken single generation must not look like a broken install."""
    def _boom(**kwargs):
        raise RuntimeError("MPS out of memory")

    monkeypatch.setattr(imagegen, "_pipeline", lambda: _boom)
    with pytest.raises(ImageGenerationFailed, match="out of memory"):
        imagegen.generate_image(
            "a jar", run_id="r", concept_title="c", image_dir=tmp_path
        )


def test_unload_pipeline_is_safe_when_nothing_is_loaded():
    imagegen.unload_pipeline()
    imagegen.unload_pipeline()


# --- UI-facing failure handling (Entry #33) -------------------------------
# `concept_image()` is what the page actually calls, so its degradation path
# is tested here rather than only the wrapper's. A crash in it takes down the
# whole concepts section, not just one image.


def _stub_streamlit(monkeypatch):
    """Replace the streamlit surface `concept_image` touches; record calls."""
    import sys
    import types
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
    import shared

    calls = {"warning": [], "image": [], "caption": []}

    class _Spinner:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(
        shared,
        "st",
        types.SimpleNamespace(
            warning=lambda m: calls["warning"].append(m),
            image=lambda p, **k: calls["image"].append(p),
            caption=lambda m: calls["caption"].append(m),
            spinner=lambda m: _Spinner(),
        ),
    )
    return shared, calls


def _concept():
    from creativesignal.schema import Concept

    return Concept(title="T", headline="H", body_copy="B", cited_creative_ids=["c1"])


def test_ui_warns_and_survives_when_the_stack_is_unavailable(monkeypatch):
    shared, calls = _stub_streamlit(monkeypatch)
    monkeypatch.setattr(
        imagegen,
        "generate_image",
        lambda *a, **k: (_ for _ in ()).throw(ImageGenerationUnavailable("no MPS")),
    )
    shared.concept_image(_concept(), run_id="r", enabled=True)

    assert calls["warning"], "an unavailable stack must say so, not fail silently"
    assert "unaffected" in calls["warning"][-1]
    assert not calls["image"], "no image may be rendered when generation failed"


def test_ui_warns_and_survives_when_one_generation_fails(monkeypatch):
    shared, calls = _stub_streamlit(monkeypatch)
    monkeypatch.setattr(
        imagegen,
        "generate_image",
        lambda *a, **k: (_ for _ in ()).throw(ImageGenerationFailed("MPS OOM")),
    )
    shared.concept_image(_concept(), run_id="r", enabled=True)

    assert "MPS OOM" in calls["warning"][-1], "the reason must reach the user"
    assert not calls["image"]


def test_ui_renders_nothing_at_all_when_disabled(monkeypatch):
    """Off is the default. It must be silent — not an error, not a blank space."""
    shared, calls = _stub_streamlit(monkeypatch)
    shared.concept_image(_concept(), run_id="r", enabled=False)
    assert not calls["warning"] and not calls["image"] and not calls["caption"]


def test_whole_rendered_prompt_stays_within_the_clip_budget():
    """Regression: v1 budgeted only the direction, not the style suffix.

    Real visual_direction text (~250 chars) plus v1's 134-char suffix ran
    ~92-98 tokens against CLIP's 77-token cap, and the silently-discarded
    tail was exactly the "no text, no lettering" negative.
    """
    from creativesignal.imagegen import MAX_PROMPT_CHARS

    realistic = (
        "Close-up macro shot of a fingertip pressing into bare skin on a "
        "forearm in soft, cool daylight, with a faint visible texture of "
        "dry/flaky skin on one side of frame and smoother skin on the other, "
        "muted winter-blue and skin-tone palette, clinical but warm mood."
    )
    prompt = build_prompt(realistic)
    assert len(prompt) <= MAX_PROMPT_CHARS


def test_the_no_text_negative_always_survives_truncation():
    """The suffix carries the instruction we can least afford to lose."""
    prompt = build_prompt("a jar " * 400)
    assert prompt.endswith("no text, no lettering")


def test_truncation_breaks_on_a_word_boundary():
    prompt = build_prompt("supercalifragilistic " * 60)
    assert "supercalifragilisti," not in prompt  # no mid-word cut
