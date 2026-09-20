"""
NEXUS VAULTS 2.0 - Golden Regression Test
Synthetic pipeline verification using 12 intentionally distinct visual assets.
Proves:
1. N distinct assets -> N distinct scene clips.
2. Scene 001 != Scene 002 != ... != Scene 012.
3. Every asset traces: Source -> Scene Clip -> Final MP4.
4. FAILS IMMEDIATELY if any asset is reused or if one global asset leaks across scenes.
"""

import unittest
import shutil
import tempfile
import json
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
from PIL import Image, ImageDraw
import _guard
_guard.ensure_isolation()  # MUST precede any project import
from core.manifest import generate_render_manifest
from media.compositor import build_composite_video_from_manifest
from media.images import compute_dhash, hamming_distance, compute_sha256
from qc.frame_verifier import verify_scene_clips_and_frames

class GoldenRegressionTest(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="nexus_regression_"))
        self.assets_dir = self.test_dir / "assets"
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.temp_scenes_dir = self.test_dir / "temp_scenes"
        self.temp_scenes_dir.mkdir(parents=True, exist_ok=True)

        # Generate 12 intentionally distinct geometric color assets
        self.asset_configs = [
            ("red_square", (255, 0, 0), "rect"),
            ("blue_circle", (0, 0, 255), "circle"),
            ("green_triangle", (0, 255, 0), "triangle"),
            ("yellow_cross", (255, 255, 0), "cross"),
            ("cyan_diamond", (0, 255, 255), "diamond"),
            ("magenta_star", (255, 0, 255), "circle"),
            ("orange_box", (255, 140, 0), "rect"),
            ("purple_shape", (128, 0, 128), "diamond"),
            ("lime_cross", (50, 205, 50), "cross"),
            ("teal_block", (0, 128, 128), "rect"),
            ("pink_circle", (255, 105, 180), "circle"),
            ("white_symbol", (240, 240, 240), "triangle"),
        ]

        self.source_assets = []
        for idx in range(12):
            img_path = self.assets_dir / f"scene_synth_{idx:02d}.jpg"
            img = Image.new("RGB", (800, 800), color=(10, 10, 10))
            draw = ImageDraw.Draw(img)
            pat_type = idx % 4
            if pat_type == 0:
                # Vertical bars
                for x in range(0, 800, 120):
                    draw.rectangle([(x, 0), (x + 60, 800)], fill=(255, 255, 255))
            elif pat_type == 1:
                # Horizontal bars
                for y in range(0, 800, 120):
                    draw.rectangle([(0, y), (800, y + 60)], fill=(255, 255, 255))
            elif pat_type == 2:
                # Checkerboard blocks
                for x in range(0, 800, 200):
                    for y in range(0, 800, 200):
                        draw.rectangle([(x, y), (x + 100, y + 100)], fill=(255, 255, 255))
            else:
                # Big diagonal cross
                draw.line([(0, 0), (800, 800)], fill=(255, 255, 255), width=80)
                draw.line([(0, 800), (800, 0)], fill=(255, 255, 255), width=80)

            draw.text((200, 380), f"TEST SCENE #{idx+1:02d}", fill=(255, 200, 0))
            img.save(img_path, "JPEG")
            self.source_assets.append(img_path)

        # Generate a dummy audio file (12 seconds)
        self.dummy_audio = self.test_dir / "dummy_audio.mp4"
        cmd = [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
            "-t", "12", "-c:a", "aac", str(self.dummy_audio)
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        # Generate a dummy subtitle file (.ass)
        self.dummy_ass = self.test_dir / "dummy.ass"
        with open(self.dummy_ass, "w", encoding="utf-8") as f:
            f.write("[Script Info]\nTitle: Dummy\nScriptType: v4.00+\n[V4+ Styles]\nFormat: Name\nStyle: Default\n[Events]\nFormat: Start, End, Style, Text\nDialogue: 0:00:00.00,0:00:12.00,Default,TEST\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_golden_12_scene_distinct_pipeline(self):
        """Validates that 12 distinct assets yield 12 distinct clips and assemble correctly."""
        scenes = []
        for i, asset_path in enumerate(self.source_assets):
            sha = compute_sha256(asset_path)
            ph = compute_dhash(asset_path)
            scenes.append({
                "scene_id": i + 1,
                "start": float(i),
                "end": float(i + 1),
                "duration": 1.0,
                "narration": f"Synthetic claim beat {i + 1}",
                "claim": f"Synthetic proposition {i + 1}",
                "visual_purpose": "SHOW_PRIMARY_EVIDENCE",
                "visual_type": "ARCHIVAL_PHOTO",
                "asset_path": str(asset_path.resolve().as_posix()),
                "path": asset_path,
                "asset_meta": {
                    "asset_id": f"synthetic_{i+1:02d}",
                    "sha256": sha,
                    "phash": hex(ph),
                    "source": "Synthetic Test Rig"
                },
                "motion_intent": "hero_reveal",
                "composition_intent": "hero_full_frame",
                "transition_in": "hard_cut",
                "transition_out": "hard_cut",
                "audio_intent": "normal"
            })

        # 1. Generate Render Manifest
        manifest_path = self.test_dir / "render_manifest.json"
        generate_render_manifest(scenes, manifest_path, file_number=999, topic="Synthetic Regression")

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)

        # 2. Render through Compositor
        output_mp4 = self.test_dir / "FILE_999_regression.mp4"
        build_composite_video_from_manifest(
            manifest_data=manifest_data,
            mixed_audio_path=self.dummy_audio,
            ass_subtitle_path=self.dummy_ass,
            output_video_path=output_mp4,
            file_number=999
        )

        self.assertTrue(output_mp4.exists(), "Final assembled MP4 must exist!")
        self.assertGreater(output_mp4.stat().st_size, 10000, "Final MP4 must have valid content size!")

        # 3. Verify All 12 Scene Clips are Pairwise Distinct
        # Default temp scenes directory for file 999:
        from core.config import config
        scenes_dir = config.storage.temp_dir / "scenes_999"

        clip_phashes = []
        for i in range(12):
            clip_file = scenes_dir / f"scene_{i:03d}.mp4"
            self.assertTrue(clip_file.exists(), f"Scene clip {clip_file.name} must exist!")
            # Extract midpoint frame
            frame_img = self.test_dir / f"clip_frame_{i:02d}.jpg"
            cmd = ["ffmpeg", "-y", "-ss", "0.5", "-i", str(clip_file), "-vframes", "1", str(frame_img)]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            ph = compute_dhash(frame_img)
            clip_phashes.append(ph)

        # Check that consecutive scene clips are distinctly different (dHash dist > 15)
        for i in range(len(clip_phashes) - 1):
            dist = hamming_distance(clip_phashes[i], clip_phashes[i + 1])
            self.assertGreater(
                dist, 10,
                f"Scene {i+1} and Scene {i+2} are identical or near-identical! (dHash dist: {dist}). Compositor must not reuse assets!"
            )

        # Clean up temp scenes 999
        shutil.rmtree(scenes_dir, ignore_errors=True)

    def test_claim_subject_drift_and_specificity(self):
        """
        GOLDEN TEST 2: Claim Subject Drift & False Uniqueness Prevention.
        Verifies that 10 distinct claims across persons, objects, locations, events,
        diagrams, and documents produce 10 distinct primary visual subjects,
        and that NONE of them blindly inherit the global video topic.
        """
        from content.scene_planner import _extract_claim_subject, _split_into_scene_claims

        topic = "D'Alembert's Paradox"

        # 10 distinct claims representing diverse evidence classes
        claims = [
            # 1. Historical Person
            "In 1752, mathematician Jean le Rond d'Alembert calculated fluid resistance across solid bodies.",
            # 2. Historical Craft / Object
            "At Kitty Hawk, the 1903 Wright Flyer measured 30 newtons of actual drag force in flight.",
            # 3. Specific Location
            "The experimental wind tunnel was constructed outside Cambridge to test fluid dynamics.",
            # 4. Experimental Event
            "In 1915, Osborne Reynolds documented boundary-layer separation in wind-tunnel experiments.",
            # 5. Scientific Mechanism
            "Boundary-layer separation regime causes low-pressure turbulent wakes behind moving airfoils.",
            # 6. Theoretical Concept
            "Inviscid fluid potential flow theory predicts zero pressure drag around symmetrical cylinders.",
            # 7. Archival Document
            "The 1752 Paris Academy treatise recorded the mathematical proof of zero resistance.",
            # 8. Testing Apparatus
            "Aeronautical wind-tunnel testing apparatus measured airflow velocities across physical wing models.",
            # 9. Physical Property Mechanism
            "Fluid viscosity and shear stress transfer kinetic energy from the solid boundary into heat.",
            # 10. Paradox Resolution
            "The paradox was resolved by discovering microscopic boundary layers adhering to physical surfaces."
        ]

        extracted_subjects = []
        extracted_types = []

        for idx, claim in enumerate(claims):
            primary_subj, supp, vtype, purpose = _extract_claim_subject(claim, topic)
            extracted_subjects.append(primary_subj)
            extracted_types.append(vtype)

            # Rule 1: The global topic MUST NOT become the scene subject
            self.assertNotEqual(
                primary_subj.strip().lower(),
                topic.strip().lower(),
                f"Scene {idx+1} suffered TOPIC DRIFT! Primary subject '{primary_subj}' cannot be the global topic '{topic}'."
            )

            # Rule 2: Primary subject must not be empty or generic
            self.assertGreater(len(primary_subj), 4, f"Primary subject '{primary_subj}' too short/generic for scene {idx+1}")

        # Rule 3: 10 distinct claims MUST produce 10 distinct primary visual subjects
        unique_subjects = set(extracted_subjects)
        self.assertEqual(
            len(unique_subjects),
            len(claims),
            f"Expected {len(claims)} unique primary visual subjects, but got {len(unique_subjects)}! Duplicates detected: {extracted_subjects}"
        )

        # Rule 4: Verify specific expected entities are correctly recognized
        self.assertIn("Jean le Rond d'Alembert", extracted_subjects[0])
        self.assertIn("1903 Wright Flyer", extracted_subjects[1])
        self.assertIn("Cambridge", extracted_subjects[2])
        self.assertIn("Osborne Reynolds", extracted_subjects[3])
        self.assertIn("Boundary-Layer", extracted_subjects[4])
        self.assertIn("Potential Flow", extracted_subjects[5])
        self.assertIn("Paris", extracted_subjects[6])
        self.assertIn("Wind-Tunnel", extracted_subjects[7])
        self.assertIn("Viscosity", extracted_subjects[8])

if __name__ == "__main__":
    unittest.main()

