"""Unit tests for Developer Mode timing collector (no Flask app required)."""
from __future__ import annotations

import os
import unittest

# Ensure flag is on before importing modules that may cache it
os.environ["DEVELOPER_MODE"] = "true"


class TimingCollectorTests(unittest.TestCase):
    def setUp(self):
        from app.core.developer_mode import clear_developer_mode_cache
        from app.core.timing_collector import TimingCollector, TimingEvent, timing_collector

        clear_developer_mode_cache()
        os.environ["DEVELOPER_MODE"] = "true"
        clear_developer_mode_cache()
        self.TimingCollector = TimingCollector
        self.TimingEvent = TimingEvent
        timing_collector.clear()
        self.collector = TimingCollector(max_sessions=20)

    def tearDown(self):
        from app.core.developer_mode import clear_developer_mode_cache

        os.environ.pop("DEVELOPER_MODE", None)
        clear_developer_mode_cache()

    def _event(self, request_id: str, function: str, ms: float, **kwargs):
        return self.TimingEvent(
            request_id=request_id,
            timestamp="2026-08-05T12:00:00+00:00",
            function=function,
            module="tests",
            duration_ms=ms,
            success=kwargs.get("success", True),
            exception_name=kwargs.get("exception_name"),
            user_id=kwargs.get("user_id"),
            candidate_id=kwargs.get("candidate_id"),
            job_id=kwargs.get("job_id"),
            depth=kwargs.get("depth", 1),
            stage=kwargs.get("stage", function),
        )

    def test_session_grouping_and_stats(self):
        from datetime import datetime, timezone

        rid = "abc123"
        started = datetime.now(timezone.utc).isoformat()
        self.collector.begin_session(
            request_id=rid,
            started_at=started,
            path="/api/parse/resume",
            method="POST",
        )
        self.collector.record(self._event(rid, "extract_text", 820, depth=2))
        self.collector.record(self._event(rid, "enrich_resume_semantic", 1720, depth=2))
        self.collector.record(self._event(rid, "run_document_intelligence", 2600, depth=1))
        self.collector.record(
            self._event(rid, "_run_resume", 2600, depth=1, candidate_id="C1")
        )
        self.collector.end_session(rid, wall_duration_ms=2650)

        session = self.collector.get_session(rid)
        self.assertIsNotNone(session)
        self.assertEqual(session.kind, "resume_parse")
        self.assertEqual(session.candidate_id, "C1")
        self.assertAlmostEqual(session.total_duration_ms, 2650, places=1)
        detail = session.to_detail()
        self.assertTrue(any("Extract Text" in s["stage"] for s in detail["timeline"]))


        stats = self.collector.compute_stats(hours=24)
        self.assertEqual(stats["request_count"], 1)
        self.assertIsNotNone(stats["average_resume_parse_ms"])

    def test_inactive_when_disabled(self):
        from app.core.developer_mode import clear_developer_mode_cache

        os.environ["DEVELOPER_MODE"] = "false"
        clear_developer_mode_cache()
        col = self.TimingCollector(max_sessions=10)
        col.begin_session(request_id="x", started_at="2026-08-05T12:00:00+00:00")
        col.record(self._event("x", "extract_text", 10))
        col.end_session("x", wall_duration_ms=10)
        self.assertIsNone(col.get_session("x"))
        self.assertEqual(col.list_recent(), [])

    def test_clear_wipes_sessions(self):
        rid = "clear-me"
        self.collector.begin_session(
            request_id=rid,
            started_at="2026-08-05T12:00:00+00:00",
            path="/api/parse/resume",
            method="POST",
        )
        self.collector.record(self._event(rid, "extract_text", 10))
        self.collector.end_session(rid, wall_duration_ms=10)
        self.assertEqual(len(self.collector.list_recent()), 1)
        self.collector.clear()
        self.assertEqual(self.collector.list_recent(), [])
        self.assertEqual(self.collector.list_recent_summaries(), [])


class TimingDecoratorTests(unittest.TestCase):
    def setUp(self):
        from app.core.developer_mode import clear_developer_mode_cache
        from app.core.timing_collector import timing_collector

        os.environ["DEVELOPER_MODE"] = "true"
        clear_developer_mode_cache()
        timing_collector.clear()

    def tearDown(self):
        from app.core.developer_mode import clear_developer_mode_cache

        os.environ.pop("DEVELOPER_MODE", None)
        clear_developer_mode_cache()

    def test_timing_records_on_success_and_failure(self):
        from app.core.request_context import start_request_context
        from app.core.timing import timing
        from app.core.timing_collector import timing_collector

        ctx = start_request_context(path="/test", method="GET")
        timing_collector.begin_session(
            request_id=ctx.request_id,
            started_at=ctx.started_at_iso,
            path="/test",
            method="GET",
        )

        @timing
        def sample_ok(candidate_id=None):
            return 42

        @timing
        def sample_fail():
            raise ValueError("boom")

        self.assertEqual(sample_ok(candidate_id="C9"), 42)
        with self.assertRaises(ValueError):
            sample_fail()

        timing_collector.end_session(ctx.request_id, wall_duration_ms=5)
        session = timing_collector.get_session(ctx.request_id)
        self.assertIsNotNone(session)
        names = {e.function for e in session.events}
        self.assertIn("sample_ok", names)
        self.assertIn("sample_fail", names)
        self.assertEqual(session.candidate_id, "C9")
        self.assertEqual(session.status, "error")

    def test_thread_worker_inherits_timing_context(self):
        """SSE parse workers must bind the parent request timing context."""
        from concurrent.futures import ThreadPoolExecutor

        from app.core.request_context import run_in_timing_context, start_request_context
        from app.core.timing import timing
        from app.core.timing_collector import timing_collector

        ctx = start_request_context(path="/api/parse/jd/stream", method="POST")
        timing_collector.begin_session(
            request_id=ctx.request_id,
            started_at=ctx.started_at_iso,
            path=ctx.path,
            method=ctx.method,
        )

        @timing
        def _fake_jd_parse():
            return "ok"

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(run_in_timing_context, ctx, _fake_jd_parse)
            self.assertEqual(future.result(), "ok")

        timing_collector.end_session(ctx.request_id, wall_duration_ms=100)
        session = timing_collector.get_session(ctx.request_id)
        self.assertIsNotNone(session)
        self.assertEqual(len(session.events), 1)
        self.assertEqual(session.events[0].request_id, ctx.request_id)
        self.assertEqual(session.events[0].function, "_fake_jd_parse")

    def test_engine_stage_timeline_order(self):
        from app.core.timing_collector import TimingCollector, TimingEvent

        col = TimingCollector(max_sessions=10)
        rid = "jd1"
        col.begin_session(request_id=rid, started_at="2026-08-05T12:00:00+00:00", path="/api/parse/jd/stream")
        for fn, ms in (
            ("cache", 5),
            ("persist_raw", 40),
            ("text", 800),
            ("layout", 50),
            ("sections", 20),
            ("deterministic", 100),
            ("semantic", 1500),
            ("validate", 10),
            ("persist", 30),
            ("_run_jd", 2555),
        ):
            col.record(
                TimingEvent(
                    request_id=rid,
                    timestamp="2026-08-05T12:00:01+00:00",
                    function=fn,
                    module="pipeline",
                    duration_ms=ms,
                    success=True,
                    depth=2 if fn != "_run_jd" else 1,
                    stage=fn,
                )
            )
        col.end_session(rid, wall_duration_ms=2600)
        detail = col.get_session(rid).to_detail()
        stages = [r["stage"] for r in detail["timeline"]]
        self.assertTrue(any("Extract Text" in s for s in stages))
        # Wrapper total hidden when engine stages exist
        self.assertFalse(any("JD Parsing (total)" == s for s in stages))

        checklist = col.get_session(rid).parse_checklist()
        names = [c["name"] for c in checklist]
        self.assertIn("Cache Check", names)
        self.assertIn("Extract Text", names)
        self.assertIn("Semantic Enrichment (LLM)", names)
        self.assertIn("Save Parsed Result", names)
        text_step = next(c for c in checklist if c["key"] == "text")
        self.assertEqual(text_step["duration_ms"], 800)
        self.assertEqual(text_step["status"], "completed")

    def test_bulk_parse_uses_resume_checklist(self):
        from app.core.request_context import start_request_context, set_timing_context
        from app.core.timing_collector import TimingCollector, record_pipeline_stage

        col = TimingCollector()
        # Patch singleton used by record_pipeline_stage
        import app.core.timing_collector as tc

        prev = tc.timing_collector
        tc.timing_collector = col
        try:
            ctx = start_request_context(
                path="/api/admin/bulk-parse/alice.pdf", method="WORKER"
            )
            col.begin_session(
                request_id=ctx.request_id,
                started_at=ctx.started_at_iso,
                path=ctx.path,
                method=ctx.method,
                job_id="job-bulk-1",
            )
            record_pipeline_stage("cache", "skipped")
            record_pipeline_stage("text", "completed", duration_ms=50)
            record_pipeline_stage("sections", "completed", duration_ms=5)
            record_pipeline_stage("deterministic", "completed", duration_ms=20)
            record_pipeline_stage("semantic", "skipped")
            record_pipeline_stage("knowledge", "completed", duration_ms=4)
            record_pipeline_stage("validate", "completed", duration_ms=2)
            record_pipeline_stage("persist", "completed", duration_ms=1)
            col.end_session(ctx.request_id, wall_duration_ms=90)
            sess = col.get_session(ctx.request_id)
            self.assertEqual(sess.kind, "bulk_parse")
            checklist = sess.parse_checklist()
            names = [c["name"] for c in checklist if not c.get("detail")]
            self.assertEqual(
                names,
                [
                    "Cache Check",
                    "Store Raw File",
                    "Extract Text",
                    "Layout Analysis",
                    "Section Detection",
                    "Deterministic Parse",
                    "Coverage Check",
                    "Semantic Enrichment (LLM)",
                    "Knowledge Enrichment",
                    "Validation",
                    "Save Parsed Result",
                ],
            )
            text_step = next(c for c in checklist if c["key"] == "text")
            self.assertEqual(text_step["duration_ms"], 50)
            cache_step = next(c for c in checklist if c["key"] == "cache")
            self.assertEqual(cache_step["status"], "skipped")
            coverage_step = next(c for c in checklist if c["key"] == "coverage")
            self.assertEqual(coverage_step["status"], "not_run")

            # Resume filter must not include bulk; Bulk filter gets one grouped row
            resume_rows = col.list_recent_summaries(limit=20, kind="resume_parse")
            self.assertEqual(resume_rows, [])
            bulk_rows = col.list_recent_summaries(limit=20, kind="bulk_parse")
            self.assertEqual(len(bulk_rows), 1)
            self.assertEqual(bulk_rows[0]["kind"], "bulk_parse")
            self.assertTrue(bulk_rows[0]["is_bulk_group"])
            self.assertEqual(bulk_rows[0]["resume_count"], 1)
            self.assertEqual(len(bulk_rows[0].get("files") or []), 1)

            detail = col.get_bulk_detail("job-bulk-1")
            self.assertIsNotNone(detail)
            self.assertEqual(len(detail["files"]), 1)
            self.assertTrue(detail["files"][0]["parse_steps"])
            names = [c["name"] for c in detail["files"][0]["parse_steps"] if not c.get("detail")]
            self.assertIn("Extract Text", names)
            self.assertIn("Deterministic Parse", names)
        finally:
            tc.timing_collector = prev
            set_timing_context(None)

    def test_apply_checklist_shows_each_step_time(self):
        from app.core.timing_collector import TimingCollector, TimingEvent

        col = TimingCollector(max_sessions=10)
        rid = "apply1"
        col.begin_session(
            request_id=rid,
            started_at="2026-08-27T05:00:00+00:00",
            path="/api/jobs/job-9/apply",
            method="POST",
        )
        for fn, ms, depth in (
            ("_internal_match", 12, 2),
            ("match_candidate_to_job", 15, 2),
            ("_persist_application_atomic", 8, 2),
            ("public_apply_to_job", 40, 1),
        ):
            col.record(
                TimingEvent(
                    request_id=rid,
                    timestamp="2026-08-27T05:00:01+00:00",
                    function=fn,
                    module="apply",
                    duration_ms=ms,
                    success=True,
                    depth=depth,
                    stage=fn,
                )
            )
        col.end_session(rid, wall_duration_ms=5)
        sess = col.get_session(rid)
        self.assertEqual(sess.kind, "apply")
        self.assertAlmostEqual(sess.total_duration_ms, 40)
        by_key = {c["key"]: c for c in sess.parse_checklist() if not c.get("detail")}
        self.assertEqual(by_key["ats_score"]["duration_ms"], 12)
        self.assertEqual(by_key["ats_match"]["duration_ms"], 15)
        self.assertEqual(by_key["persist_application"]["duration_ms"], 8)
        self.assertEqual(by_key["apply_submit"]["duration_ms"], 40)
        for row in by_key.values():
            self.assertEqual(row["status"], "completed")

    def test_zero_ms_engine_stage_does_not_hide_real_extract_time(self):
        from app.core.timing_collector import TimingCollector, TimingEvent

        col = TimingCollector(max_sessions=10)
        rid = "resume-zero"
        col.begin_session(
            request_id=rid,
            started_at="2026-08-27T05:00:00+00:00",
            path="/api/parse/resume/public/stream",
            method="POST",
        )
        col.record(
            TimingEvent(
                request_id=rid,
                timestamp="2026-08-27T05:00:01+00:00",
                function="text",
                module="pipeline",
                duration_ms=0,
                success=True,
                depth=2,
                stage="text",
            )
        )
        col.record(
            TimingEvent(
                request_id=rid,
                timestamp="2026-08-27T05:00:01+00:00",
                function="extract_text",
                module="text_extraction",
                duration_ms=820,
                success=True,
                depth=2,
                stage="extract_text",
            )
        )
        col.record(
            TimingEvent(
                request_id=rid,
                timestamp="2026-08-27T05:00:02+00:00",
                function="_run_resume",
                module="pipeline",
                duration_ms=900,
                success=True,
                depth=1,
                stage="_run_resume",
            )
        )
        col.end_session(rid, wall_duration_ms=10)
        text_step = next(c for c in col.get_session(rid).parse_checklist() if c["key"] == "text")
        self.assertEqual(text_step["duration_ms"], 820)
        self.assertEqual(text_step["status"], "completed")
        coverage = next(c for c in col.get_session(rid).parse_checklist() if c["key"] == "coverage")
        self.assertEqual(coverage["status"], "not_run")
        upload = next(c for c in col.get_session(rid).parse_checklist() if c["key"] == "upload")
        self.assertEqual(upload["status"], "not_run")
        autofill = next(c for c in col.get_session(rid).parse_checklist() if c["key"] == "autofill")
        self.assertEqual(autofill["status"], "not_run")

    def test_wall_clock_beats_parse_wrapper_total(self):
        """SSE teardown used to freeze total at _run_resume (49s) while the user waited minutes."""
        from app.core.timing_collector import TimingCollector, TimingEvent

        col = TimingCollector(max_sessions=10)
        rid = "resume-wall"
        col.begin_session(
            request_id=rid,
            started_at="2026-08-27T05:00:00+00:00",
            path="/api/parse/resume/stream",
            method="POST",
        )
        col.record(
            TimingEvent(
                request_id=rid,
                timestamp="2026-08-27T05:00:01+00:00",
                function="text",
                module="pipeline",
                duration_ms=27000,
                success=True,
                depth=2,
                stage="text",
            )
        )
        col.record(
            TimingEvent(
                request_id=rid,
                timestamp="2026-08-27T05:00:50+00:00",
                function="_run_resume",
                module="pipeline",
                duration_ms=49000,
                success=True,
                depth=1,
                stage="_run_resume",
            )
        )
        col.end_session(rid, wall_duration_ms=150000)
        sess = col.get_session(rid)
        self.assertAlmostEqual(sess.total_duration_ms, 150000, places=1)
        self.assertAlmostEqual(sess.wall_duration_ms, 150000, places=1)

    def test_client_autofill_timing_sets_user_visible_total(self):
        from app.core.timing_collector import TimingCollector, TimingEvent, attach_client_timings
        import app.core.timing_collector as tc

        col = TimingCollector(max_sessions=10)
        prev = tc.timing_collector
        tc.timing_collector = col
        try:
            rid = "resume-client"
            col.begin_session(
                request_id=rid,
                started_at="2026-08-27T05:00:00+00:00",
                path="/api/parse/resume/public/stream",
                method="POST",
            )
            col.record(
                TimingEvent(
                    request_id=rid,
                    timestamp="2026-08-27T05:00:01+00:00",
                    function="_run_resume",
                    module="pipeline",
                    duration_ms=49000,
                    success=True,
                    depth=1,
                    stage="_run_resume",
                )
            )
            col.end_session(rid, wall_duration_ms=52000)
            self.assertTrue(
                attach_client_timings(
                    rid,
                    {
                        "total_ms": 185000,
                        "spans": [
                            {"key": "upload", "duration_ms": 800},
                            {"key": "client_wait", "duration_ms": 120000},
                            {"key": "text", "duration_ms": 180000},
                            {"key": "autofill", "duration_ms": 1400},
                        ],
                    },
                )
            )
            sess = col.get_session(rid)
            self.assertAlmostEqual(sess.total_duration_ms, 185000, places=1)
            by_key = {c["key"]: c for c in sess.parse_checklist() if not c.get("detail")}
            self.assertEqual(by_key["upload"]["duration_ms"], 800)
            self.assertEqual(by_key["client_wait"]["duration_ms"], 120000)
            self.assertEqual(by_key["autofill"]["duration_ms"], 1400)
            self.assertEqual(by_key["autofill"]["status"], "completed")
            self.assertEqual(by_key["text"]["duration_ms"], 180000)
        finally:
            tc.timing_collector = prev


if __name__ == "__main__":
    unittest.main()
