"""
AI Video Factory - Repair Engine with Escalation
Surgical repairs that re-enter appropriate QC gates.
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from core.config import config
from core.logging import log
from core.state_machine import RunStateMachine, RunState
from core.checkpoint import CheckpointManager, CheckpointManifest


class FailureSeverity(Enum):
    MINOR = "minor"      # single asset/scene issue
    MAJOR = "major"      # multiple scenes, script issue
    CRITICAL = "critical"  # topic fundamentally broken


class FailureCategory(Enum):
    TECHNICAL_BLACK_FRAME = "TECHNICAL_BLACK_FRAME"
    TECHNICAL_FREEZE_FRAME = "TECHNICAL_FREEZE_FRAME"
    TECHNICAL_CORRUPTION = "TECHNICAL_CORRUPTION"
    TECHNICAL_DURATION = "TECHNICAL_DURATION"
    TECHNICAL_LUFS = "TECHNICAL_LUFS"
    TECHNICAL_RESOLUTION = "TECHNICAL_RESOLUTION"
    TECHNICAL_CAPTION_TIMING = "TECHNICAL_CAPTION_TIMING"
    TECHNICAL_MISSING_SCENE = "TECHNICAL_MISSING_SCENE"
    TECHNICAL_MISSING_ASSET = "TECHNICAL_MISSING_ASSET"
    EDITORIAL_UNSUPPORTED_CLAIM = "EDITORIAL_UNSUPPORTED_CLAIM"
    EDITORIAL_VISUAL_MISMATCH = "EDITORIAL_VISUAL_MISMATCH"
    EDITORIAL_HOOK_MISMATCH = "EDITORIAL_HOOK_MISMATCH"
    EDITORIAL_FABRICATED_EVIDENCE = "EDITORIAL_FABRICATED_EVIDENCE"
    EDITORIAL_MISLEADING_ARCHIVAL = "EDITORIAL_MISLEADING_ARCHIVAL"
    EDITORIAL_VISUAL_SLUDGE = "EDITORIAL_VISUAL_SLUDGE"
    EDITORIAL_COHERENCE = "EDITORIAL_COHERENCE"
    EDITORIAL_ENDING_MISMATCH = "EDITORIAL_ENDING_MISMATCH"


@dataclass
class FailureReport:
    """Structured failure report for repair planning."""
    attempt: int
    gate: str  # "QC1" or "QC2" or "FINAL_VERIFY"
    failure_id: str
    category: FailureCategory
    severity: FailureSeverity
    affected_components: List[str]  # scene IDs, asset IDs, script sections
    root_cause: str
    suggested_repair: str
    repair_strategy: str
    previous_attempts: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)


class RepairStrategy(Enum):
    REPLACE_ASSET = "REPLACE_ASSET"           # single asset swap
    REPLACE_SCENE = "REPLACE_SCENE"           # single scene re-render
    REPLACE_AUDIO = "REPLACE_AUDIO"           # voice/mastering redo
    REWRITE_SCRIPT_SECTION = "REWRITE_SCRIPT_SECTION"  # surgical script edit
    REWRITE_FULL_SCRIPT = "REWRITE_FULL_SCRIPT"  # full script regeneration
    REGENERATE_HOOK = "REGENERATE_HOOK"       # new hook selection
    RESEARCH_CLAIM = "RESEARCH_CLAIM"         # deeper source verification
    REPLACE_VISUAL_EVIDENCE = "REPLACE_VISUAL_EVIDENCE"  # new asset search
    CHANGE_STORY_ANGLE = "CHANGE_STORY_ANGLE"  # different narrative approach
    DEFER_TOPIC = "DEFER_TOPIC"               # topic impossible, try next


# Repair escalation ladder - each failure tries next strategy
REPAIR_ESCALATION: Dict[FailureCategory, List[RepairStrategy]] = {
    FailureCategory.TECHNICAL_BLACK_FRAME: [
        RepairStrategy.REPLACE_ASSET,
        RepairStrategy.REPLACE_SCENE,
        RepairStrategy.REPLACE_VISUAL_EVIDENCE,
        RepairStrategy.DEFER_TOPIC,
    ],
    FailureCategory.TECHNICAL_FREEZE_FRAME: [
        RepairStrategy.REPLACE_ASSET,
        RepairStrategy.REPLACE_SCENE,
        RepairStrategy.REPLACE_VISUAL_EVIDENCE,
        RepairStrategy.DEFER_TOPIC,
    ],
    FailureCategory.TECHNICAL_CORRUPTION: [
        RepairStrategy.REPLACE_ASSET,
        RepairStrategy.REPLACE_SCENE,
        RepairStrategy.DEFER_TOPIC,
    ],
    FailureCategory.TECHNICAL_DURATION: [
        RepairStrategy.REPLACE_AUDIO,
        RepairStrategy.REWRITE_SCRIPT_SECTION,
        RepairStrategy.REWRITE_FULL_SCRIPT,
        RepairStrategy.DEFER_TOPIC,
    ],
    FailureCategory.TECHNICAL_LUFS: [
        RepairStrategy.REPLACE_AUDIO,
        RepairStrategy.DEFER_TOPIC,
    ],
    FailureCategory.TECHNICAL_RESOLUTION: [
        RepairStrategy.REPLACE_ASSET,
        RepairStrategy.REPLACE_SCENE,
        RepairStrategy.DEFER_TOPIC,
    ],
    FailureCategory.TECHNICAL_CAPTION_TIMING: [
        RepairStrategy.REPLACE_AUDIO,
        RepairStrategy.REWRITE_SCRIPT_SECTION,
        RepairStrategy.DEFER_TOPIC,
    ],
    FailureCategory.TECHNICAL_MISSING_SCENE: [
        RepairStrategy.REPLACE_SCENE,
        RepairStrategy.REWRITE_FULL_SCRIPT,
        RepairStrategy.DEFER_TOPIC,
    ],
    FailureCategory.TECHNICAL_MISSING_ASSET: [
        RepairStrategy.REPLACE_VISUAL_EVIDENCE,
        RepairStrategy.REPLACE_ASSET,
        RepairStrategy.DEFER_TOPIC,
    ],
    FailureCategory.EDITORIAL_UNSUPPORTED_CLAIM: [
        RepairStrategy.RESEARCH_CLAIM,
        RepairStrategy.REWRITE_SCRIPT_SECTION,
        RepairStrategy.REWRITE_FULL_SCRIPT,
        RepairStrategy.DEFER_TOPIC,
    ],
    FailureCategory.EDITORIAL_VISUAL_MISMATCH: [
        RepairStrategy.REPLACE_VISUAL_EVIDENCE,
        RepairStrategy.REPLACE_SCENE,
        RepairStrategy.CHANGE_STORY_ANGLE,
        RepairStrategy.DEFER_TOPIC,
    ],
    FailureCategory.EDITORIAL_HOOK_MISMATCH: [
        RepairStrategy.REGENERATE_HOOK,
        RepairStrategy.REWRITE_FULL_SCRIPT,
        RepairStrategy.CHANGE_STORY_ANGLE,
        RepairStrategy.DEFER_TOPIC,
    ],
    FailureCategory.EDITORIAL_FABRICATED_EVIDENCE: [
        RepairStrategy.RESEARCH_CLAIM,
        RepairStrategy.REWRITE_SCRIPT_SECTION,
        RepairStrategy.REWRITE_FULL_SCRIPT,
        RepairStrategy.DEFER_TOPIC,
    ],
    FailureCategory.EDITORIAL_MISLEADING_ARCHIVAL: [
        RepairStrategy.REPLACE_VISUAL_EVIDENCE,
        RepairStrategy.REPLACE_SCENE,
        RepairStrategy.DEFER_TOPIC,
    ],
    FailureCategory.EDITORIAL_VISUAL_SLUDGE: [
        RepairStrategy.REPLACE_VISUAL_EVIDENCE,
        RepairStrategy.CHANGE_STORY_ANGLE,
        RepairStrategy.DEFER_TOPIC,
    ],
    FailureCategory.EDITORIAL_COHERENCE: [
        RepairStrategy.REWRITE_SCRIPT_SECTION,
        RepairStrategy.REWRITE_FULL_SCRIPT,
        RepairStrategy.CHANGE_STORY_ANGLE,
        RepairStrategy.DEFER_TOPIC,
    ],
    FailureCategory.EDITORIAL_ENDING_MISMATCH: [
        RepairStrategy.REWRITE_SCRIPT_SECTION,
        RepairStrategy.REWRITE_FULL_SCRIPT,
        RepairStrategy.DEFER_TOPIC,
    ],
}


class RepairEngine:
    """
    Surgical repair engine with escalation.
    Every failure produces a structured report, selects minimal repair,
    executes it, and re-enters the appropriate QC gate.
    """

    def __init__(self, run_id: str, state_machine: RunStateMachine, checkpoint: CheckpointManager):
        self.run_id = run_id
        self.state_machine = state_machine
        self.checkpoint = checkpoint
        self.failure_history: List[FailureReport] = []
        self.failure_dir = config.storage.state_dir / "runs" / run_id / "failures"
        self.failure_dir.mkdir(parents=True, exist_ok=True)

    def analyze_failure(self, gate: str, qc_result: Dict[str, Any], context: Dict[str, Any]) -> FailureReport:
        """Analyze QC failure and produce structured failure report."""
        failures = []

        # QC1 Technical failures
        if gate == "QC1":
            if qc_result.get("black_frame_count", 0) > 0:
                failures.append(FailureCategory.TECHNICAL_BLACK_FRAME)
            if qc_result.get("freeze_frame_count", 0) > 0:
                failures.append(FailureCategory.TECHNICAL_FREEZE_FRAME)
            if not qc_result.get("duration_pass", True):
                failures.append(FailureCategory.TECHNICAL_DURATION)
            if not qc_result.get("lufs_pass", True):
                failures.append(FailureCategory.TECHNICAL_LUFS)
            if not qc_result.get("resolution_pass", True):
                failures.append(FailureCategory.TECHNICAL_RESOLUTION)
            if qc_result.get("layer1_count", 0) < qc_result.get("total_scenes", 0):
                failures.append(FailureCategory.TECHNICAL_MISSING_SCENE)
            if qc_result.get("layer2_count", 0) < qc_result.get("total_scenes", 0):
                failures.append(FailureCategory.TECHNICAL_MISSING_ASSET)

        # QC2 Editorial failures
        elif gate == "QC2":
            if context.get("unsupported_claims", 0) > 0:
                failures.append(FailureCategory.EDITORIAL_UNSUPPORTED_CLAIM)
            if context.get("visual_mismatch_scenes"):
                failures.append(FailureCategory.EDITORIAL_VISUAL_MISMATCH)
            if context.get("hook_mismatch", False):
                failures.append(FailureCategory.EDITORIAL_HOOK_MISMATCH)
            if context.get("fabricated_evidence", False):
                failures.append(FailureCategory.EDITORIAL_FABRICATED_EVIDENCE)
            if context.get("misleading_archival", False):
                failures.append(FailureCategory.EDITORIAL_MISLEADING_ARCHIVAL)
            if context.get("visual_sludge", False):
                failures.append(FailureCategory.EDITORIAL_VISUAL_SLUDGE)
            if context.get("coherence_fail", False):
                failures.append(FailureCategory.EDITORIAL_COHERENCE)
            if context.get("ending_mismatch", False):
                failures.append(FailureCategory.EDITORIAL_ENDING_MISMATCH)

        if not failures:
            # Generic fallback
            failures.append(FailureCategory.TECHNICAL_CORRUPTION)

        # Pick primary failure (most severe)
        primary = failures[0]

        # Determine severity
        if primary in (FailureCategory.TECHNICAL_BLACK_FRAME, FailureCategory.TECHNICAL_FREEZE_FRAME):
            severity = FailureSeverity.MINOR
        elif primary in (FailureCategory.EDITORIAL_UNSUPPORTED_CLAIM, FailureCategory.EDITORIAL_VISUAL_MISMATCH):
            severity = FailureSeverity.MAJOR
        else:
            severity = FailureSeverity.MAJOR

        # Select repair strategy based on escalation
        strategies = REPAIR_ESCALATION.get(primary, [RepairStrategy.DEFER_TOPIC])
        strategy = strategies[min(self.state_machine.attempt_count, len(strategies) - 1)]

        # Build failure report
        report = FailureReport(
            attempt=self.state_machine.attempt_count + 1,
            gate=gate,
            failure_id=f"{primary.value}_{self.state_machine.attempt_count + 1}",
            category=primary,
            severity=severity,
            affected_components=context.get("affected_components", []),
            root_cause=self._diagnose_root_cause(primary, context),
            suggested_repair=strategy.value,
            repair_strategy=strategy.value,
            previous_attempts=self.state_machine.attempt_count,
            metadata=context,
        )

        self.failure_history.append(report)
        self._save_failure_report(report)
        self.state_machine.enter_repair(
            failure_id=report.failure_id,
            severity=severity.value,
            affected_components=report.affected_components,
            root_cause=report.root_cause
        )

        return report

    def _diagnose_root_cause(self, category: FailureCategory, context: Dict[str, Any]) -> str:
        """Generate human-readable root cause."""
        causes = {
            FailureCategory.TECHNICAL_BLACK_FRAME: f"Scene {context.get('black_frame_scene', 'unknown')} produced black frames - likely asset download/corruption or FFmpeg filter error",
            FailureCategory.TECHNICAL_FREEZE_FRAME: f"Scene {context.get('freeze_frame_scene', 'unknown')} has frozen frames - likely static image with insufficient motion or FFmpeg concat issue",
            FailureCategory.TECHNICAL_DURATION: f"Final duration {context.get('duration', 'unknown')}s outside 30-40s bounds - script timing or audio/mastering mismatch",
            FailureCategory.TECHNICAL_LUFS: f"Measured LUFS {context.get('lufs', 'unknown')} outside ±1 LU of -14 target - mastering filter parameter issue",
            FailureCategory.TECHNICAL_RESOLUTION: f"Output resolution {context.get('resolution', 'unknown')} not 1080x1920 - compositor scaling issue",
            FailureCategory.TECHNICAL_CAPTION_TIMING: "ASS caption timing drift - word boundary sync failure",
            FailureCategory.TECHNICAL_MISSING_SCENE: f"Scene {context.get('missing_scene', 'unknown')} missing from render - scene planner or asset harvest failure",
            FailureCategory.TECHNICAL_MISSING_ASSET: f"Asset for scene {context.get('missing_asset_scene', 'unknown')} not harvested - media preflight undercounted",
            FailureCategory.EDITORIAL_UNSUPPORTED_CLAIM: f"Script claim '{context.get('unsupported_claim', 'unknown')}' not grounded in source text",
            FailureCategory.EDITORIAL_VISUAL_MISMATCH: f"Scene {context.get('mismatch_scene', 'unknown')} visual doesn't support claim - relevance scoring failure",
            FailureCategory.EDITORIAL_HOOK_MISMATCH: "Selected hook doesn't match script narrative - hook scoring misaligned with script content",
            FailureCategory.EDITORIAL_FABRICATED_EVIDENCE: "Script contains dates/names/coordinates not in verified source - hallucination in script generation",
            FailureCategory.EDITORIAL_MISLEADING_ARCHIVAL: "Asset presented as primary evidence but is atmospheric/contextual - visual purpose mismatch",
            FailureCategory.EDITORIAL_VISUAL_SLUDGE: "Too many generated graphics or low-relevance assets - asset harvest quality gates failed",
            FailureCategory.EDITORIAL_COHERENCE: "Script narrative flow broken - scene planner beat division or script structure issue",
            FailureCategory.EDITORIAL_ENDING_MISMATCH: "Script ending question not supported by preceding evidence - claim verification gap",
        }
        return causes.get(category, f"Uncategorized failure: {category.value}")

    def _save_failure_report(self, report: FailureReport):
        """Save failure report to run directory."""
        report_file = self.failure_dir / f"failure_{report.attempt:03d}_{report.failure_id}.json"
        report_file.write_text(json.dumps(asdict(report), indent=2, default=str), encoding="utf-8")

    def execute_repair(self, report: FailureReport, pipeline_functions: Dict[str, Callable]) -> Dict[str, Any]:
        """
        Execute the selected repair strategy.
        Returns context updates for pipeline continuation.
        """
        strategy = RepairStrategy(report.repair_strategy)
        log.info(f"REPAIR [{report.attempt}]: {strategy.value} for {report.failure_id}")

        try:
            if strategy == RepairStrategy.REPLACE_ASSET:
                return self._repair_replace_asset(report, pipeline_functions)
            elif strategy == RepairStrategy.REPLACE_SCENE:
                return self._repair_replace_scene(report, pipeline_functions)
            elif strategy == RepairStrategy.REPLACE_AUDIO:
                return self._repair_replace_audio(report, pipeline_functions)
            elif strategy == RepairStrategy.REWRITE_SCRIPT_SECTION:
                return self._repair_rewrite_script_section(report, pipeline_functions)
            elif strategy == RepairStrategy.REWRITE_FULL_SCRIPT:
                return self._repair_rewrite_full_script(report, pipeline_functions)
            elif strategy == RepairStrategy.REGENERATE_HOOK:
                return self._repair_regenerate_hook(report, pipeline_functions)
            elif strategy == RepairStrategy.RESEARCH_CLAIM:
                return self._repair_research_claim(report, pipeline_functions)
            elif strategy == RepairStrategy.REPLACE_VISUAL_EVIDENCE:
                return self._repair_replace_visual_evidence(report, pipeline_functions)
            elif strategy == RepairStrategy.CHANGE_STORY_ANGLE:
                return self._repair_change_story_angle(report, pipeline_functions)
            elif strategy == RepairStrategy.DEFER_TOPIC:
                return self._repair_defer_topic(report, pipeline_functions)
            else:
                raise ValueError(f"Unknown repair strategy: {strategy}")
        except Exception as e:
            log.error(f"REPAIR FAILED: {strategy.value} - {e}")
            raise

    def _repair_replace_asset(self, report: FailureReport, funcs: Dict) -> Dict:
        """Replace single problematic asset."""
        scene_id = report.affected_components[0] if report.affected_components else None
        # Re-run asset harvest for just this scene
        new_scene = funcs["re_harvest_scene"](scene_id)
        return {"replaced_scene": new_scene, "repair_type": "asset"}

    def _repair_replace_scene(self, report: FailureReport, funcs: Dict) -> Dict:
        """Re-render single problematic scene."""
        scene_id = report.affected_components[0] if report.affected_components else None
        new_scene = funcs["re_render_scene"](scene_id)
        return {"replaced_scene": new_scene, "repair_type": "scene"}

    def _repair_replace_audio(self, report: FailureReport, funcs: Dict) -> Dict:
        """Re-generate voice + mastering."""
        new_audio = funcs["re_generate_audio"]()
        return {"new_audio_path": new_audio, "repair_type": "audio"}

    def _repair_rewrite_script_section(self, report: FailureReport, funcs: Dict) -> Dict:
        """Surgical rewrite of problematic script section."""
        new_script = funcs["rewrite_script_section"](report.affected_components)
        return {"new_script": new_script, "repair_type": "script_section"}

    def _repair_rewrite_full_script(self, report: FailureReport, funcs: Dict) -> Dict:
        """Full script regeneration with new constraints."""
        new_script = funcs["regenerate_script"](context={"repair": report.failure_id})
        return {"new_script": new_script, "repair_type": "full_script"}

    def _repair_regenerate_hook(self, report: FailureReport, funcs: Dict) -> Dict:
        """Select next best hook and regenerate script."""
        new_hook = funcs["select_next_hook"]()
        new_script = funcs["regenerate_script"](context={"new_hook": new_hook})
        return {"new_hook": new_hook, "new_script": new_script, "repair_type": "hook"}

    def _repair_research_claim(self, report: FailureReport, funcs: Dict) -> Dict:
        """Deeper source verification for unsupported claim."""
        verified_facts = funcs["verify_claim"](report.affected_components[0])
        return {"verified_facts": verified_facts, "repair_type": "research"}

    def _repair_replace_visual_evidence(self, report: FailureReport, funcs: Dict) -> Dict:
        """Search for new visual evidence for claim."""
        new_assets = funcs["search_new_evidence"](report.affected_components[0])
        return {"new_assets": new_assets, "repair_type": "visual_evidence"}

    def _repair_change_story_angle(self, report: FailureReport, funcs: Dict) -> Dict:
        """Try different narrative angle on same topic."""
        new_script = funcs["regenerate_script"](context={"new_angle": True})
        return {"new_script": new_script, "repair_type": "story_angle"}

    def _repair_defer_topic(self, report: FailureReport, funcs: Dict) -> Dict:
        """Defer to next topic candidate."""
        has_next = self.state_machine.defer_to_next_topic()
        return {"deferred": True, "has_next": has_next, "repair_type": "defer_topic"}


class RepairEscalationManager:
    """
    Manages repair escalation logic:
    - Tracks attempts per failure category
    - Enforces escalation ladder
    - Decides when to defer topic
    """

    def __init__(self, repair_engine: RepairEngine):
        self.engine = repair_engine
        self.category_attempts: Dict[FailureCategory, int] = {}

    def should_escalate(self, report: FailureReport) -> bool:
        """Check if current strategy failed and we should escalate."""
        self.category_attempts[report.category] = self.category_attempts.get(report.category, 0) + 1
        strategies = REPAIR_ESCALATION.get(report.category, [])
        current_index = min(self.category_attempts[report.category] - 1, len(strategies) - 1)
        return current_index + 1 < len(strategies)

    def get_next_strategy(self, category: FailureCategory) -> RepairStrategy:
        """Get next strategy in escalation ladder."""
        strategies = REPAIR_ESCALATION.get(category, [RepairStrategy.DEFER_TOPIC])
        attempts = self.category_attempts.get(category, 0)
        return strategies[min(attempts, len(strategies) - 1)]

    def is_exhausted(self, category: FailureCategory) -> bool:
        """Check if all strategies exhausted for this category."""
        strategies = REPAIR_ESCALATION.get(category, [RepairStrategy.DEFER_TOPIC])
        attempts = self.category_attempts.get(category, 0)
        return attempts >= len(strategies)