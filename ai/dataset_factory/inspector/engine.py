"""Core inspection engine."""

from __future__ import annotations

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .analyzers import analyze_docx, analyze_pdf
from .config import FACTORY_VERSION, InspectorConfig, STAGE_VERSION
from .discovery import build_directory_tree, discover_files, initial_file_record
from .duplicates import detect_filename_duplicates, detect_hash_duplicates
from .format_detection import FormatRegistry
from .hashing import hash_file
from .logging_setup import log_file_issue, log_phase
from .models import (
    InspectionPhase,
    InspectionResult,
    OcrSignal,
    PhaseRecord,
    PhaseStatus,
)
from .quality import assess_quality, quality_to_dict
from .reporting.generators import (
    build_hash_index,
    build_inspection_log,
    build_manifest,
    build_profile,
)
from .reporting.writer import write_artifacts
from .sampling import select_sample_files
from .statistics import compute_statistics, statistics_to_dict
from .utils import isoformat_datetime, utc_now


class InspectionEngine:
    """Orchestrates read-only dataset inspection."""

    def __init__(
        self,
        config: InspectorConfig,
        logger: logging.Logger,
        events: list | None = None,
    ) -> None:
        self.config = config
        self.logger = logger
        self.events = events
        self.registry = FormatRegistry()

    def run(self) -> InspectionResult:
        """Execute a full inspection run."""
        started_at = utc_now()
        result = InspectionResult(
            run_id=str(uuid.uuid4()),
            started_at=started_at,
            source_path=str(self.config.source_path),
            output_path=str(self.config.output_path),
            dry_run=self.config.dry_run,
        )
        result.phases = [
            PhaseRecord(phase_id=phase.value) for phase in InspectionPhase
        ]

        t0 = time.perf_counter()

        try:
            self._run_phase(result, InspectionPhase.DISCOVER, self._phase_discover)
            self._run_phase(result, InspectionPhase.CLASSIFY, self._phase_classify)
            self._run_phase(result, InspectionPhase.MEASURE, self._phase_measure)
            self._run_phase(result, InspectionPhase.HASH, self._phase_hash)
            self._run_phase(result, InspectionPhase.DETECT_ISSUES, self._phase_detect_issues)
            self._run_phase(result, InspectionPhase.SAMPLE, self._phase_sample)
            self._run_phase(result, InspectionPhase.SCORE, self._phase_score)
            result.status = "inspected_with_warnings" if result.errors else "inspected"
            if result.stats.issues["corrupt"] > 0 or result.stats.issues["zero_byte"] > 0:
                result.status = "inspected_with_warnings"
            result.completed_at = utc_now()
            result.duration_seconds = time.perf_counter() - t0
            self._run_phase(result, InspectionPhase.EMIT, self._phase_emit)
        except Exception as exc:  # noqa: BLE001
            result.status = "inspection_failed"
            self.logger.exception("Inspection failed: %s", exc)
            raise
        finally:
            if result.completed_at is None:
                result.completed_at = utc_now()
            if result.duration_seconds == 0.0:
                result.duration_seconds = time.perf_counter() - t0
            if self.events is not None:
                result.events = list(self.events)

        return result

    def _run_phase(self, result: InspectionResult, phase: InspectionPhase, handler) -> None:
        record = next(item for item in result.phases if item.phase_id == phase.value)
        record.status = PhaseStatus.RUNNING
        record.started_at = utc_now()
        log_phase(self.logger, phase.value, f"Starting phase: {phase.value}")
        handler(result)
        record.completed_at = utc_now()
        record.status = PhaseStatus.SUCCESS
        log_phase(self.logger, phase.value, f"Completed phase: {phase.value}")

    def _phase_discover(self, result: InspectionResult) -> None:
        file_paths, _ = discover_files(self.config)
        result.files = [initial_file_record(path, self.config.source_path) for path in file_paths]
        tree, max_depth, total_dirs = build_directory_tree(
            self.config.source_path,
            file_paths,
            self.config.max_depth_logged,
        )
        result.directory_tree = tree
        result.max_depth = max_depth
        result.total_directories = total_dirs
        self.logger.info("Discovered %d files", len(result.files))

    def _phase_classify(self, result: InspectionResult) -> None:
        for record in result.files:
            if record.read_error:
                continue
            path = Path(record.absolute_path)
            detected = self.registry.detect(path)
            record.format = detected.format_id
            record.unsupported_format = not detected.supported

    def _phase_measure(self, result: InspectionResult) -> None:
        return

    def _phase_hash(self, result: InspectionResult) -> None:
        paths = [Path(r.absolute_path) for r in result.files if not r.read_error]
        records_by_path = {r.absolute_path: r for r in result.files}

        with ThreadPoolExecutor(max_workers=self.config.workers) as executor:
            futures = {
                executor.submit(
                    hash_file,
                    path,
                    self.config.max_file_size_bytes,
                ): path
                for path in paths
            }
            for future in as_completed(futures):
                path = futures[future]
                record = records_by_path[str(path)]
                try:
                    digest, error = future.result()
                    if error:
                        record.hash_error = error
                        result.errors += 1
                        log_file_issue(
                            self.logger,
                            level=logging.ERROR,
                            phase_id=InspectionPhase.HASH.value,
                            code="FILE_READ_ERROR",
                            path=record.relative_path,
                            message=error,
                        )
                    else:
                        record.sha256 = digest
                except Exception as exc:  # noqa: BLE001
                    record.hash_error = str(exc)
                    result.errors += 1

    def _phase_detect_issues(self, result: InspectionResult) -> None:
        processable = [r for r in result.files if not r.read_error]

        with ThreadPoolExecutor(max_workers=self.config.workers) as executor:
            futures = {
                executor.submit(self._analyze_file, Path(r.absolute_path), r): r
                for r in processable
            }
            for future in as_completed(futures):
                record = futures[future]
                try:
                    future.result()
                except Exception as exc:  # noqa: BLE001
                    record.read_error = str(exc)
                    result.errors += 1
                    log_file_issue(
                        self.logger,
                        level=logging.ERROR,
                        phase_id=InspectionPhase.DETECT_ISSUES.value,
                        code="FILE_READ_ERROR",
                        path=record.relative_path,
                        message=str(exc),
                    )

    def _analyze_file(self, path: Path, record) -> None:
        """Run format-specific analysis on a single file."""
        if record.zero_byte:
            record.corrupt = True
            return

        if record.format == "pdf":
            analysis = analyze_pdf(path)
            try:
                with path.open("rb") as handle:
                    header = handle.read(4)
            except OSError:
                header = b""
            if analysis.corrupted and header == b"PK\x03\x04":
                analysis = analyze_docx(path)
                record.format = "docx"
                record.docx_analysis = analysis
                record.corrupt = analysis.corrupted
                record.metadata = analysis.metadata
                record.metadata_available = analysis.metadata_available
                if analysis.paragraph_count_estimate is not None:
                    record.page_count = max(1, analysis.paragraph_count_estimate // 40)
                if analysis.error:
                    self._count_warning_or_error(record, analysis.error)
                return
            record.pdf_analysis = analysis
            record.corrupt = analysis.corrupted
            record.password_protected = analysis.encrypted
            record.page_count = analysis.page_count
            record.metadata = analysis.metadata
            record.metadata_available = analysis.metadata_available
            record.ocr_signal = analysis.ocr_signal
            if analysis.error:
                self._count_warning_or_error(record, analysis.error)
            return

        if record.format == "docx":
            analysis = analyze_docx(path)
            record.docx_analysis = analysis
            record.corrupt = analysis.corrupted
            record.metadata = analysis.metadata
            record.metadata_available = analysis.metadata_available
            if analysis.paragraph_count_estimate is not None:
                record.page_count = max(1, analysis.paragraph_count_estimate // 40)
            if analysis.error:
                self._count_warning_or_error(record, analysis.error)
            return

        if record.format == "txt":
            self._analyze_txt(path, record)

    def _analyze_txt(self, path: Path, record) -> None:
        try:
            raw = path.read_bytes()
        except OSError as exc:
            record.read_error = str(exc)
            return

        if b"\x00" in raw:
            record.encoding_error = True

        try:
            text = raw.decode("utf-8")
            record.metadata_available = True
            record.metadata = {
                "encoding": "utf-8",
                "line_count": text.count("\n") + (1 if text else 0),
            }
        except UnicodeDecodeError:
            record.encoding_error = True
            return

        has_crlf = "\r\n" in text
        has_lf = "\n" in text and not has_crlf
        has_cr = "\r" in text.replace("\r\n", "")
        endings = sum([has_crlf, has_lf, has_cr])
        record.mixed_line_endings = endings > 1

    def _count_warning_or_error(self, record, message: str) -> None:
        del record, message

    def _phase_sample(self, result: InspectionResult) -> None:
        selected, method = select_sample_files(
            result.files,
            rate=self.config.sampling_rate,
            min_samples=self.config.min_samples,
            max_samples=self.config.max_samples,
        )
        result.selected_sample_files = selected
        self._sampling_method = method

    def _phase_score(self, result: InspectionResult) -> None:
        result.duplicate_groups, result.hash_entries = detect_hash_duplicates(result.files)
        result.filename_duplicate_groups = detect_filename_duplicates(result.files)
        result.stats = compute_statistics(result.files, result.duplicate_groups, self.config.doc_type)
        result.quality = assess_quality(
            result.files,
            result.stats,
            result.duplicate_groups,
            result.filename_duplicate_groups,
        )
        result.warnings = sum(
            1
            for finding in result.quality.findings
            if finding.get("severity") == "warning"
        )

    def _phase_emit(self, result: InspectionResult) -> None:
        created_at = isoformat_datetime(result.completed_at or utc_now())
        config_snapshot = self.config.snapshot()

        manifest = build_manifest(
            result,
            config_snapshot,
            dataset_id=self.config.dataset_id,
            dataset_version=self.config.dataset_version,
            dataset_name=self.config.dataset_name,
            doc_type=self.config.doc_type,
            factory_version=FACTORY_VERSION,
            status=result.status,
        )
        profile = build_profile(
            result,
            result.stats,
            dataset_id=self.config.dataset_id,
            dataset_version=self.config.dataset_version,
            dataset_name=self.config.dataset_name,
            sampling_method=getattr(self, "_sampling_method", "stratified_by_format_hash_bucket"),
            sampling_rate=self.config.sampling_rate,
        )
        statistics = statistics_to_dict(
            result.stats,
            run_id=result.run_id,
            dataset_id=self.config.dataset_id,
            dataset_version=self.config.dataset_version,
            created_at=created_at,
        )
        quality = quality_to_dict(
            result.quality,
            run_id=result.run_id,
            dataset_id=self.config.dataset_id,
            dataset_version=self.config.dataset_version,
            created_at=created_at,
        )
        hash_index = build_hash_index(
            result,
            result.duplicate_groups,
            result.hash_entries,
            dataset_id=self.config.dataset_id,
            dataset_version=self.config.dataset_version,
        )

        if self.config.dry_run:
            self.logger.info("Dry run — skipping artifact write to %s", self.config.output_path)
            result.artifacts_written = []
            return

        output_path = self.config.output_path
        if not output_path.exists():
            output_path.mkdir(parents=True, exist_ok=True)
        elif not output_path.is_dir():
            raise NotADirectoryError(f"OUTPUT_NOT_WRITABLE: {output_path}")

        artifacts = {
            "dataset_manifest.yaml": manifest,
            "dataset_profile.yaml": profile,
            "statistics.yaml": statistics,
            "quality_report.yaml": quality,
            "hash_index.json": hash_index,
        }
        written = write_artifacts(output_path, artifacts)

        inspection_log = build_inspection_log(
            result,
            config_snapshot,
            dataset_id=self.config.dataset_id,
            dataset_version=self.config.dataset_version,
            factory_version=FACTORY_VERSION,
            artifacts_written=written,
        )
        from .reporting.writer import write_yaml

        write_yaml(output_path / "inspection_log.yaml", inspection_log)
        written.append("inspection_log.yaml")
        result.artifacts_written = written
        self.logger.info("Wrote %d artifacts to %s", len(written), output_path)
