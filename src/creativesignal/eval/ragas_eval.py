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


def _claude_judge():
    """Wrap the project's own Claude client as Ragas's judge LLM.

    Ragas defaults to OpenAI if no `llm=` is passed — which would require a
    second vendor API key, violating "ANTHROPIC_API_KEY is the only secret"
    (AGENTS.md). Wrapping the existing key through langchain-anthropic keeps
    Ragas on the one vendor already in use.
    """
    import os

    from dotenv import load_dotenv
    from langchain_anthropic import ChatAnthropic
    from ragas.llms import LangchainLLMWrapper

    from creativesignal.llm import SONNET_MODEL, MissingAPIKeyError

    load_dotenv(override=True)  # `.env` must win over a stray shell var — see llm.py Entry #31
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise MissingAPIKeyError(
            "ANTHROPIC_API_KEY is not set — needed for Ragas's judge LLM too."
        )
    # `temperature=None` on ChatAnthropic is necessary but NOT sufficient.
    # Two separate hardcoded defaults sit between a metric's call and
    # ChatAnthropic, and both had to be found by reading actual ragas source,
    # not guessed — see decision-log Entry #30 for the full trace:
    #   1. `BaseRagasLLM.generate()` (ragas/llms/base.py) replaces an incoming
    #      `temperature=None` with a hardcoded `1e-8` BEFORE calling
    #      `agenerate_text` — so by the time `agenerate_text` runs, the value
    #      is never None, and overriding `LangchainLLMWrapper.get_temperature`
    #      (my first attempt) never fires, because that branch only triggers
    #      `if temperature is None`.
    #   2. `LangchainLLMWrapper.agenerate_text` itself then forwards whatever
    #      it received straight to `self.langchain_llm.agenerate_prompt(...,
    #      temperature=<the 1e-8>)`.
    # The only point low enough to guarantee `temperature=None` reaches
    # ChatAnthropic is `agenerate_text` itself — so it is overridden here to
    # ignore the incoming value entirely. Verified against a real API call
    # (not the constructor test alone, which is what missed layer 1).
    class _NoTemperatureWrapper(LangchainLLMWrapper):
        async def agenerate_text(self, prompt, n=1, temperature=None, stop=None, callbacks=None):
            from ragas.llms.base import is_multiple_completion_supported

            # Same branching as the original `agenerate_text` (answer_relevancy
            # calls with n=3 for its strictness parameter) — the only change
            # is forcing temperature=None instead of forwarding whatever was
            # passed in.
            if is_multiple_completion_supported(self.langchain_llm):
                return await self.langchain_llm.agenerate_prompt(
                    prompts=[prompt], n=n, temperature=None, stop=stop, callbacks=callbacks,
                )
            result = await self.langchain_llm.agenerate_prompt(
                prompts=[prompt] * n, temperature=None, stop=stop, callbacks=callbacks,
            )
            result.generations = [[g[0] for g in result.generations]]
            return result

    return _NoTemperatureWrapper(
        ChatAnthropic(model=SONNET_MODEL, api_key=key, temperature=None)
    )


def evaluate(samples: list[RagasSample]) -> dict:
    """Run Ragas faithfulness + answer relevancy, judged by Claude. Requires an API key."""
    if len(samples) < MIN_SAMPLES:
        raise InsufficientSamples(
            f"{len(samples)} samples, need >= {MIN_SAMPLES}. Generate runs "
            "first (needs ANTHROPIC_API_KEY — docs/decision-log.md B3)."
        )

    from datasets import Dataset
    from ragas import evaluate as ragas_evaluate
    from ragas.embeddings import HuggingfaceEmbeddings
    from ragas.metrics import answer_relevancy, faithfulness

    dataset = Dataset.from_dict(
        {
            "question": [s.question for s in samples],
            "answer": [s.answer for s in samples],
            "contexts": [s.contexts for s in samples],
        }
    )
    result = ragas_evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy],
        llm=_claude_judge(),
        # answer_relevancy embeds question/answer to score relevance; reuse
        # the project's own local embedding model rather than defaulting to
        # OpenAI embeddings, for the same one-vendor reason as the judge LLM.
        embeddings=HuggingfaceEmbeddings(model_name="BAAI/bge-small-en-v1.5"),
    )
    # `EvaluationResult` has no `.items()` (it is not dict-like) — its
    # aggregate per-metric scores live in `_repr_dict`, the same attribute
    # `repr()` reads. Confirmed by inspecting `EvaluationResult.__repr__`
    # rather than assumed; there is no public accessor in this ragas version.
    #
    # The aggregate mean silently drops samples the judge LLM's output failed
    # to parse (RagasOutputParserException) — a known compatibility gap
    # between Claude's output format and ragas's parser, hit on ~80% of
    # Faithfulness's NLI-statement calls in practice (decision-log Entry #30).
    # `to_pandas()` gives per-sample scores, so the real support for each
    # metric's mean is counted here explicitly rather than reported as if it
    # covered every sample.
    per_sample = result.to_pandas()
    n_scored = {
        metric: int(per_sample[metric].notna().sum())
        for metric in ("faithfulness", "answer_relevancy")
        if metric in per_sample.columns
    }
    return {
        "n_samples": len(samples),
        "n_scored": n_scored,
        "run_ids": sorted({s.run_id for s in samples}),
        "scores": {k: float(v) for k, v in result._repr_dict.items()},
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
    print(f"scored on: {payload['n_scored']} of {payload['n_samples']} samples per metric")
    print(f"\nresults -> {save_results(payload)}")
    print(
        "\nSample sizes belong next to these numbers wherever they are "
        "reported — see docs/eval-plan.md."
    )


if __name__ == "__main__":
    main()
