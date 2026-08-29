"""W3.4: Phoenix tracing setup, and the in-process trace the UI renders.

Two consumers, one structure. `AgentTrace` is the source of truth: the
"How this was produced" expander renders it, and each step is also emitted as
a Phoenix span. Two renderings of one trace can never disagree; two
separately-maintained logs would.

Phoenix is optional at runtime — it runs fully local, but the app must work
if it isn't running. `setup_tracing()` degrades to a no-op.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

_TRACING_READY = False


@dataclass
class TraceStep:
    """One step: what was called, with what, what came back, how long."""

    name: str
    inputs: dict[str, Any] = field(default_factory=dict)
    output_summary: str = ""
    duration_s: float = 0.0
    error: str | None = None

    def as_line(self) -> str:
        status = f"ERROR: {self.error}" if self.error else self.output_summary
        return f"{self.name} ({self.duration_s:.2f}s) — {status}"


@dataclass
class AgentTrace:
    """The ordered record of one agent run."""

    steps: list[TraceStep] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def tool_call_count(self) -> int:
        return len(self.steps)

    def note(self, message: str) -> None:
        """A decision that wasn't a tool call — a coverage check, a bail-out."""
        self.notes.append(message)

    @contextmanager
    def step(self, name: str, **inputs: Any) -> Iterator[TraceStep]:
        """Time one step, record it, and mirror it to Phoenix if available."""
        record = TraceStep(name=name, inputs=inputs)
        started = time.perf_counter()
        try:
            yield record
        except Exception as exc:
            record.error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            record.duration_s = time.perf_counter() - started
            self.steps.append(record)
            _emit_span(record)


def _emit_span(step: TraceStep) -> None:
    """Best-effort Phoenix span. Never let telemetry break a run."""
    if not _TRACING_READY:
        return
    try:  # pragma: no cover - depends on a live collector
        from opentelemetry import trace

        tracer = trace.get_tracer("creativesignal")
        with tracer.start_as_current_span(step.name) as span:
            for key, value in step.inputs.items():
                span.set_attribute(f"input.{key}", str(value)[:500])
            span.set_attribute("output.summary", step.output_summary[:500])
            span.set_attribute("duration_s", step.duration_s)
            if step.error:
                span.set_attribute("error", step.error)
    except Exception:
        pass


def setup_tracing(project_name: str = "creativesignal") -> bool:
    """Register the Phoenix OTel exporter. Returns True if tracing is live.

    Safe to call repeatedly and safe to call with no collector running — the
    app must not depend on observability being up.
    """
    global _TRACING_READY
    if _TRACING_READY:
        return True
    try:
        from phoenix.otel import register

        register(project_name=project_name, auto_instrument=True)
        _TRACING_READY = True
    except Exception:
        _TRACING_READY = False
    return _TRACING_READY


def launch_phoenix():  # pragma: no cover - developer convenience
    """Start a local Phoenix UI. Local-only, no cloud account (§0.1)."""
    import phoenix as px

    return px.launch_app()
