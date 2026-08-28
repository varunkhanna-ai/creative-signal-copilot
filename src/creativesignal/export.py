"""W4.7: export a run to Markdown. (PDF is the Section 4 stretch.)

The export is a deliverable someone forwards to a colleague, so it carries
the full honesty apparatus — coverage statement, citations with source links,
and every reviewer flag with its evidence. An export that dropped the flags
would be a nicer-looking document that misrepresents the work.
"""

from __future__ import annotations

from creativesignal.schema import HONESTY_RULE, Run


def _flag_marker(severity: str) -> str:
    return {"claim": "CLAIM", "similarity": "SIMILARITY", "info": "INFO"}.get(
        severity, severity.upper()
    )


def run_to_markdown(run: Run, source_urls: dict[str, str] | None = None) -> str:
    """Render one persisted run as a self-contained Markdown document."""
    source_urls = source_urls or {}
    lines: list[str] = []

    lines.append("# CreativeSignal — concept set")
    lines.append("")
    lines.append(f"**Run ID:** `{run.run_id}`  ")
    lines.append(f"**Generated:** {run.created_at.isoformat(timespec='seconds')}  ")
    if run.model_versions:
        versions = ", ".join(f"{k}={v}" for k, v in sorted(run.model_versions.items()))
        lines.append(f"**Models:** {versions}  ")
    if run.prompt_versions:
        prompts = ", ".join(f"{k}={v}" for k, v in sorted(run.prompt_versions.items()))
        lines.append(f"**Prompts:** {prompts}")
    lines.append("")
    lines.append(f"> {HONESTY_RULE}")
    lines.append("")

    # Brief
    lines.append("## Brief")
    lines.append("")
    for key, value in run.brief.items():
        if value:
            lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")
    lines.append("")

    # Evidence
    lines.append("## Evidence retrieved")
    lines.append("")
    if run.retrieved_creative_ids:
        for creative_id in run.retrieved_creative_ids:
            url = source_urls.get(creative_id)
            link = f" — [source]({url})" if url else " — no source link (synthetic corpus)"
            lines.append(f"- `{creative_id}`{link}")
    else:
        lines.append("- None retrieved.")
    lines.append("")

    # Trend report
    if run.trend_report:
        report = run.trend_report
        lines.append("## Trend report")
        lines.append("")
        if report.patterns:
            for pattern in report.patterns:
                cites = ", ".join(f"`{c}`" for c in pattern.cited_creative_ids)
                lines.append(
                    f"- **{pattern.description}** — {pattern.prevalence_statement}."
                    + (f" Cited: {cites}" if cites else "")
                )
        else:
            lines.append("- No prevalence patterns reported.")
        lines.append("")
        if report.counter_examples:
            lines.append("**Counter-examples**")
            lines.append("")
            for item in report.counter_examples:
                lines.append(f"- {item}")
            lines.append("")
        if report.confidence_note:
            lines.append(f"*Confidence:* {report.confidence_note}")
            lines.append("")
        lines.append(f"*{report.coverage_statement}*")
        lines.append("")

    # Concepts with their review
    lines.append("## Concepts")
    lines.append("")
    reviews = {r.concept_title: r for r in run.review_results}
    if not run.concepts:
        lines.append("No concepts passed the citation self-check.")
        lines.append("")

    for i, concept in enumerate(run.concepts, start=1):
        lines.append(f"### {i}. {concept.title}")
        lines.append("")
        if concept.hook_type:
            lines.append(f"*Hook type:* {concept.hook_type}")
            lines.append("")
        lines.append(f"**{concept.headline}**")
        lines.append("")
        lines.append(concept.body_copy)
        lines.append("")
        if concept.rationale:
            lines.append(f"*Why this concept:* {concept.rationale}")
            lines.append("")
        if concept.evidence_note:
            lines.append(f"*Evidence:* {concept.evidence_note}")
            lines.append("")
        cites = ", ".join(f"`{c}`" for c in concept.cited_creative_ids)
        lines.append(f"*Cites:* {cites or 'none'}")
        lines.append("")

        review = reviews.get(concept.title)
        if review:
            if review.flags:
                lines.append("**Reviewer flags**")
                lines.append("")
                for flag in review.flags:
                    lines.append(f"- **[{_flag_marker(flag.severity)}]** {flag.message}")
                    lines.append(f"  - *Evidence:* {flag.evidence}")
                lines.append("")
            else:
                lines.append("**Reviewer:** no flags raised.")
                lines.append("")

    if run.token_cost_usd:
        lines.append(f"*Generation cost: ${run.token_cost_usd:.4f}*")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(HONESTY_RULE)
    lines.append("")
    return "\n".join(lines)


def export_filename(run: Run) -> str:
    stamp = run.created_at.strftime("%Y%m%d-%H%M%S")
    return f"creativesignal-{stamp}-{run.run_id}.md"
