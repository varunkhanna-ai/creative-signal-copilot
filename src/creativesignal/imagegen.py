"""The single local image-generation wrapper. No `diffusers` use anywhere else.

Deliberately mirrors `llm.py`: one lazily-built pipeline, one public entry
point (`generate_image`), a typed result carrying what the call cost, a
`is_available()` probe so callers can degrade instead of crashing, and a CSV
cost log. The parallel is the point — a reader who understands `llm.py`
understands this module.

Runs entirely locally on Apple Silicon via PyTorch's MPS backend:
  - No API key. `ANTHROPIC_API_KEY` remains the project's only secret.
  - No per-call money cost. The cost is latency and memory, logged as such.

Rationale and measured feasibility: decision-log Entry #33, which reverses
Entry #2's "text-only, no image generation" call — that decision rested on
image generation requiring a second vendor API key, which local generation
removes.

**Not free of cost, just free of money.** ~6s and ~16GB of driver-reserved
unified memory per 1080x1080 image on the reference machine, which is why
generation is opt-in and strictly sequential (one image per call).
"""

from __future__ import annotations

import csv
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

# sd-turbo is distilled for single-step generation. At 1 step the output is a
# stylistic mood image, not a photoreal packshot — which matches what a
# `visual_direction` brief is for (Entry #33), and the UI must not imply more.
MODEL_ID = "stabilityai/sd-turbo"
IMAGE_SIZE = 1080
INFERENCE_STEPS = 1
# sd-turbo is trained for guidance_scale=0.0; any other value degrades it.
GUIDANCE_SCALE = 0.0

PROMPT_NAME = "image_prompt_v2"
IMAGE_DIR = Path("data/generated_images")
IMAGE_LOG = Path("eval/image_log.csv")

IMAGE_LOG_FIELDS = (
    "timestamp", "run_id", "concept_title", "model", "prompt_version",
    "width", "height", "steps", "latency_s", "path",
)

# CLIP's text encoder caps at 77 tokens and silently discards the tail beyond
# it. v1 budgeted only the visual_direction and ignored the style suffix
# appended after it, so every real prompt ran ~92-98 tokens and the truncated
# tail was exactly the "no text, no lettering" negative — the instruction most
# needed, dropped on every generation. The budget now covers the WHOLE
# rendered prompt, and v2's suffix is shortened so more of the direction
# survives. ~4 chars/token is the usual English rule of thumb; 260 leaves
# headroom under 77 tokens.
MAX_PROMPT_CHARS = 260


class ImageGenerationUnavailable(RuntimeError):
    """Raised when the local image stack cannot run at all.

    Distinct from a generation *failure*: this means diffusers/torch/MPS are
    missing or unusable, so no retry will help and the caller should hide or
    disable the feature rather than surface an error per concept.
    """


class ImageGenerationFailed(RuntimeError):
    """Raised when a specific generation attempt failed.

    The stack works; this one image did not. Callers should show the message
    against the affected concept and leave the rest of the page intact.
    """


class ImageGenerationSkipped(RuntimeError):
    """Raised when generation was deliberately not attempted.

    A third, distinct outcome: nothing is broken and nothing failed — the
    request was declined because it would reliably produce a bad image
    (Entry #38). Kept separate from `ImageGenerationFailed` so the UI can
    say "skipped, here's why" rather than reporting an error for correct
    behaviour.
    """


# Second-layer guard against the anatomy failure mode (Entry #37: 4 of 4
# human-subject compositions came back malformed, at both 1 and 4 steps).
# Layer one is the concept_v3 prompt, which asks for product-only framing;
# this catches the cases where the model ignores it, or where the input is an
# older run's visual_direction written under v2, or the ad-copy fallback.
#
# Matched as whole words on the visual_direction only. Word-boundary matching
# matters: substring matching would flag "skincare" for "skin" and "brand"
# for "hand", vetoing almost every legitimate product description.
HUMAN_ANATOMY_TERMS: tuple[str, ...] = (
    # people
    "person", "people", "man", "woman", "men", "women", "girl", "boy",
    "model", "models", "figure", "someone", "human", "child", "adult",
    # body parts
    "hand", "hands", "finger", "fingers", "fingertip", "fingertips",
    "face", "faces", "facial", "skin", "arm", "arms", "forearm", "wrist",
    "leg", "legs", "body", "shoulder", "shoulders", "neck", "cheek",
    "cheeks", "lip", "lips", "eye", "eyes", "eyelash", "eyelashes",
    "brow", "brows", "eyebrow", "eyebrows", "nose", "mouth", "hair",
    "palm", "palms", "knuckle", "knuckles", "nail", "nails",
    # actions that imply a person
    "applying", "apply", "touching", "touch", "holding", "hold", "massaging",
    "rubbing", "smiling", "posing", "wearing", "portrait", "selfie",
    "hands-on", "self-care",
)


# Negation cues. A direction saying "no hands or skin visible" is describing
# a product-only shot and must NOT be skipped — and concept_v3, which asks
# for no people, makes that phrasing *more* likely, not less. Real v2 output
# already contained "no hands or skin visible" on an otherwise ideal
# product flat-lay. Spans from a negation cue to the next clause boundary are
# removed before matching. See Entry #38.
_NEGATION_SPAN = r"\b(?:no|without|free of|excluding|absent|minus)\b[^,.;]*"
_HYPHEN_FREE = r"\b[a-z]+-free\b"

# Product and packaging vocabulary that reuses body-part words. Stripped
# before matching, for the same reason negations are: these are the phrases a
# *correct* product-only direction contains, and flagging them would make the
# guard fire hardest on its own best output.
#
# This is not hypothetical. "a few water droplets on the bottle's shoulder"
# came back from a real concept_v3 run and tripped on `shoulder`. Worse,
# `lip` and `eye` would veto lip balm and eye cream outright — both in-scope
# categories per Entry #22 — so every direction for them would be skipped.
_PRODUCT_PHRASES = (
    # "lip balm", "eye cream", "hand wash", "body lotion", "face serum"
    r"\b(?:lip|lips|eye|eyes|hand|hands|foot|body|face|facial|skin|hair)"
    r"[\s-]+(?:balm|cream|creme|serum|oil|wash|scrub|mask|lotion|butter|gel|"
    r"stick|tint|gloss|care|treatment|patch|patches|drops?|mist|toner|"
    r"cleanser|moisturi[sz]er|sunscreen|spf|salve|ointment)\b",
    # "the bottle's shoulder", "jar neck", "tube body"
    r"\b(?:bottle|jar|tube|vial|pump|cap|container|packaging|carton|tin)"
    r"(?:'s)?[\s-]+(?:shoulder|shoulders|neck|body|face|lip|lips|nose)\b",
    # "shoulder of the bottle"
    r"\b(?:shoulder|shoulders|neck|body|face|lip|lips|nose)\s+of\s+the\s+"
    r"(?:bottle|jar|tube|vial|pump|cap|container|carton|tin)\b",
    # ingredient / material names that collide
    r"\bpalm\s+(?:oil|butter|wax|extract)\b",
    r"\bshea\s+butter\b",
)


def find_human_subject(text: str) -> str | None:
    """Return the first human-anatomy term in `text`, or None if clean.

    Whole-word and case-insensitive, ignoring negated spans. Returns the
    matched term rather than a bool so callers can tell the user exactly what
    tripped the guard — a bare "skipped" with no reason is the kind of silent
    behaviour this project treats as a defect.
    """
    import re

    if not text:
        return None
    lowered = text.lower()
    # Drop negated spans first, so "no hands visible" reads as clean while
    # "a hand applying cream, no text" still trips on "hand".
    scannable = re.sub(_NEGATION_SPAN, " ", lowered)
    scannable = re.sub(_HYPHEN_FREE, " ", scannable)
    # Then product/packaging vocabulary, so "lip balm" and "bottle's shoulder"
    # read as the product nouns they are.
    for pattern in _PRODUCT_PHRASES:
        scannable = re.sub(pattern, " ", scannable)
    for term in HUMAN_ANATOMY_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", scannable):
            return term
    return None


@dataclass(frozen=True)
class GeneratedImage:
    """A completed generation plus what it cost — the pair the log needs."""

    path: Path
    prompt: str
    model: str
    width: int
    height: int
    steps: int
    latency_s: float

    @property
    def relative_path(self) -> str:
        """Repo-relative path, which is what gets persisted to the runs table."""
        try:
            return str(self.path.relative_to(Path.cwd()))
        except ValueError:
            return str(self.path)


def is_streamlit_cloud() -> bool:
    """True when running on Streamlit Community Cloud.

    Checked before anything else in `is_available()` because the deployed app
    must never offer this feature: the host is Linux with no MPS, `torch` and
    `diffusers` are deliberately not in `requirements.txt` (they would add
    gigabytes to a build that cannot use them), and a first call would try to
    pull ~4.8GB of weights onto an ephemeral container.

    No single official env var identifies the platform, so this checks the
    three signals it actually sets, any of which is sufficient. Erring toward
    a false positive is the safe direction — it hides a feature that would
    not have worked there anyway.
    """
    import os
    import sys

    # Deliberately NOT keyed on STREAMLIT_SERVER_HEADLESS: that is set by any
    # `streamlit run --server.headless true`, including local development,
    # and would disable the feature exactly where it works.
    if os.environ.get("STREAMLIT_SHARING_MODE"):
        return True
    if os.environ.get("HOSTNAME", "").startswith("streamlit"):
        return True
    # Cloud checks the repo out under /mount/src/<repo>.
    return any(str(p).startswith("/mount/src") for p in sys.path)


def is_available() -> tuple[bool, str]:
    """Can local generation run here? Returns (ok, human-readable reason).

    Checked in dependency order so the reason names the first real problem
    rather than a symptom of it. Never raises — this is the probe callers use
    to decide whether to offer the feature at all.
    """
    if is_streamlit_cloud():
        return False, (
            "Local image generation is disabled on the deployed app — it "
            "needs Apple Silicon (MPS) and a ~4.8GB local model. Run the app "
            "locally on a Mac to use it."
        )

    try:
        import torch
    except ImportError:
        return False, "PyTorch is not installed."

    try:
        import diffusers  # noqa: F401
    except ImportError:
        return False, "diffusers is not installed (`pip install diffusers`)."

    if not torch.backends.mps.is_available():
        # CPU generation is technically possible but takes minutes per image,
        # which is not a usable interaction — better to say so than to hang.
        return False, (
            "Apple Silicon MPS backend is unavailable. Local generation needs "
            "it; CPU-only generation is too slow to be usable here."
        )
    return True, "Local generation available (MPS)."


def build_prompt(visual_direction: str, fallback: str = "") -> str:
    """Render the versioned image prompt from a concept's visual direction.

    `visual_direction` is the intended input, but every run persisted before
    Entry #33 predates that field. Rather than refuse, fall back to the
    concept's own copy so existing runs remain generatable — the caller is
    told which was used via the returned prompt itself.
    """
    from creativesignal.llm import load_prompt

    direction = (visual_direction or "").strip() or (fallback or "").strip()
    if not direction:
        raise ImageGenerationFailed(
            "Concept has neither a visual direction nor copy to derive one "
            "from, so there is nothing to generate an image of."
        )

    template = load_prompt(PROMPT_NAME)
    # Budget the rendered prompt, not just the direction: the style suffix is
    # part of what CLIP counts, and it holds the negatives we cannot afford to
    # lose. Truncate the direction on a word boundary so the suffix always fits.
    suffix_len = len(template.format(visual_direction="").strip())
    available = max(MAX_PROMPT_CHARS - suffix_len, 40)
    if len(direction) > available:
        direction = direction[:available].rsplit(" ", 1)[0].rstrip(" ,.;:")
    return template.format(visual_direction=direction).strip()


@lru_cache(maxsize=1)
def _pipeline():
    """Build the one diffusion pipeline, lazily and once per process.

    Cached because loading costs ~30s while generation costs ~6s — reloading
    per image would dominate the interaction. Cached at module level (not per
    call) for the same single-point-of-access reason `llm.py` caches its client.
    """
    ok, reason = is_available()
    if not ok:
        raise ImageGenerationUnavailable(reason)

    import torch
    from diffusers import AutoPipelineForText2Image

    try:
        pipe = AutoPipelineForText2Image.from_pretrained(
            MODEL_ID,
            # fp32: MPS does not reliably support fp16 for this pipeline.
            torch_dtype=torch.float32,
            # Weights are public and need no token, but a first run downloads
            # ~4.8GB — surfaced to the user by the caller, not silently.
            safety_checker=None,
        )
        return pipe.to("mps")
    except Exception as exc:
        raise ImageGenerationUnavailable(
            f"Could not load the image model ({MODEL_ID}): "
            f"{type(exc).__name__}: {exc}"
        ) from exc


def unload_pipeline() -> None:
    """Drop the cached pipeline and free MPS memory.

    Worth calling on a memory-constrained machine: a 1080x1080 generation
    reserves ~16GB of unified memory, so holding the pipeline idle is not
    free. Safe to call when nothing is loaded.
    """
    _pipeline.cache_clear()
    try:
        import torch

        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
    except Exception:
        pass  # freeing memory must never be the thing that breaks a run


def log_generation(
    image: GeneratedImage,
    run_id: str = "",
    concept_title: str = "",
    path: Path = IMAGE_LOG,
) -> None:
    """Append one row to `eval/image_log.csv`.

    The analogue of `llm.py`'s cost log. There is no dollar cost to record,
    so the logged cost is latency and dimensions — which is what actually
    constrains this feature.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=IMAGE_LOG_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "run_id": run_id,
                "concept_title": concept_title,
                "model": image.model,
                "prompt_version": PROMPT_NAME,
                "width": image.width,
                "height": image.height,
                "steps": image.steps,
                "latency_s": round(image.latency_s, 3),
                "path": image.relative_path,
            }
        )


def image_path_for(run_id: str, concept_title: str, image_dir: Path = IMAGE_DIR) -> Path:
    """Deterministic on-disk location for one concept's image.

    Derived from run_id + concept title so a replayed run resolves to the same
    file without needing a lookup, and so regenerating overwrites rather than
    accumulating orphans.
    """
    slug = "".join(
        c if c.isalnum() or c in "-_" else "-" for c in concept_title.lower()
    ).strip("-")[:60] or "concept"
    return image_dir / (run_id or "unsaved") / f"{slug}.png"


def generate_image(
    visual_direction: str,
    *,
    run_id: str = "",
    concept_title: str = "",
    fallback_text: str = "",
    size: int = IMAGE_SIZE,
    image_dir: Path = IMAGE_DIR,
) -> GeneratedImage:
    """Generate one square image locally. The single entry point.

    Raises `ImageGenerationUnavailable` if the stack cannot run at all,
    `ImageGenerationSkipped` if the direction describes a human subject the
    model cannot render reliably, or `ImageGenerationFailed` if this specific
    attempt failed. Callers are expected to distinguish all three (disable
    the feature / explain the skip / flag one concept).
    """
    # Guard before the pipeline loads: a skipped request should cost nothing,
    # not 30s of model load followed by a refusal.
    source_text = (visual_direction or "").strip() or (fallback_text or "").strip()
    matched = find_human_subject(source_text)
    if matched:
        raise ImageGenerationSkipped(
            "Image generation skipped — this concept's visual direction "
            f"includes human-subject elements (matched {matched!r}), which "
            "this model cannot render reliably. Product-only framing works; "
            "see docs/decision-log.md Entry #37."
        )

    prompt = build_prompt(visual_direction, fallback=fallback_text)
    pipe = _pipeline()  # may raise ImageGenerationUnavailable

    started = time.perf_counter()
    try:
        result = pipe(
            prompt=prompt,
            num_inference_steps=INFERENCE_STEPS,
            guidance_scale=GUIDANCE_SCALE,
            height=size,
            width=size,
        )
        pil_image = result.images[0]
    except Exception as exc:
        raise ImageGenerationFailed(
            f"Image generation failed: {type(exc).__name__}: {exc}"
        ) from exc
    latency = time.perf_counter() - started

    out_path = image_path_for(run_id, concept_title, image_dir)
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pil_image.save(out_path)
    except OSError as exc:
        raise ImageGenerationFailed(
            f"Generated the image but could not save it to {out_path}: {exc}"
        ) from exc

    image = GeneratedImage(
        path=out_path,
        prompt=prompt,
        model=MODEL_ID,
        width=size,
        height=size,
        steps=INFERENCE_STEPS,
        latency_s=latency,
    )
    log_generation(image, run_id=run_id, concept_title=concept_title)
    return image
