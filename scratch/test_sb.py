import sys
sys.path.insert(0, ".")
from content.scene_planner import generate_storyboard

script = (
    "In 1752 French mathematician Jean d’Alembert proved zero drag, yet the Wright brothers felt resistance in 1903. "
    "That year in Paris d'Alembert published his potential‑flow theorem claiming no force on a moving body. "
    "At Kitty Hawk, the 1903 Flyer measured 30 newtons of drag. "
    "In 1915 Osborne Reynolds documented boundary‑layer separation in wind‑tunnel tests, proving viscosity matters. "
    "What actually happened to D'Alembert's paradox. NEXUS VAULTS."
)

sb = generate_storyboard(script, "D'Alembert's paradox", 29.7)
print(f"Generated {len(sb)} scenes:")
for s in sb:
    print(f"S{s['scene_id']:02d}: Claim: '{s['claim'][:40]}' -> Subject: '{s['primary_visual_subject']}' [{s['visual_type']}]")
