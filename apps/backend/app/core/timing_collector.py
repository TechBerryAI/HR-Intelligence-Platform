"""
In-memory timing session store for Developer Mode.

Inactive when DEVELOPER_MODE is off — record() is a no-op.
No database; bounded ring buffer to avoid production memory pressure.
"""
from __future__ import annotations

import statistics
import threading
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.developer_mode import developer_mode_max_sessions, is_developer_mode_enabled

# Engine stage key -> display name (matches Document Intelligence pipeline)
ENGINE_STEP_LABELS: dict[str, str] = {
    "cache": "Cache Check",
    "persist_raw": "Store Raw File",
    "text": "Extract Text",
    "layout": "Layout Analysis",
    "sections": "Section Detection",
    "deterministic": "Deterministic Parse",
    "knowledge": "Knowledge Enrichment",
    "coverage": "Coverage Check",
    "semantic": "Semantic Enrichment (LLM)",
    "validate": "Validation",
    "persist": "Save Parsed Result",
}

# Full ordered checklists — every step always shown on the dashboard
RESUME_PIPELINE_STEPS: tuple[tuple[str, str], ...] = (
    ("cache", "Cache Check"),
    ("persist_raw", "Store Raw File"),
    ("text", "Extract Text"),
    ("layout", "Layout Analysis"),
    ("sections", "Section Detection"),
    ("deterministic", "Deterministic Parse"),
    ("semantic", "Semantic Enrichment (LLM)"),
    ("knowledge", "Knowledge Enrichment"),
    ("validate", "Validation"),
    ("persist", "Save Parsed Result"),
)

JD_PIPELINE_STEPS: tuple[tuple[str, str], ...] = (
    ("cache", "Cache Check"),
    ("persist_raw", "Store Raw File"),
    ("text", "Extract Text"),
    ("layout", "Layout Analysis"),
    ("sections", "Section Detection"),
    ("deterministic", "Deterministic Parse"),
    ("knowledge", "Knowledge Enrichment"),
    ("coverage", "Coverage Check"),
    ("semantic", "Semantic Enrichment (LLM)"),
    ("validate", "Validation"),
    ("persist", "Save Parsed Result"),
)

# Public apply submit checklist (parse already done client-side before submit)
APPLY_PIPELINE_STEPS: tuple[tuple[str, str], ...] = (
    ("validate", "Validate Payload"),
    ("upsert_candidate", "Create Candidate"),
    ("save_profile", "Save Profile"),
    ("link_resume", "Link Parsed Resume"),
    ("load_jd", "Load Job Description"),
    ("ats_match", "ATS Matching"),
    ("persist", "Database Save"),
)

APPLY_STEP_LABELS: dict[str, str] = {k: v for k, v in APPLY_PIPELINE_STEPS}
APPLY_STAGES: frozenset[str] = frozenset(APPLY_STEP_LABELS.keys())

# Display / classification helpers — product labels for timed functions + DI stages
STAGE_LABELS: dict[str, str] = {
    **{k: v for k, v in ENGINE_STEP_LABELS.items()},
    **APPLY_STEP_LABELS,
    "extract_text": "Extract Text",
    "parse_via_runtime": "LLM Inference (AI Runtime)",
    "_call_section_llm": "LLM Call (Semantic)",
    "enrich_resume_semantic": "Semantic Enrichment (LLM)",
    "enrich_jd_semantic": "Semantic Enrichment (LLM)",
    "store_raw_file": "Store Raw File",
    "run_document_intelligence": "Document Intelligence (total)",
    "_run_resume": "Resume Parsing (total)",
    "_run_jd": "JD Parsing (total)",
    "match_candidate_to_job": "ATS Matching",
    "_internal_match": "ATS Score Computation",
    "_optional_llm_narrative": "ATS Narrative (LLM)",
    "_persist_application_atomic": "Database Save",
    "public_apply_to_job": "Public Apply (total)",
}

# Canonical order for mixed timelines
PIPELINE_ORDER: tuple[str, ...] = tuple(
    dict.fromkeys(
        [name for _, name in RESUME_PIPELINE_STEPS]
        + [name for _, name in JD_PIPELINE_STEPS]
        + [name for _, name in APPLY_PIPELINE_STEPS]
        + [
            "LLM Call (Semantic)",
            "LLM Inference (AI Runtime)",
            "Resume Parsing (total)",
            "JD Parsing (total)",
            "Document Intelligence (total)",
            "ATS Matching",
            "ATS Matching (total)",
            "ATS Score Computation",
            "ATS Narrative (LLM)",
            "Database Save",
            "Public Apply (total)",
        ]
    )
)

WRAPPER_STAGES: frozenset[str] = frozenset(
    {
        "Resume Parsing (total)",
        "JD Parsing (total)",
        "Document Intelligence (total)",
        "Public Apply (total)",
        "ATS Matching",
        "ATS Matching (total)",
    }
)

STAGE_GROUP: dict[str, str] = {
    **{name: "Parsing" for _, name in RESUME_PIPELINE_STEPS},
    **{name: "Parsing" for _, name in JD_PIPELINE_STEPS},
    **{name: "Apply" for _, name in APPLY_PIPELINE_STEPS},
    "Semantic Enrichment (LLM)": "LLM",
    "LLM Call (Semantic)": "LLM",
    "LLM Inference (AI Runtime)": "LLM",
    "ATS Narrative (LLM)": "LLM",
    "ATS Matching": "ATS Matching",
    "ATS Matching (total)": "ATS Matching",
    "ATS Score Computation": "ATS Matching",
    "Database Save": "Persist",
    "Public Apply (total)": "Apply",
    "Resume Parsing (total)": "Parsing",
    "JD Parsing (total)": "Parsing",
    "Document Intelligence (total)": "Parsing",
}

LLM_FUNCTIONS: frozenset[str] = frozenset(
    {
        "parse_via_runtime",
        "_call_section_llm",
        "enrich_resume_semantic",
        "enrich_jd_semantic",
        "_optional_llm_narrative",
        "semantic",
    }
)

KIND_MARKERS: dict[str, tuple[str, ...]] = {
    "resume_parse": ("_run_resume", "enrich_resume_semantic", "run_document_intelligence", "text", "deterministic"),
    "jd_parse": ("_run_jd", "enrich_jd_semantic", "text", "deterministic", "coverage"),
    "bulk_parse": ("text", "deterministic", "sections", "extract_text", "parse_resume_text_via_engine"),
    "ats": ("match_candidate_to_job", "_internal_match"),
    "apply": ("public_apply_to_job", "_persist_application_atomic"),
}

ENGINE_STAGES: frozenset[str] = frozenset(ENGINE_STEP_LABELS.keys())

# Map alternate @timing function names onto checklist keys
FUNCTION_TO_STEP_KEY: dict[str, str] = {
    "extract_text": "text",
    "store_raw_file": "persist_raw",
    "enrich_resume_semantic": "semantic",
    "enrich_jd_semantic": "semantic",
    "_call_section_llm": "semantic",
    "parse_via_runtime": "semantic",
    # Apply submit
    "match_candidate_to_job": "ats_match",
    "_persist_application_atomic": "persist",
}



@dataclass
class TimingEvent:
    request_id: str
    timestamp: str
    function: str
    module: str
    duration_ms: float
    success: bool
    exception_name: Optional[str] = None
    user_id: Optional[str] = None
    candidate_id: Optional[str] = None
    job_id: Optional[str] = None
    depth: int = 0
    stage: str = ""
    outcome: str = "completed"  # completed | failed | skipped

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TimingSession:
    request_id: str
    started_at: str
    path: str = ""
    method: str = ""
    user_id: Optional[str] = None
    candidate_id: Optional[str] = None
    job_id: Optional[str] = None
    status: str = "ok"  # ok | error
    total_duration_ms: float = 0.0
    kind: str = "other"
    events: list[TimingEvent] = field(default_factory=list)
    finished_at: Optional[str] = None

    def to_summary(self) -> dict[str, Any]:
        # Re-resolve so path-based bulk vs single resume stays accurate in filters
        kind = _classify_session(self)
        return {
            "request_id": self.request_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "path": self.path,
            "method": self.method,
            "user_id": self.user_id,
            "candidate_id": self.candidate_id,
            "job_id": self.job_id,
            "status": self.status,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "kind": kind,
            "event_count": len(self.events),
            "stages": self.stage_timeline(),
            "is_bulk_group": False,
            "resume_count": None,
        }

    def to_detail(self) -> dict[str, Any]:
        data = self.to_summary()
        data["events"] = [e.to_dict() for e in self.events]
        data["timeline"] = self.pipeline_timeline()
        data["functions"] = self.function_details()
        data["breakdown"] = self.category_breakdown()
        data["parse_steps"] = self.parse_checklist()
        return data

    def parse_checklist(self) -> list[dict[str, Any]]:
        """
        Full resume/JD/apply step list with timing for every stage.

        Always returns every canonical step so the UI can show:
        Cache Check … 12 ms, Semantic Enrichment … skipped, etc.
        """
        kind = (
            self.kind
            if self.kind in ("resume_parse", "jd_parse", "bulk_parse", "apply")
            else _classify_session(self)
        )
        path = (self.path or "").lower()
        names = {e.function for e in self.events}

        # Prefer path / function signals so resume never accidentally uses JD list
        if "public_apply_to_job" in names or "/apply" in path:
            kind = "apply"
        elif "/bulk-parse" in path or "bulk_parse" in path:
            kind = "bulk_parse"
        elif "/parse/jd" in path or "_run_jd" in names or "enrich_jd_semantic" in names:
            kind = "jd_parse"
        elif (
            "/parse/resume" in path
            or "_run_resume" in names
            or "enrich_resume_semantic" in names
        ):
            kind = "resume_parse"
        elif kind not in ("resume_parse", "jd_parse", "bulk_parse", "apply"):
            if "coverage" in names:
                kind = "jd_parse"
            elif names & ENGINE_STAGES or names & set(FUNCTION_TO_STEP_KEY):
                kind = "resume_parse"
            else:
                return []

        if kind == "apply":
            return self._apply_checklist()

        # Bulk resume uses the same step checklist as single-file resume parse
        template = JD_PIPELINE_STEPS if kind == "jd_parse" else RESUME_PIPELINE_STEPS
        allowed_keys = ENGINE_STAGES

        # Best event per engine key
        by_key: dict[str, TimingEvent] = {}
        for ev in self.events:
            key = ev.function
            if key in FUNCTION_TO_STEP_KEY:
                mapped = FUNCTION_TO_STEP_KEY[key]
                # Keep engine-stage event preferred over aliased @timing
                if key in allowed_keys:
                    pass  # key already engine stage
                else:
                    key = mapped
            if key not in allowed_keys:
                continue
            prev = by_key.get(key)
            if prev is None:
                by_key[key] = ev
            elif ev.function in allowed_keys and prev.function not in allowed_keys:
                by_key[key] = ev
            elif prev.function in allowed_keys and ev.function not in allowed_keys:
                # Keep engine-stage row; only replace if aliased timing is clearly longer
                if ev.duration_ms > prev.duration_ms and prev.duration_ms <= 0:
                    by_key[key] = ev
            elif ev.duration_ms > prev.duration_ms:
                # Prefer the longer measured duration (avoids a later 0ms double-complete winning)
                by_key[key] = ev
            elif (
                ev.duration_ms == prev.duration_ms
                and ev.function in allowed_keys
                and prev.function not in allowed_keys
            ):
                by_key[key] = ev

        rows: list[dict[str, Any]] = []
        for idx, (key, name) in enumerate(template, start=1):
            ev = by_key.get(key)
            if ev is None:
                rows.append(
                    {
                        "step": idx,
                        "key": key,
                        "name": name,
                        "duration_ms": None,
                        "status": "not_run",
                        "success": None,
                        "function": key,
                    }
                )
                continue
            status = (ev.outcome or "completed").lower()
            if not ev.success:
                status = "failed"
            rows.append(
                {
                    "step": idx,
                    "key": key,
                    "name": name,
                    "duration_ms": None
                    if status == "skipped"
                    else round(ev.duration_ms, 3),
                    "status": status,
                    "success": ev.success,
                    "function": ev.function,
                }
            )

        # Append LLM inference detail under semantic when available
        llm_ev = next((e for e in self.events if e.function == "parse_via_runtime"), None)
        if llm_ev is not None:
            rows.append(
                {
                    "step": None,
                    "key": "llm_inference",
                    "name": "↳ LLM Inference (AI Runtime)",
                    "duration_ms": round(llm_ev.duration_ms, 3),
                    "status": "completed" if llm_ev.success else "failed",
                    "success": llm_ev.success,
                    "function": "parse_via_runtime",
                    "detail": True,
                }
            )
        return rows

    def _apply_checklist(self) -> list[dict[str, Any]]:
        """Ordered apply-submit steps + optional ATS score / narrative detail rows."""
        by_key: dict[str, TimingEvent] = {}
        for ev in self.events:
            key = ev.function
            if key in FUNCTION_TO_STEP_KEY:
                mapped = FUNCTION_TO_STEP_KEY[key]
                if key not in APPLY_STAGES:
                    key = mapped
            if key not in APPLY_STAGES:
                continue
            prev = by_key.get(key)
            if prev is None or ev.duration_ms > prev.duration_ms:
                by_key[key] = ev
            elif (
                prev.duration_ms <= 0
                and ev.duration_ms >= 0
                and ev.function in APPLY_STAGES
            ):
                by_key[key] = ev

        rows: list[dict[str, Any]] = []
        for idx, (key, name) in enumerate(APPLY_PIPELINE_STEPS, start=1):
            ev = by_key.get(key)
            if ev is None:
                rows.append(
                    {
                        "step": idx,
                        "key": key,
                        "name": name,
                        "duration_ms": None,
                        "status": "not_run",
                        "success": None,
                        "function": key,
                    }
                )
                continue
            status = (ev.outcome or "completed").lower()
            if not ev.success:
                status = "failed"
            rows.append(
                {
                    "step": idx,
                    "key": key,
                    "name": name,
                    "duration_ms": None
                    if status == "skipped"
                    else round(ev.duration_ms, 3),
                    "status": status,
                    "success": ev.success,
                    "function": ev.function,
                }
            )

        score_ev = next((e for e in self.events if e.function == "_internal_match"), None)
        if score_ev is not None:
            rows.append(
                {
                    "step": None,
                    "key": "ats_score",
                    "name": "↳ ATS Score Computation",
                    "duration_ms": round(score_ev.duration_ms, 3),
                    "status": "completed" if score_ev.success else "failed",
                    "success": score_ev.success,
                    "function": "_internal_match",
                    "detail": True,
                }
            )
        narr_ev = next(
            (e for e in self.events if e.function == "_optional_llm_narrative"), None
        )
        if narr_ev is not None:
            status = (narr_ev.outcome or "completed").lower()
            if not narr_ev.success:
                status = "failed"
            rows.append(
                {
                    "step": None,
                    "key": "ats_narrative",
                    "name": "↳ ATS Narrative (LLM)",
                    "duration_ms": None
                    if status == "skipped"
                    else round(narr_ev.duration_ms, 3),
                    "status": status,
                    "success": narr_ev.success,
                    "function": "_optional_llm_narrative",
                    "detail": True,
                }
            )
        return rows

    def function_details(self) -> list[dict[str, Any]]:
        """Every timed function with exact ms — primary detail view for the dashboard."""
        by_fn: dict[str, TimingEvent] = {}
        order: list[str] = []
        for ev in self.events:
            fn = ev.function
            if not fn:
                continue
            if fn not in by_fn:
                order.append(fn)
            prev = by_fn.get(fn)
            if prev is None or ev.duration_ms >= prev.duration_ms:
                by_fn[fn] = ev
        rows = []
        for fn in order:
            ev = by_fn[fn]
            label = STAGE_LABELS.get(fn) or ev.stage or fn
            category = STAGE_GROUP.get(label, "Other")
            if fn in LLM_FUNCTIONS:
                category = "LLM"
            rows.append(
                {
                    "function": fn,
                    "label": label,
                    "category": category,
                    "module": ev.module,
                    "duration_ms": round(ev.duration_ms, 2),
                    "success": ev.success,
                    "exception_name": ev.exception_name,
                    "depth": ev.depth,
                    "is_llm": fn in LLM_FUNCTIONS,
                }
            )
        return rows

    def category_breakdown(self) -> dict[str, Any]:
        """Roll-up totals — especially exact LLM time."""
        details = self.function_details()
        # Prefer leaf LLM inference time when available
        llm_inference = next(
            (r["duration_ms"] for r in details if r["function"] == "parse_via_runtime"),
            None,
        )
        llm_call = next(
            (r["duration_ms"] for r in details if r["function"] == "_call_section_llm"),
            None,
        )
        llm_narrative = next(
            (r["duration_ms"] for r in details if r["function"] == "_optional_llm_narrative"),
            None,
        )
        llm_total = 0.0
        if llm_inference is not None:
            llm_total += llm_inference
        if llm_narrative is not None:
            llm_total += llm_narrative
        elif llm_call is not None and llm_inference is None:
            llm_total += llm_call

        extract_ms = next(
            (
                r["duration_ms"]
                for r in details
                if r["function"] in ("extract_text", "text")
            ),
            None,
        )
        return {
            "llm_inference_ms": llm_inference,
            "llm_call_ms": llm_call,
            "llm_narrative_ms": llm_narrative,
            "llm_total_ms": round(llm_total, 2) if llm_total else None,
            "extract_text_ms": extract_ms,
            "overall_ms": round(self.total_duration_ms, 2),
            "function_count": len(details),
        }

    def stage_timeline(self) -> list[dict[str, Any]]:
        """One row per unique function (latest / max duration if nested duplicates)."""
        by_fn: dict[str, TimingEvent] = {}
        for ev in self.events:
            prev = by_fn.get(ev.function)
            if prev is None or ev.duration_ms >= prev.duration_ms:
                by_fn[ev.function] = ev
        rows = []
        for fn, ev in by_fn.items():
            rows.append(
                {
                    "function": fn,
                    "stage": ev.stage or STAGE_LABELS.get(fn, fn),
                    "duration_ms": round(ev.duration_ms, 2),
                    "success": ev.success,
                    "depth": ev.depth,
                }
            )
        rows.sort(key=lambda r: (-r["depth"], -r["duration_ms"]))
        return rows

    def pipeline_timeline(self) -> list[dict[str, Any]]:
        """
        Ordered product pipeline steps for the dashboard.

        Prefers Document Intelligence engine stages (cache → extract → … → save).
        When those exist, wrapper totals (_run_resume / run_document_intelligence)
        are omitted from the step list (still available as overall duration).
        """
        best: dict[str, TimingEvent] = {}
        has_engine = False
        for ev in self.events:
            if ev.function in ENGINE_STAGES:
                has_engine = True
            label = STAGE_LABELS.get(ev.function) or ev.stage or ev.function
            prev = best.get(label)
            if prev is None or ev.duration_ms >= prev.duration_ms:
                best[label] = ev

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for label in PIPELINE_ORDER:
            if has_engine and label in WRAPPER_STAGES:
                continue
            ev = best.get(label)
            if ev is None:
                continue
            seen.add(label)
            # Strip leading "N. " for cleaner UI numbering (FE can re-number)
            display = label
            rows.append(
                {
                    "stage": display,
                    "group": STAGE_GROUP.get(label, "Other"),
                    "function": ev.function,
                    "duration_ms": round(ev.duration_ms, 2),
                    "success": ev.success,
                }
            )
        for label, ev in best.items():
            if label in seen:
                continue
            if has_engine and label in WRAPPER_STAGES:
                continue
            rows.append(
                {
                    "stage": label,
                    "group": STAGE_GROUP.get(label, "Other"),
                    "function": ev.function,
                    "duration_ms": round(ev.duration_ms, 2),
                    "success": ev.success,
                }
            )
        return rows


class TimingCollector:
    def __init__(self, max_sessions: Optional[int] = None) -> None:
        self._lock = threading.RLock()
        self._max = max_sessions or developer_mode_max_sessions()
        self._sessions: dict[str, TimingSession] = {}
        self._order: deque[str] = deque(maxlen=self._max)
        self._open: dict[str, TimingSession] = {}

    def clear(self) -> int:
        """Remove all stored / in-flight timing sessions. Returns how many were dropped."""
        with self._lock:
            removed = len(self._sessions) + len(self._open)
            self._sessions.clear()
            self._order.clear()
            self._open.clear()
            return removed

    def begin_session(
        self,
        *,
        request_id: str,
        started_at: str,
        path: str = "",
        method: str = "",
        user_id: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> None:
        if not is_developer_mode_enabled():
            return
        with self._lock:
            session = TimingSession(
                request_id=request_id,
                started_at=started_at,
                path=path,
                method=method,
                user_id=user_id,
                job_id=str(job_id) if job_id else None,
            )
            self._open[request_id] = session

    def record(self, event: TimingEvent) -> None:
        if not is_developer_mode_enabled():
            return
        with self._lock:
            session = self._open.get(event.request_id) or self._sessions.get(event.request_id)
            if session is None:
                session = TimingSession(
                    request_id=event.request_id,
                    started_at=event.timestamp,
                    user_id=event.user_id,
                    candidate_id=event.candidate_id,
                    job_id=event.job_id,
                )
                self._open[event.request_id] = session
            session.events.append(event)
            if event.user_id:
                session.user_id = event.user_id
            if event.candidate_id:
                session.candidate_id = event.candidate_id
            if event.job_id:
                session.job_id = event.job_id
            if not event.success:
                session.status = "error"

    def mark_error(self, request_id: str) -> None:
        if not is_developer_mode_enabled():
            return
        with self._lock:
            session = self._open.get(request_id) or self._sessions.get(request_id)
            if session is not None:
                session.status = "error"

    def end_session(self, request_id: str, *, wall_duration_ms: Optional[float] = None) -> None:
        if not is_developer_mode_enabled():
            return
        with self._lock:
            session = self._open.pop(request_id, None)
            if session is None:
                return
            # Only keep requests that actually ran @timing-instrumented work
            if not session.events:
                return
            session.finished_at = datetime.now(timezone.utc).isoformat()
            # Prefer outermost timed duration as pipeline total; fall back to wall clock
            top = [e for e in session.events if e.depth <= 1]
            timed_total = max((e.duration_ms for e in (top or session.events)), default=0.0)
            if timed_total > 0:
                session.total_duration_ms = timed_total
            elif wall_duration_ms is not None:
                session.total_duration_ms = wall_duration_ms
            session.kind = _classify_session(session)
            self._sessions[request_id] = session
            self._order.append(request_id)
            alive = set(self._order)
            for rid in list(self._sessions.keys()):
                if rid not in alive:
                    self._sessions.pop(rid, None)

    def get_session(self, request_id: str) -> Optional[TimingSession]:
        with self._lock:
            session = self._sessions.get(request_id) or self._open.get(request_id)
            if session is None:
                return None
            if (not session.kind or session.kind == "other") and session.events:
                session.kind = _classify_session(session)
            if session.total_duration_ms <= 0 and session.events:
                top = [e for e in session.events if e.depth <= 1]
                session.total_duration_ms = max(
                    (e.duration_ms for e in (top or session.events)),
                    default=0.0,
                )
            return session

    def list_recent(
        self,
        *,
        limit: int = 50,
        candidate_id: Optional[str] = None,
        job_id: Optional[str] = None,
        function_name: Optional[str] = None,
        status: Optional[str] = None,
        request_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        kind: Optional[str] = None,
    ) -> list[TimingSession]:
        with self._lock:
            ids = list(reversed(self._order))
            sessions = [self._sessions[i] for i in ids if i in self._sessions]
            # Include in-flight / late-finished sessions that have events (SSE workers)
            for rid, open_sess in self._open.items():
                if open_sess.events and rid not in self._sessions:
                    sessions.insert(0, open_sess)
        out: list[TimingSession] = []
        for s in sessions:
            if request_id and s.request_id != request_id and not s.request_id.startswith(request_id):
                continue
            if candidate_id and (s.candidate_id or "") != candidate_id:
                continue
            if job_id and (s.job_id or "") != job_id:
                continue
            if status and s.status != status:
                continue
            # Finalize kind before filtering so open/legacy sessions match UI filters
            s.kind = _classify_session(s)
            if kind and s.kind != kind:
                continue
            if function_name:
                fn = function_name.lower()
                if not any(fn in e.function.lower() or fn in e.module.lower() for e in s.events):
                    continue
            if date_from and s.started_at < date_from:
                continue
            if date_to and s.started_at > date_to:
                continue
            if s.total_duration_ms <= 0 and s.events:
                s.total_duration_ms = max(e.duration_ms for e in s.events)
            out.append(s)
            if len(out) >= limit:
                break
        return out

    def compute_stats(self, *, hours: float = 24.0) -> dict[str, Any]:
        with self._lock:
            sessions = list(self._sessions.values())

        cutoff = None
        if hours and hours > 0:
            from datetime import timedelta

            cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

        filtered = [s for s in sessions if not cutoff or s.started_at >= cutoff]

        def _avg_for_kind(kind: str) -> Optional[float]:
            vals = [s.total_duration_ms for s in filtered if s.kind == kind and s.total_duration_ms > 0]
            if not vals:
                # Fallback: sessions that contain a marker function
                markers = KIND_MARKERS.get(kind, ())
                vals = []
                for s in filtered:
                    for e in s.events:
                        if e.function in markers:
                            vals.append(e.duration_ms)
                            break
            return round(statistics.mean(vals), 2) if vals else None

        fn_durations: dict[str, list[float]] = defaultdict(list)
        all_durations: list[float] = []
        for s in filtered:
            if s.total_duration_ms > 0:
                all_durations.append(s.total_duration_ms)
            for e in s.events:
                fn_durations[e.function].append(e.duration_ms)

        def _avg_map(d: dict[str, list[float]]) -> list[dict[str, Any]]:
            rows = [
                {
                    "function": fn,
                    "avg_ms": round(statistics.mean(vals), 2),
                    "count": len(vals),
                    "max_ms": round(max(vals), 2),
                    "min_ms": round(min(vals), 2),
                }
                for fn, vals in d.items()
                if vals
            ]
            return rows

        avgs = _avg_map(fn_durations)
        slowest = sorted(avgs, key=lambda r: r["avg_ms"], reverse=True)[:10]
        fastest = sorted(avgs, key=lambda r: r["avg_ms"])[:10]

        p95 = None
        if all_durations:
            sorted_d = sorted(all_durations)
            idx = min(len(sorted_d) - 1, int(round(0.95 * (len(sorted_d) - 1))))
            p95 = round(sorted_d[idx], 2)

        # Hourly averages for charts (last 24 buckets)
        hourly_parse: dict[str, list[float]] = defaultdict(list)
        hourly_ats: dict[str, list[float]] = defaultdict(list)
        hourly_all: dict[str, list[float]] = defaultdict(list)
        for s in filtered:
            hour_key = (s.started_at or "")[:13]  # YYYY-MM-DDTHH
            if not hour_key:
                continue
            if s.kind in ("resume_parse", "jd_parse") and s.total_duration_ms > 0:
                hourly_parse[hour_key].append(s.total_duration_ms)
            if s.kind == "ats" and s.total_duration_ms > 0:
                hourly_ats[hour_key].append(s.total_duration_ms)
            if s.total_duration_ms > 0:
                hourly_all[hour_key].append(s.total_duration_ms)

        def _series(d: dict[str, list[float]]) -> list[dict[str, Any]]:
            return [
                {"hour": k, "avg_ms": round(statistics.mean(v), 2), "count": len(v)}
                for k, v in sorted(d.items())
            ]

        distribution = [
            {
                "function": r["function"],
                "avg_ms": r["avg_ms"],
                "count": r["count"],
            }
            for r in sorted(avgs, key=lambda x: x["count"], reverse=True)[:20]
        ]

        return {
            "window_hours": hours,
            "request_count": len(filtered),
            "average_resume_parse_ms": _avg_for_kind("resume_parse"),
            "average_jd_parse_ms": _avg_for_kind("jd_parse"),
            "average_ats_ms": _avg_for_kind("ats"),
            "average_apply_ms": _avg_for_kind("apply"),
            "p95_request_ms": p95,
            "slowest_functions": slowest,
            "fastest_functions": fastest,
            "charts": {
                "avg_parsing_24h": _series(hourly_parse),
                "avg_ats_24h": _series(hourly_ats),
                "request_duration_trend": _series(hourly_all),
                "top_slowest_functions": slowest,
                "function_distribution": distribution,
            },
        }

    def list_recent_summaries(self, *, limit: int = 50, **filters) -> list[dict[str, Any]]:
        """
        Recent sessions for the dashboard.

        - Single resume parse → ``resume_parse`` rows (Resume filter)
        - Bulk worker files → one ``bulk_parse`` row per job (Bulk filter)
        Kind filter is applied after grouping so Resume never includes bulk jobs.
        """
        kind_filter = (filters.get("kind") or "").strip() or None
        # Fetch without kind so bulk grouping still works when filtering by kind
        fetch_filters = {k: v for k, v in filters.items() if k != "kind"}
        raw = self.list_recent(limit=max(limit * 4, 80), **fetch_filters)

        by_job: dict[str, list[TimingSession]] = {}
        for s in raw:
            kind = _classify_session(s)
            s.kind = kind
            if kind == "bulk_parse":
                jid = str(s.job_id or s.request_id)
                by_job.setdefault(jid, []).append(s)

        seen_jobs: set[str] = set()
        out: list[dict[str, Any]] = []
        for s in raw:
            kind = _classify_session(s)
            s.kind = kind
            if kind == "bulk_parse":
                jid = str(s.job_id or s.request_id)
                if jid in seen_jobs:
                    continue
                seen_jobs.add(jid)
                kids = by_job.get(jid) or [s]
                if s.job_id:
                    kids = self._bulk_sessions_for_job(str(s.job_id)) or kids
                summary = _bulk_group_summary(str(s.job_id or jid), kids)
            else:
                # Never surface bulk worker files under Resume / JD / Apply
                summary = s.to_summary()
            if kind_filter and summary.get("kind") != kind_filter:
                continue
            out.append(summary)
            if len(out) >= limit:
                break
        return out

    def _bulk_sessions_for_job(self, job_id: str) -> list[TimingSession]:
        jid = str(job_id)
        with self._lock:
            found = [
                s
                for s in list(self._sessions.values()) + list(self._open.values())
                if (s.kind == "bulk_parse" or _classify_session(s) == "bulk_parse")
                and str(s.job_id or "") == jid
                and s.events
            ]
        found.sort(key=lambda s: s.started_at or "", reverse=True)
        return found

    def get_bulk_detail(self, job_id: str) -> Optional[dict[str, Any]]:
        kids = self._bulk_sessions_for_job(job_id)
        if not kids:
            # Synthetic group key when a bulk file had no job_id (request_id used)
            sess = self.get_session(job_id)
            if sess is not None and _classify_session(sess) == "bulk_parse":
                kids = [sess]
        if not kids:
            return None
        return _bulk_group_detail(str(job_id), kids)

    def get_session_or_bulk(self, request_id: str) -> Optional[dict[str, Any]]:
        rid = (request_id or "").strip()
        if rid.startswith("bulk:"):
            return self.get_bulk_detail(rid[5:])
        session = self.get_session(rid)
        if session is None:
            return None
        return session.to_detail()


def _filename_from_bulk_path(path: str) -> str:
    p = (path or "").rstrip("/")
    if "/bulk-parse/" in p:
        return p.split("/bulk-parse/", 1)[-1] or "resume"
    return p.split("/")[-1] or "resume"


def _bulk_group_summary(job_id: str, kids: list[TimingSession]) -> dict[str, Any]:
    kids = sorted(kids, key=lambda s: s.started_at or "")
    total_ms = sum(float(s.total_duration_ms or 0) for s in kids)
    ok = sum(1 for s in kids if s.status != "error")
    failed = sum(1 for s in kids if s.status == "error")
    started = kids[0].started_at if kids else None
    finished = None
    for s in kids:
        if s.finished_at:
            finished = s.finished_at
    return {
        "request_id": f"bulk:{job_id}",
        "started_at": started,
        "finished_at": finished,
        "path": f"/api/admin/bulk-parse/job/{job_id}",
        "method": "WORKER",
        "user_id": kids[0].user_id if kids else None,
        "candidate_id": None,
        "job_id": job_id,
        "status": "error" if failed and not ok else ("ok" if failed == 0 else "ok"),
        "total_duration_ms": round(total_ms, 2),
        "kind": "bulk_parse",
        "event_count": sum(len(s.events) for s in kids),
        "stages": [],
        "resume_count": len(kids),
        "success_count": ok,
        "failed_count": failed,
        "is_bulk_group": True,
        # Lightweight file list for sidebar expand (no full step payloads)
        "files": [
            {
                "request_id": s.request_id,
                "filename": _filename_from_bulk_path(s.path),
                "total_duration_ms": round(float(s.total_duration_ms or 0), 2),
                "status": s.status,
            }
            for s in kids
        ],
    }


def _bulk_group_detail(job_id: str, kids: list[TimingSession]) -> dict[str, Any]:
    summary = _bulk_group_summary(job_id, kids)
    # Aggregate checklist: average duration for completed steps; skipped if all skipped
    templates = list(RESUME_PIPELINE_STEPS)
    by_key: dict[str, list[dict[str, Any]]] = {k: [] for k, _ in templates}
    for s in kids:
        for row in s.parse_checklist():
            key = row.get("key")
            if key in by_key and not row.get("detail"):
                by_key[key].append(row)

    parse_steps: list[dict[str, Any]] = []
    for idx, (key, name) in enumerate(templates, start=1):
        rows = by_key.get(key) or []
        if not rows:
            parse_steps.append(
                {
                    "step": idx,
                    "key": key,
                    "name": name,
                    "duration_ms": None,
                    "status": "not_run",
                    "success": None,
                    "function": key,
                }
            )
            continue
        skipped = all((r.get("status") or "") == "skipped" for r in rows)
        failed = any((r.get("status") or "") == "failed" for r in rows)
        completed = [
            r
            for r in rows
            if (r.get("status") or "") == "completed" and r.get("duration_ms") is not None
        ]
        if skipped and not completed:
            parse_steps.append(
                {
                    "step": idx,
                    "key": key,
                    "name": name,
                    "duration_ms": None,
                    "status": "skipped",
                    "success": True,
                    "function": key,
                }
            )
        elif failed and not completed:
            parse_steps.append(
                {
                    "step": idx,
                    "key": key,
                    "name": name,
                    "duration_ms": None,
                    "status": "failed",
                    "success": False,
                    "function": key,
                }
            )
        else:
            avg = (
                sum(float(r["duration_ms"]) for r in completed) / len(completed)
                if completed
                else None
            )
            parse_steps.append(
                {
                    "step": idx,
                    "key": key,
                    "name": name,
                    "duration_ms": round(avg, 2) if avg is not None else None,
                    "status": "completed" if avg is not None else "not_run",
                    "success": True,
                    "function": key,
                }
            )

    files = []
    for s in sorted(kids, key=lambda x: x.started_at or ""):
        files.append(
            {
                "request_id": s.request_id,
                "filename": _filename_from_bulk_path(s.path),
                "total_duration_ms": round(float(s.total_duration_ms or 0), 2),
                "status": s.status,
                "started_at": s.started_at,
                # Per-resume checklist — same shape as a single resume_parse detail
                "parse_steps": s.parse_checklist(),
                "kind": "resume_parse",
            }
        )

    detail = dict(summary)
    detail["events"] = []
    detail["timeline"] = []
    detail["functions"] = []
    detail["breakdown"] = {}
    detail["parse_steps"] = parse_steps
    detail["files"] = files
    detail["resume_count"] = len(kids)
    return detail


def _classify_session(session: TimingSession) -> str:
    names = {e.function for e in session.events}
    path = (session.path or "").lower()
    if "public_apply_to_job" in names or "/apply" in path:
        return "apply"
    if "match_candidate_to_job" in names or "_internal_match" in names:
        return "ats"
    if "/bulk-parse" in path or path.startswith("bulk:") or "bulk_parse" in path:
        return "bulk_parse"
    # Resume before JD-by-engine-stages: path/functions are authoritative
    if "/parse/resume" in path or "_run_resume" in names or "enrich_resume_semantic" in names:
        return "resume_parse"
    if "/parse/jd" in path or "_run_jd" in names or "enrich_jd_semantic" in names:
        return "jd_parse"
    if "coverage" in names:
        return "jd_parse"
    if "run_document_intelligence" in names or (names & ENGINE_STAGES):
        if "jd" in path:
            return "jd_parse"
        return "resume_parse"
    if "extract_text" in names or "text" in names:
        return "jd_parse" if "jd" in path else "resume_parse"
    return "other"


def record_pipeline_stage(
    stage: str,
    outcome: str,
    *,
    duration_ms: float = 0.0,
    module: str = "app.core.timing_collector",
    depth: int = 2,
) -> None:
    """
    Record one Document Intelligence / bulk checklist stage when Developer Mode is on
    and a timing request context is bound. No-op otherwise.
    """
    try:
        from app.core.developer_mode import is_developer_mode_enabled
        from app.core.request_context import get_timing_context

        if not is_developer_mode_enabled() or not stage or get_timing_context() is None:
            return
        status = (outcome or "completed").lower()
        if status not in ("completed", "failed", "skipped"):
            status = "completed"
        timing_collector.record(
            make_timing_event(
                function=stage,
                module=module,
                duration_ms=max(0.0, float(duration_ms)),
                success=status != "failed",
                exception_name="StageFailed" if status == "failed" else None,
                depth=depth,
                outcome=status,
            )
        )
    except Exception:
        pass


# Process-wide singleton
timing_collector = TimingCollector()


def make_timing_event(
    *,
    function: str,
    module: str,
    duration_ms: float,
    success: bool,
    exception_name: Optional[str] = None,
    depth: int = 0,
    outcome: str = "completed",
) -> TimingEvent:
    from app.core.request_context import get_timing_context

    ctx = get_timing_context()
    request_id = ctx.request_id if ctx else f"orphan-{id(threading.current_thread())}"
    short = function.rsplit(".", 1)[-1]
    return TimingEvent(
        request_id=request_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        function=short,
        module=module,
        duration_ms=round(duration_ms, 3),
        success=success,
        exception_name=exception_name,
        user_id=ctx.user_id if ctx else None,
        candidate_id=ctx.candidate_id if ctx else None,
        job_id=ctx.job_id if ctx else None,
        depth=depth,
        stage=STAGE_LABELS.get(short, short),
        outcome=outcome if outcome in ("completed", "failed", "skipped") else "completed",
    )
