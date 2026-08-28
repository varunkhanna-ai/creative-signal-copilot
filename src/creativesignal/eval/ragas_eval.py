"""W5.7: Ragas groundedness / faithfulness over generated outputs.

Scope note: Ragas covers *generation* quality — is the output supported by
the retrieved contexts. Retrieval metrics stay hand-rolled (`metrics.py`) so
every formula is explainable in an interview. One framework, one job.

The sample is drawn from the `runs` table by run_id, so the same fixed set
can be re-scored later and compared against the human rubric (W5.8) run on
identical outputs.

**Never executed.** Requires generated runs, which require an API key
(decision-log B3) and a corpus worth generating from (B2).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from creativesignal.runs import list_runs, load_run
from creativesignal.sources.curated import CuratedCorpusConnector

RESULTS_DIR = Path("eval/results")
MIN_SAMPLES = 5


@dataclass
class RagasSample:
    """One (question, answer, contexts) triple, traceable to its run."""

    run_id: str
    question: str
    answer: str
    contexts: list[str]


class InsufficientSamples(RuntimeError):
    """Raised rather than reporting a mean over one or two runs."""


def build_samples(run_ids: list[str] | None = None) -> list[RagasSample]:
    """Turn persisted runs into Ragas inputs.

    The `answer` is the concept text plus its rationale — the claims that
    must be grounded. The `contexts` are the retrieved creatives' copy, which
    is exactly what the generator was given.
    """
    runs = (
        [r for r in (load_run(rid) for rid in run_ids) if r]
        if run_ids
        else list_runs(limit=50)
    )
    source = CuratedCorpusConnector()
    samples: list[RagasSample] = []

    for run in runs:
        contexts = []
        for creative_id in run.retrieved_creative_ids:
            creative = source.get(creative_id)
            if creative:
                contexts.append(
                    f"[{creative_id}] {creative.headline or ''} "
                    f"{creative.body_copy or ''}".strip()
                )
        if not contexts:
            continue
        for concept in run.concepts:
            samples.append(
                RagasSample(
                    run_id=run.run_id,
                    question=run.brief.get("text", ""),
                    answer=f"{concept.headline} {concept.body_copy} {concept.rationale}".strip(),
                    contexts=contexts,
                )
            )
    return samples


def evaluate(samples: list[RagasSample]) -> dict:
    """Run Ragas faithfulness + answer relevancy. Requires an API key."""
    if len(samples) < MIN_SAMPLES:
        raise InsufficientSamples(
            f"{len(samples)} samples, need >= {MIN_SAMPLES}. Generate runs "
            "first (needs ANTHROPIC_API_KEY — docs/decision-log.md B3)."
        )

    from datasets import Dataset
    from ragas import evaluate as ragas_evaluate
    from ragas.metrics import answer_relevancy, faithfulness

    dataset = Dataset.from_dict(
        {
            "question": [s.question for s in samples],
            "answer": [s.answer for s in samples],
            "contexts": [s.contexts for s in samples],
        }
    )
    result = ragas_evaluate(dataset, metrics=[faithfulness, answer_relevancy])
    return {
        "n_samples": len(samples),
        "run_ids": sorted({s.run_id for s in samples}),
        "scores": {k: float(v) for k, v in result.items() if isinstance(v, (int, float))},
    }


def save_results(payload: dict, out_dir: Path = RESULTS_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "ragas_eval.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def main() -> None:
    samples = build_samples()
    print(f"{len(samples)} concept-level samples from persisted runs.")
    try:
        payload = evaluate(samples)
    except InsufficientSamples as exc:
        print(f"CANNOT RUN: {exc}")
        return
    except Exception as exc:  # missing key, ragas config, etc.
        print(f"Ragas evaluation failed: {type(exc).__name__}: {exc}")
        return
    print(json.dumps(payload["scores"], indent=2))
    print(f"\nresults -> {save_results(payload)}")
    print(
        "\nSample sizes belong next to these numbers wherever they are "
        "reported — see docs/eval-plan.md."
    )


if __name__ == "__main__":
    main()
