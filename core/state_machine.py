"""
AI Video Factory - Explicit State Machine
Enforces allowed/forbidden transitions. Every run is a state machine instance.
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List, Set
from pathlib import Path
import json
import os
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


# Forbidden transitions - these MUST be blocked in code
FORBIDDEN_TRANSITIONS: Dict[RunState, Set[RunState]] = {
    RunState.QC1: {RunState.QC2, RunState.FINAL_VERIFY, RunState.READY_TO_PUBLISH, RunState.UPLOADING},
    RunState.QC1_FAILED: {RunState.QC2, RunState.FINAL_VERIFY, RunState.READY_TO_PUBLISH, RunState.UPLOADING},
    RunState.QC2: {RunState.PUBLISHED, RunState.UPLOADING},
    RunState.QC2_FAILED: {RunState.FINAL_VERIFY, RunState.READY_TO_PUBLISH, RunState.UPLOADING, RunState.PUBLISHED},
    RunState.FINAL_VERIFY: {RunState.PUBLISHED, RunState.UPLOADING},
    RunState.FINAL_VERIFY_FAILED: {RunState.READY_TO_PUBLISH, RunState.UPLOADING, RunState.PUBLISHED},
    RunState.UPLOADING: {RunState.PUBLISHED},  # must pass UPLOAD_VERIFY first
}

# Allowed repair transitions - repair always re-enters appropriate QC
REPAIR_TRANSITIONS: Dict[RunState, RunState] = {
    RunState.QC1: RunState.QC1_REPAIR,
    RunState.QC2: RunState.QC2_REPAIR,
    RunState.FINAL_VERIFY: RunState.RENDERING,  # editorial repair may need full re-render
}

# After repair, where to go
POST_REPAIR_TARGET: Dict[RunState, RunState] = {
    RunState.QC1_REPAIR: RunState.QC1,
    RunState.QC2_REPAIR: RunState.QC2,
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
    Persists every transition. Enforces forbidden transitions.
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
        """Save state machine to checkpoint directory."""
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
        """Load state machine from checkpoint."""
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
        """
        Attempt state transition. Returns True if allowed, False if forbidden.
        Raises ValueError if transition is forbidden by law.
        """
        # Check forbidden transitions
        if self.current_state in FORBIDDEN_TRANSITIONS:
            if new_state in FORBIDDEN_TRANSITIONS[self.current_state]:
                raise ValueError(
                    f"FORBIDDEN TRANSITION: {self.current_state.value} → {new_state.value}. "
                    f"Law 2: No failed stage can advance."
                )

        # Check repair escalation limit
        if new_state in (RunState.QC1_REPAIR, RunState.QC2_REPAIR):
            self.attempt_count += 1
            if self.attempt_count > self.max_repair_attempts:
                log.error(f"REPAIR ESCALATION: Max attempts ({self.max_repair_attempts}) exceeded. Deferring topic.")
                new_state = RunState.TOPIC_DEFERRED
                reason = f"Max repair attempts exceeded ({self.max_repair_attempts})"

        # Record transition
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
        log.info(f"STATE: {transition.from_state} → {transition.to_state} [{reason}]")
        return True

    def can_transition(self, new_state: RunState) -> bool:
        """Check if transition is allowed without performing it."""
        if self.current_state in FORBIDDEN_TRANSITIONS:
            if new_state in FORBIDDEN_TRANSITIONS[self.current_state]:
                return False
        return True

    def enter_repair(self, failure_id: str, severity: str, affected_components: List[str], root_cause: str) -> RunState:
        """Enter appropriate repair state with failure metadata."""
        if self.current_state == RunState.QC1:
            repair_state = RunState.QC1_REPAIR
        elif self.current_state == RunState.QC2:
            repair_state = RunState.QC2_REPAIR
        elif self.current_state == RunState.FINAL_VERIFY:
            repair_state = RunState.QC1_REPAIR  # editorial repair may need re-render
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
        """Get the target state after repair completes."""
        if self.current_state == RunState.QC1_REPAIR:
            return RunState.QC1
        elif self.current_state == RunState.QC2_REPAIR:
            return RunState.QC2
        return RunState.QC1

    def defer_to_next_topic(self) -> bool:
        """Try next topic candidate. Returns True if another candidate exists."""
        if self.selected_topic_index + 1 < len(self.topic_candidates):
            self.selected_topic_index += 1
            self.attempt_count = 0
            self.repair_strategies_tried.clear()
            self.transition(RunState.MEDIA_PREFLIGHT, reason=f"Deferred to candidate #{self.selected_topic_index + 1}")
            return True
        return False


# Timezone import
from datetime import timezone