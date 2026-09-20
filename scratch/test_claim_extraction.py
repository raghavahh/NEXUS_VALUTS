import re

def extract_subject(claim: str, topic: str):
    clean = claim.replace("’", "'").replace("“", '"').replace("”", '"').strip()

    # 1. Historical actors, craft, and scientists
    names = re.findall(
        r'\b(?:Wright brothers|Orville Wright|Wilbur Wright|1903 Flyer|Wright Flyer|Osborne Reynolds|'
        r'Jean d\'Alembert|Jean le Rond d\'Alembert|d\'Alembert|Stephen Hawking|Hawking|Albert Einstein|'
        r'Einstein|Isaac Newton|Newton|Niels Bohr|Max Planck|Galileo|Oppenheimer|Hubble|LIGO|Mary Celeste|Marconi)\b',
        clean,
        re.IGNORECASE
    )
    if names:
        n = names[0]
        if "flyer" in n.lower() or "wright" in n.lower():
            if "kitty hawk" in clean.lower():
                return "1903 Wright Flyer / Kitty Hawk", "OBJECT_CLOSEUP", "SHOW_PRIMARY_EVIDENCE"
            return "1903 Wright Flyer", "OBJECT_CLOSEUP", "SHOW_PRIMARY_EVIDENCE"
        if "reynolds" in n.lower():
            return "Osborne Reynolds / Boundary-Layer Separation", "DIAGRAM", "EXPLAIN_MECHANISM"
        if "alembert" in n.lower():
            if "1752" in clean or "proved" in clean:
                return "Jean le Rond d'Alembert 1752 Proof", "PORTRAIT", "IDENTIFY_PERSON"
            return "D'Alembert Potential-Flow Theorem", "DOCUMENT", "SHOW_PRIMARY_EVIDENCE"
        return n.title(), "PORTRAIT", "IDENTIFY_PERSON"

    # 2. Locations
    locs = re.findall(r'\b(Kitty Hawk|Paris|Cambridge|Berlin|Princeton|M87|Messier 87|Fort Detrick|Azores)\b', clean, re.IGNORECASE)
    if locs:
        return f"{locs[0].title()} Historical Location", "ARCHIVAL_PHOTO", "ESTABLISH_LOCATION"

    # 3. Specific mechanisms / scientific terms
    mechs = re.findall(
        r'\b(boundary[- ]layer separation|potential[- ]flow theorem|viscosity|zero drag|30 newtons|drag|wind[- ]tunnel|resistance|thermal radiation|event horizon|singularity)\b',
        clean,
        re.IGNORECASE
    )
    if mechs:
        return f"{mechs[0].title()} Mechanism", "DIAGRAM", "EXPLAIN_MECHANISM"

    # 4. Multi-word capitalized phrases
    caps = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', clean)
    if caps and caps[0].lower() != "nexus vaults":
        return caps[0], "ARCHIVAL_PHOTO", "SHOW_PRIMARY_EVIDENCE"

    # Fallback: Extract first 3-4 significant words from the claim itself
    words = [
        w for w in re.findall(r'\b[A-Za-z0-9\-]+\b', clean)
        if w.lower() not in {
            "the", "a", "an", "in", "on", "at", "to", "for", "with", "but", "however",
            "when", "while", "where", "why", "how", "what", "then", "now", "if", "that",
            "this", "and", "yet", "proving", "matters", "nexus", "vaults"
        }
    ]
    if words:
        return " ".join(words[:3]).title(), "ARCHIVAL_PHOTO", "SHOW_PRIMARY_EVIDENCE"

    if "what actually happened" in clean.lower():
        return f"{topic} Paradox Resolution", "DIAGRAM", "REVEAL_INFORMATION"
    if clean.strip().upper() == "NEXUS VAULTS.":
        return "NEXUS Archival Investigation Verdict", "ARCHIVAL_PHOTO", "CLOSE_OUT"

    return f"{topic} Archival Evidence", "ARCHIVAL_PHOTO", "SHOW_PRIMARY_EVIDENCE"

def split_into_scene_claims(script: str, num_scenes: int, topic: str):
    clean = re.sub(r'\s+', ' ', script).strip()
    # Split by periods, questions, exclamations, and major conjunctions/commas
    parts = [p.strip() for p in re.split(r'(?<=[.!?])\s+|(?<=[,;])\s+|\s+(?:while|yet|however|proving|where)\s+', clean) if p.strip()]
    meaningful = [p for p in parts if p.lower() != "nexus vaults." and len(p.split()) >= 2]
    if not meaningful:
        meaningful = parts or [topic]

    while len(meaningful) > num_scenes:
        # Merge shortest adjacent pair
        min_len = 999
        min_idx = 0
        for idx in range(len(meaningful) - 1):
            comb = len(meaningful[idx].split()) + len(meaningful[idx+1].split())
            if comb < min_len:
                min_len = comb
                min_idx = idx
        merged = meaningful[min_idx] + ", " + meaningful[min_idx+1]
        meaningful = meaningful[:min_idx] + [merged] + meaningful[min_idx+2:]

    while len(meaningful) < num_scenes:
        longest_idx = max(range(len(meaningful)), key=lambda idx: len(meaningful[idx].split()))
        words = meaningful[longest_idx].split()
        if len(words) >= 4:
            mid = len(words) // 2
            h1 = " ".join(words[:mid])
            h2 = " ".join(words[mid:])
            meaningful = meaningful[:longest_idx] + [h1, h2] + meaningful[longest_idx+1:]
        else:
            break

    while len(meaningful) < num_scenes:
        meaningful.append(f"{topic} investigation focus")

    return meaningful[:num_scenes]

full_script = "In 1752 French mathematician Jean d’Alembert proved zero drag, yet the Wright brothers felt resistance in 1903. That year in Paris d'Alembert published his potential‑flow theorem claiming no force on a moving body. At Kitty Hawk, the 1903 Flyer measured 30 newtons of drag. In 1915 Osborne Reynolds documented boundary‑layer separation in wind‑tunnel tests, proving viscosity matters. What actually happened to D'Alembert's paradox. NEXUS VAULTS."

beats = split_into_scene_claims(full_script, 10, "D'Alembert's paradox")
print(f"SPLIT INTO {len(beats)} BEATS:")
for i, b in enumerate(beats, 1):
    subj, vtype, purp = extract_subject(b, "D'Alembert's paradox")
    print(f"Scene {i:02d}: Claim: '{b[:45]}' -> Subject: '{subj}' [{vtype}]")

