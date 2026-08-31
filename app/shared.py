"""Shared UI vocabulary. Every page uses these; no page invents its own.

Keeps the AGENTS.md component rules in one place — the honesty footer is
verbatim, creative cards render identically everywhere, and no page defines
colors (that is `.streamlit/config.toml`'s job alone).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Arrow's mimalloc allocator segfaults (SIGSEGV in `mi_thread_init`) when
# pyarrow submodules are first imported inside Streamlit's script-runner
# thread — it killed the server process on the first search, with no
# traceback. Switching Arrow to the system allocator fixes it. Must be set
# before pyarrow creates its default pool. See docs/decision-log.md Entry #12.
os.environ.setdefault("ARROW_DEFAULT_MEMORY_POOL", "system")

import streamlit as st

# F4 (W6.2): Streamlit Cloud's base image ships an sqlite too old for Chroma.
# Must run before chromadb is imported anywhere, so it lives at the top of
# the shared import path rather than in one page.
try:  # pragma: no cover - deploy-environment shim
    import pysqlite3  # noqa: F401

    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ImportError:
    pass  # local dev: the system sqlite is new enough

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from creativesignal.schema import HONESTY_RULE  # noqa: E402


def page_header(title: str, caption: str) -> None:
    """`st.title` -> one-line caption. Identical skeleton on every page."""
    st.title(title)
    st.caption(caption)


def honesty_footer() -> None:
    """The verbatim honesty rule. Bottom of every page, no exceptions."""
    st.divider()
    st.caption(HONESTY_RULE)


def creative_card(result, show_scores: bool = False) -> None:
    """Render one retrieved creative: bordered container, provenance footer.

    `result` is a RetrievedCreative or anything with `.creative`.
    """
    creative = getattr(result, "creative", result)
    with st.container(border=True):
        st.markdown(f"**{creative.headline or '(no headline)'}**")
        if creative.body_copy:
            st.write(creative.body_copy)

        provenance = " · ".join(
            [
                creative.advertiser,
                creative.platform,
                creative.date_observed.isoformat(),
            ]
        )
        if creative.source_url:
            provenance += f" · [source]({creative.source_url})"
        else:
            provenance += " · no source link (synthetic corpus)"
        st.caption(f"`{creative.creative_id}` · {provenance}")

        if show_scores and hasattr(result, "score"):
            with st.expander("Why this was retrieved"):
                st.write(
                    f"Fused score **{result.score:.3f}** "
                    f"(semantic {result.semantic_score:.3f}, "
                    f"keyword {result.keyword_score:.3f})"
                )
                st.caption(
                    "Matched via: "
                    + ", ".join(result.matched_representations or ["unknown"])
                )
                st.caption(
                    "Score is retrieval similarity — a match on wording, not "
                    "evidence that this ad performed."
                )


def empty_state(message: str) -> None:
    """One helpful sentence, never a blank pane or a stack trace."""
    st.info(message)


def corpus_warning() -> None:
    """Surface the corpus gap in the product itself, not only in the docs."""
    from creativesignal.sources.curated import CuratedCorpusConnector

    try:
        creatives = CuratedCorpusConnector().all_creatives()
    except FileNotFoundError:
        st.error("No corpus found. Run `make download && make ingest` first.")
        return

    tier3 = sum(1 for c in creatives if c.source_type == "tier3")
    if tier3 == 0:
        st.warning(
            f"Corpus is {len(creatives)} synthetic Tier-2 ads with no provenance. "
            "Tier-3 curation (the real, source-linked Meta Ad Library sample) "
            "is outstanding, so retrieval quality here is not representative "
            "and no eval numbers are published. See docs/decision-log.md."
        )


def render_trace(trace) -> None:
    """W3.3: the agent's plan->tools->evidence path, collapsed by default."""
    with st.expander("How this was produced"):
        for i, step in enumerate(trace.steps, start=1):
            st.markdown(f"{i}. **{step.name}** — {step.duration_s:.2f}s")
            if step.inputs:
                st.code(
                    "\n".join(f"{k}={v!r}" for k, v in step.inputs.items()),
                    language="python",
                )
            if step.error:
                st.error(step.error)
            elif step.output_summary:
                st.caption(step.output_summary)
        for note in trace.notes:
            st.caption(f"Note: {note}")


# Reviewer severities -> the two accent colours the UI direction allows.
_FLAG_COLOR = {"claim": "red", "similarity": "orange", "info": "gray"}


def reviewer_flags(review) -> None:
    """Render reviewer flags inline on a concept, evidence on expand."""
    if review is None:
        return
    if not review.flags:
        st.caption(":green[Reviewer: no flags raised.]")
        return

    for flag in review.flags:
        color = _FLAG_COLOR.get(flag.severity, "gray")
        st.markdown(f":{color}[**{flag.severity.upper()}** — {flag.message}]")
        with st.expander("Evidence for this flag"):
            st.write(flag.evidence)
            if flag.span:
                st.caption(f"Matched text: {flag.span!r}")
            if flag.related_creative_ids:
                st.caption(f"Related: {', '.join(flag.related_creative_ids)}")


def live_mode_allowed() -> bool:
    """W6.1b: live generation is gated behind a password when deployed.

    Locally (no deploy secrets configured) live mode is simply on. On the
    deployed app it requires `st.secrets["demo_password"]`, so no
    unauthenticated visitor can spend API credits.
    """
    try:
        expected = st.secrets["demo_password"]
    except Exception:
        return True  # no deploy secrets present -> local dev

    if st.session_state.get("live_unlocked"):
        return True
    supplied = st.sidebar.text_input("Demo password", type="password")
    if supplied and supplied == expected:
        st.session_state["live_unlocked"] = True
        return True
    return False


def concept_image(concept, run_id: str = "", enabled: bool = False) -> None:
    """Render a concept's generated image, or generate it on explicit opt-in.

    Entry #33. Three states, none of which is a silent blank:
      - an image already exists  -> show it (demo mode replays with no compute)
      - generation is off        -> say nothing at all (the default; not an error)
      - generation is on         -> generate, persist, and show; on failure show
                                    why against this concept and leave the rest
                                    of the page intact.
    """
    from pathlib import Path

    from creativesignal.imagegen import (
        ImageGenerationFailed,
        ImageGenerationSkipped,
        ImageGenerationUnavailable,
        generate_image,
    )
    from creativesignal.runs import attach_image

    # The anatomy caveat is measured, not hedging: 4 of 4 sampled compositions
    # involving people or hands came back malformed, at both 1 and 4 inference
    # steps (Entry #37). Stated on every image because the failure is obvious
    # once noticed and misleading if not.
    caption = (
        "Generated locally from the concept's visual direction. A mood "
        "reference for a designer, not a finished asset — and not evidence "
        "of anything about the retrieved ads. Compositions involving people "
        "or hands are usually malformed at this quality setting; "
        "product-only framing is far more reliable."
    )

    # Already generated: replay costs nothing.
    if concept.image_path and Path(concept.image_path).exists():
        st.image(concept.image_path, use_container_width=True)
        st.caption(caption)
        return

    if not enabled:
        return

    with st.spinner(f"Generating image for {concept.title}..."):
        try:
            image = generate_image(
                concept.visual_direction,
                run_id=run_id,
                concept_title=concept.title,
                # Pre-Entry-#33 runs have no visual_direction; fall back to the
                # concept's own copy so saved runs stay generatable.
                fallback_text=f"{concept.headline}. {concept.body_copy}",
            )
        except ImageGenerationUnavailable as exc:
            st.warning(
                f"Image generation is unavailable on this machine: {exc} "
                "Everything else on this page is unaffected."
            )
            return
        except ImageGenerationSkipped as exc:
            # Not an error: the guard working as designed (Entry #38). Shown
            # as info, not a warning, so correct behaviour does not read as
            # a fault.
            st.info(str(exc))
            return
        except ImageGenerationFailed as exc:
            st.warning(f"Could not generate an image for this concept: {exc}")
            return

    if run_id:
        attach_image(run_id, concept.title, image.relative_path)

    st.image(str(image.path), use_container_width=True)
    st.caption(f"{caption} Generated in {image.latency_s:.1f}s.")


def image_generation_status() -> tuple[bool, str]:
    """Whether local image generation can run here, and why not if it can't.

    Thin pass-through so pages never import `imagegen` directly — same
    single-point-of-access rule the rest of the app follows.
    """
    from creativesignal.imagegen import is_available

    return is_available()
