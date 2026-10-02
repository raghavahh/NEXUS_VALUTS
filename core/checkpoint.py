"""
AI Video Factory - Checkpoint System
Per-stage artifact preservation with immutable attempt directories.
"""

import shutil
import hashlib
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from core.config import config
from core.logging import log


@dataclass
class CheckpointManifest:
    """Manifest for a checkpoint/attempt."""
    run_id: str
    attempt_number: int
    stage: str
    timestamp: str
    artifacts: List[str] = field(default_factory=list)
    file_hashes: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: str = "IN_PROGRESS"  # IN_PROGRESS, COMPLETED, FAILED


class CheckpointManager:
    """
    Manages per-stage checkpoints with immutable attempt directories.
    Structure:
    .factory_state/runs/RUN_ID/
    ├── state_machine.json
    ├── discovery/
    │   ├── candidates.json
    │   └── rankings.json
    ├── selected/
    │   └── topic.json
    ├── research/
    │   ├── sources.json
    │   └── claims.json
    ├── script/
    │   ├── hooks.json
    │   └── script.json
    ├── scenes/
    │   └── scenes.json
    ├── attempts/
    │   ├── 001/
    │   │   ├── master.mp4
    │   │   ├── manifest.json
    │   │   ├── hashes.json
    │   │   ├── contact_sheet.jpg
    │   │   └── qc_reports/
    │   ├── 002/
    │   └── ...
    ├── qc/
    │   ├── qc1/
    │   ├── qc2/
    │   └── final/
    └── final/
        ├── master.mp4
        ├── manifest.json
        └── hashes.json
    """

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.base_dir = config.storage.state_dir / "runs" / run_id
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.attempts_dir = self.base_dir / "attempts"
        self.attempts_dir.mkdir(exist_ok=True)

    def stage_dir(self, stage: str) -> Path:
        """Get directory for a pipeline stage checkpoint."""
        d = self.base_dir / stage
        d.mkdir(parents=True, exist_ok=True)
        return d

    def new_attempt(self) -> Path:
        """Create new immutable attempt directory with next number."""
        existing = sorted(self.attempts_dir.iterdir())
        attempt_num = len(existing) + 1
        attempt_dir = self.attempts_dir / f"{attempt_num:03d}"
        attempt_dir.mkdir(parents=True, exist_ok=True)
        return attempt_dir

    def save_stage_checkpoint(self, stage: str, filename: str, data: Any) -> Path:
        """Save a stage checkpoint file (JSON serializable)."""
        stage_dir = self.stage_dir(stage)
        filepath = stage_dir / filename
        if isinstance(data, (dict, list)):
            filepath.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        elif isinstance(data, str):
            filepath.write_text(data, encoding="utf-8")
        elif isinstance(data, bytes):
            filepath.write_bytes(data)
        else:
            filepath.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return filepath

    def load_stage_checkpoint(self, stage: str, filename: str) -> Optional[Any]:
        """Load a stage checkpoint file."""
        stage_dir = self.stage_dir(stage)
        filepath = stage_dir / filename
        if not filepath.exists():
            return None
        if filename.endswith(".json"):
            return json.loads(filepath.read_text(encoding="utf-8"))
        return filepath.read_text(encoding="utf-8")

    def create_attempt_manifest(self, attempt_dir: Path, stage: str, metadata: Dict[str, Any] = None) -> CheckpointManifest:
        """Create manifest for an attempt directory."""
        manifest = CheckpointManifest(
            run_id=self.run_id,
            attempt_number=int(attempt_dir.name),
            stage=stage,
            timestamp=datetime.now().isoformat(),
            metadata=metadata or {},
        )
        return manifest

    def finalize_attempt(self, attempt_dir: Path, manifest: CheckpointManifest):
        """Finalize attempt: compute hashes, save manifest."""
        manifest.status = "COMPLETED"
        # Hash all files in attempt
        for filepath in attempt_dir.rglob("*"):
            if filepath.is_file() and filepath.name != "manifest.json":
                rel_path = filepath.relative_to(attempt_dir)
                manifest.file_hashes[str(rel_path)] = self._file_hash(filepath)
                manifest.artifacts.append(str(rel_path))

        # Save manifest
        manifest_path = attempt_dir / "manifest.json"
        manifest_path.write_text(json.dumps(asdict(manifest), indent=2, default=str), encoding="utf-8")
        log.info(f"Checkpoint finalized: {attempt_dir.name} ({len(manifest.artifacts)} artifacts)")

    def _file_hash(self, filepath: Path) -> str:
        """SHA-256 hash of file."""
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    def copy_to_final(self, attempt_dir: Path) -> Path:
        """Copy successful attempt to final/ directory."""
        final_dir = self.base_dir / "final"
        final_dir.mkdir(exist_ok=True)

        for src in attempt_dir.iterdir():
            dst = final_dir / src.name
            if src.is_file():
                shutil.copy2(src, dst)
            elif src.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)

        log.info(f"Copied attempt {attempt_dir.name} to final/")
        return final_dir

    def get_latest_attempt(self) -> Optional[Path]:
        """Get the most recent attempt directory."""
        attempts = sorted(self.attempts_dir.iterdir())
        return attempts[-1] if attempts else None

    def get_attempt_manifest(self, attempt_num: int) -> Optional[CheckpointManifest]:
        """Load manifest for a specific attempt."""
        attempt_dir = self.attempts_dir / f"{attempt_num:03d}"
        manifest_path = attempt_dir / "manifest.json"
        if not manifest_path.exists():
            return None
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return CheckpointManifest(**data)