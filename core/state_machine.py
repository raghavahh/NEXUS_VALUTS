"""
AI Video Factory - Explicit State Machine
Enforces ALLOWED transitions only (whitelist). Anything not explicitly allowed = hard failure.
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Set
from pathlib import Path
import json
from core.config import config
from core.logging import log


class RunState(Enum):
    """Explicit run states with enforced transitions."""
    RUN_CREATED = "RUN_CREATED"
    PREFLIGHT = "PREFLIGHT"
    DISCOVERING = "DISCOVERING"
    FILTERING = "FILTERING"
    SCORING = "SCORING"
    SHORTLISTED = "SHORTLISTED"
    DEEP_ANALYSIS = "DEEP_ANALYSIS"
    SELECTED = "SELECTED"

    RESEARCHING = "RESEARCHING"
    CLAIM_VERIFICATION = "CLAIM_VERIFICATION"
    HOOK_GENERATION = "HOOK_GENERATION"
    SCRIPTING = "SCRIPTING"
    SCRIPT_QC = "SCRIPT_QC"

    SCENE_PLANNING = "SCENE_PLANNING"
    MEDIA_PREFLIGHT = "MEDIA_PREFLIGHT"
    MEDIA_HARVEST = "MEDIA_HARVEST"
    AUDIO_GENERATION = "AUDIO_GENERATION"
    RENDERING = "RENDERING"

    QC1 = "QC1"
    QC1_FAILED = "QC1_FAILED"
    QC1_REPAIR = "QC1_REPAIR"

    QC2 = "QC2"
    QC2_FAILED = "QC2_FAILED"
    QC2_REPAIR = "QC2_REPAIR"

    FINAL_VERIFY = "FINAL_VERIFY"
    FINAL_VERIFY_FAILED = "FINAL_VERIFY_FAILED"
    READY_TO_PUBLISH = "READY_TO_PUBLISH"
    UPLOADING = "UPLOADING"
    UPLOAD_VERIFY = "UPLOAD_VERIFY"

    PUBLISHED = "PUBLISHED"
    ANALYTICS_PENDING = "ANALYTICS_PENDING"
    LEARNING = "LEARNING"
    COMPLETED = "COMPLETED"

    TOPIC_DEFERRED = "TOPIC_DEFERRED"
    RUN_FAILED = "RUN_FAILED"


# EXPLICIT ALLOWED TRANSITIONS (whitelist) - anything not listed = hard failure
ALLOWED_TRANSITIONS: Dict[RunState, Set[RunState]] = {
    RunState.RUN_CREATED: {RunState.PREFLIGHT},
    RunState.PREFLIGHT: {RunState.DISCOVERING, RunState.RUN_FAILED},
    RunState.DISCOVERING: {RunState.FILTERING, RunState.SCORING, RunState.SHORTLISTED, RunState.DEEP_ANALYSIS, RunState.SELECTED, RunState.RUN_FAILED},
    RunState.FILTERING: {RunState.SCORING, RunState.SHORTLISTED, RunState.DEEP_ANALYSIS, RunState.SELECTED, RunState.RUN_FAILED},
    RunState.SCORING: {RunState.SHORTLISTED, RunState.RUN_FAILED},
    RunState.SHORTLISTED: {RunState.DEEP_ANALYSIS, RunState.RUN_FAILED},
    RunState.DEEP_ANALYSIS: {RunState.SELECTED, RunState.RUN_FAILED},
    RunState.SELECTED: {RunState.RESEARCHING, RunState.MEDIA_PREFLIGHT, RunState.TOPIC_DEFERRED},
    RunState.RESEARCHING: {RunState.CLAIM_VERIFICATION, RunState.TOPIC_DEFERRED},
    RunState.CLAIM_VERIFICATION: {RunState.HOOK_GENERATION, RunState.TOPIC_DEFERRED},
    RunState.HOOK_GENERATION: {RunState.SCRIPTING, RunState.TOPIC_DEFERRED},
    RunState.SCRIPTING: {RunState.SCRIPT_QC, RunState.TOPIC_DEFERRED},
    RunState.SCRIPT_QC: {RunState.SCENE_PLANNING, RunState.TOPIC_DEFERRED},
    RunState.SCENE_PLANNING: {RunState.MEDIA_PREFLIGHT, RunState.TOPIC_DEFERRED},
    RunState.MEDIA_PREFLIGHT: {RunState.MEDIA_HARVEST, RunState.TOPIC_DEFERRED},
    RunState.MEDIA_HARVEST: {RunState.AUDIO_GENERATION, RunState.TOPIC_DEFERRED},
    RunState.AUDIO_GENERATION: {RunState.RENDERING, RunState.TOPIC_DEFERRED},
    RunState.RENDERING: {RunState.QC1, RunState.TOPIC_DEFERRED},
    RunState.QC1: {RunState.QC2, RunState.QC1_FAILED},
    RunState.QC1_FAILED: {RunState.QC1_REPAIR, RunState.TOPIC_DEFERRED},
    RunState.QC1_REPAIR: {RunState.QC1},
    RunState.QC2: {RunState.FINAL_VERIFY, RunState.QC2_FAILED},
    RunState.QC2_FAILED: {RunState.QC2_REPAIR, RunState.TOPIC_DEFERRED},
    RunState.QC2_REPAIR: {RunState.QC1},
    RunState.FINAL_VERIFY: {RunState.READY_TO_PUBLISH, RunState.FINAL_VERIFY_FAILED},
    RunState.FINAL_VERIFY_FAILED: {RunState.RENDERING, RunState.TOPIC_DEFERRED},
    RunState.READY_TO_PUBLISH: {RunState.UPLOADING},
    RunState.UPLOADING: {RunState.UPLOAD_VERIFY},
    RunState.UPLOAD_VERIFY: {RunState.PUBLISHED},
    RunState.PUBLISHED: {RunState.ANALYTICS_PENDING},
    RunState.ANALYTICS_PENDING: {RunState.LEARNING},
    RunState.LEARNING: {RunState.COMPLETED},
    RunState.TOPIC_DEFERRED: {RunState.DISCOVERING, RunState.RUN_FAILED},
    RunState.RUN_FAILED: set(),
    RunState.COMPLETED: set(),
}


@dataclass
class StateTransition:
    """Single state transition record."""
    from_state: str
    to_state: str
    timestamp: str
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunStateMachine:
    """
    Explicit state machine for a production run.
    Persists every transition. Enforces ALLOWED transitions only.
    """
    run_id: str
    current_state: RunState = RunState.RUN_CREATED
    history: List[StateTransition] = field(default_factory=list)
    attempt_count: int = 0
    max_repair_attempts: int = 5
    repair_strategies_tried: List[str] = field(default_factory=list)
    topic_candidates: List[Dict[str, Any]] = field(default_factory=list)
    selected_topic_index: int = 0
    checkpoint_dir: Optional[Path] = None

    def __post_init__(self):
        self.checkpoint_dir = config.storage.state_dir / "runs" / self.run_id
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._persist()

    def _persist(self):
        state_file = self.checkpoint_dir / "state_machine.json"
        data = {
            "run_id": self.run_id,
            "current_state": self.current_state.value,
            "history": [
                {
                    "from_state": t.from_state,
                    "to_state": t.to_state,
                    "timestamp": t.timestamp,
                    "reason": t.reason,
                    "metadata": t.metadata,
                }
                for t in self.history
            ],
            "attempt_count": self.attempt_count,
            "max_repair_attempts": self.max_repair_attempts,
            "repair_strategies_tried": self.repair_strategies_tried,
            "topic_candidates": self.topic_candidates,
            "selected_topic_index": self.selected_topic_index,
        }
        state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, run_id: str) -> "RunStateMachine":
        checkpoint_dir = config.storage.state_dir / "runs" / run_id
        state_file = checkpoint_dir / "state_machine.json"
        if not state_file.exists():
            return cls(run_id=run_id)
        data = json.loads(state_file.read_text(encoding="utf-8"))
        history = [StateTransition(**h) for h in data.get("history", [])]
        return cls(
            run_id=data["run_id"],
            current_state=RunState(data["current_state"]),
            history=history,
            attempt_count=data.get("attempt_count", 0),
            max_repair_attempts=data.get("max_repair_attempts", 5),
            repair_strategies_tried=data.get("repair_strategies_tried", []),
            topic_candidates=data.get("topic_candidates", []),
            selected_topic_index=data.get("selected_topic_index", 0),
        )

    def transition(self, new_state: RunState, reason: str = "", metadata: Optional[Dict[str, Any]] = None) -> bool:
        allowed = ALLOWED_TRANSITIONS.get(self.current_state, set())
        if new_state not in allowed:
            raise ValueError(
                f"FORBIDDEN TRANSITION: {self.current_state.value} -> {new_state.value}. "
                f"Allowed from {self.current_state.value}: {', '.join(s.value for s in allowed)}. "
                f"Law 2: No failed stage can advance; only explicit whitelisted transitions permitted."
            )

        if new_state in (RunState.QC1_REPAIR, RunState.QC2_REPAIR):
            self.attempt_count += 1
            if self.attempt_count > self.max_repair_attempts:
                log.error(f"REPAIR ESCALATION: Max attempts ({self.max_repair_attempts}) exceeded. Deferring topic.")
                new_state = RunState.TOPIC_DEFERRED
                reason = f"Max repair attempts exceeded ({self.max_repair_attempts})"

        transition = StateTransition(
            from_state=self.current_state.value,
            to_state=new_state.value,
            timestamp=datetime.now(timezone.utc).isoformat(),
            reason=reason,
            metadata=metadata or {},
        )
        self.history.append(transition)
        self.current_state = new_state
        self._persist()
        log.info(f"STATE: {transition.from_state} -> {transition.to_state} [{reason}]")
        return True

    def can_transition(self, new_state: RunState) -> bool:
        allowed = ALLOWED_TRANSITIONS.get(self.current_state, set())
        return new_state in allowed

    def enter_repair(self, failure_id: str, severity: str, affected_components: List[str], root_cause: str) -> RunState:
        if self.current_state == RunState.QC1:
            repair_state = RunState.QC1_REPAIR
        elif self.current_state == RunState.QC2:
            repair_state = RunState.QC2_REPAIR
        elif self.current_state == RunState.FINAL_VERIFY:
            repair_state = RunState.QC1_REPAIR
        else:
            repair_state = RunState.QC1_REPAIR

        metadata = {
            "failure_id": failure_id,
            "severity": severity,
            "affected_components": affected_components,
            "root_cause": root_cause,
            "attempt": self.attempt_count + 1,
        }
        self.repair_strategies_tried.append(failure_id)
        self.transition(repair_state, reason=f"Repair: {failure_id}", metadata=metadata)
        return repair_state

    def post_repair_target(self) -> RunState:
        if self.current_state == RunState.QC1_REPAIR:
            return RunState.QC1
        elif self.current_state == RunState.QC2_REPAIR:
            return RunState.QC1
        return RunState.QC1

    def defer_to_next_topic(self) -> bool:
        if self.selected_topic_index + 1 < len(self.topic_candidates):
            self.selected_topic_index += 1
            self.attempt_count = 0
            self.repair_strategies_tried.clear()
            self.transition(RunState.MEDIA_PREFLIGHT, reason=f"Deferred to candidate #{self.selected_topic_index + 1}")
            return True
        return False
