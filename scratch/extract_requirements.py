# Read all PRD parts and combine
parts = []
for i in range(1, 8):
    with open(f'C:/YT-SHORTS/PRD_Revision_3_part{i}.txt', 'r', encoding='utf-8') as f:
        parts.append(f.read())

full_prd = '\n'.join(parts)

# Save combined PRD
with open('C:/YT-SHORTS/PRD_Revision_3_full.txt', 'w', encoding='utf-8') as f:
    f.write(full_prd)

print(f"Combined PRD length: {len(full_prd)} characters")

# Now extract requirements - look for sentences with modal verbs indicating requirements
import re

# Patterns for requirement indicators
requirement_patterns = [
    r'(?:must|shall|will|is required to|are required to|shall not|must not|prohibited|forbidden|shall ensure|shall verify|shall confirm|shall inspect|shall determine|shall classify|shall trace|shall build|shall fix|shall preserve|shall not stop|shall do not|shall not claim|shall not reply)',
    r'(?:objective is|goal is|The end state should be|The final system should support|Verify that|Confirm that|Ensure that|Determine whether|Inspect|Trace|Build|Classify|Do not|Do NOT|NOT|NEVER)',
    r'(?:Required:|Actions?:|Verify:|Check:|Inspect:|Trace:|Build:|Classify:|Do not:|DO NOT:|NOT:|NEVER:)'
]

# Function to identify which phase a sentence might belong to
def identify_phase(sentence, full_text):
    sentence_lower = sentence.lower()
    if 'repository discovery' in sentence_lower or 'phase 1' in sentence_lower:
        return 'Phase 1 - Repository Discovery'
    elif 'read the entire prd' in sentence_lower or 'phase 2' in sentence_lower:
        return 'Phase 2 - Read the Entire PRD'
    elif 'complete system map' in sentence_lower or 'phase 3' in sentence_lower:
        return 'Phase 3 - Complete System Map'
    elif 'prd ↔ code reconciliation' in sentence_lower or 'phase 4' in sentence_lower:
        return 'Phase 4 - PRD ↔ Code Reconciliation'
    elif 'database / state truth' in sentence_lower or 'phase 5' in sentence_lower:
        return 'Phase 5 - Database / State Truth'
    elif 'current production archive' in sentence_lower or 'phase 6' in sentence_lower:
        return 'Phase 6 - Current Production Archive'
    elif 'production autonomy' in sentence_lower or 'phase 7' in sentence_lower:
        return 'Phase 7 - Production Autonomy'
    elif 'autonomous learning' in sentence_lower or 'phase 8' in sentence_lower:
        return 'Phase 8 - Autonomous Learning'
    elif 'visual intelligence' in sentence_lower or 'phase 9' in sentence_lower:
        return 'Phase 9 - Visual Intelligence'
    elif 'factuality' in sentence_lower or 'phase 10' in sentence_lower:
        return 'Phase 10 - Factuality'
    elif 'qc' in sentence_lower or 'quality control' in sentence_lower or 'phase 11' in sentence_lower:
        return 'Phase 11 - QC'
    elif 'publishing safety' in sentence_lower or 'phase 12' in sentence_lower:
        return 'Phase 12 - Publishing Safety'
    elif 'idempotency' in sentence_lower or 'phase 13' in sentence_lower:
        return 'Phase 13 - Idempotency'
    elif 'error handling' in sentence_lower or 'phase 14' in sentence_lower:
        return 'Phase 14 - Error Handling'
    elif 'automation' in sentence_lower or 'phase 15' in sentence_lower:
        return 'Phase 15 - Automation'
    elif 'implement everything missing' in sentence_lower or 'phase 16' in sentence_lower:
        return 'Phase 16 - Implement Everything Missing'
    elif 'current production standard' in sentence_lower or 'phase 17' in sentence_lower:
        return 'Phase 17 - Current Production Standard'
    elif 'verification' in sentence_lower or 'phase 18' in sentence_lower:
        return 'Phase 18 - Verification'
    elif 'real production run' in sentence_lower or 'phase 19' in sentence_lower:
        return 'Phase 19 - Real Production Run'
    elif 'critical behavior' in sentence_lower or 'final report' in sentence_lower:
        return 'Critical Behavior / Final Report'
    else:
        return 'General'

# Extract sentences that contain requirement indicators
sentences = re.split(r'(?<=[.!?])\s+', full_prd)
requirements = []

for i, sentence in enumerate(sentences):
    sentence = sentence.strip()
    if len(sentence) < 10:  # Skip too short
        continue
        
    # Check if sentence contains requirement indicators
    is_requirement = False
    for pattern in requirement_patterns:
        if re.search(pattern, sentence, re.IGNORECASE):
            is_requirement = True
            break
    
    # Also look for specific requirement language from the briefing
    requirement_indicators = [
        'must', 'shall', 'will', 'required', 'necessary', 'essential', 'critical',
        'verify', 'confirm', 'ensure', 'determine', 'inspect', 'trace', 'build',
        'classify', 'fix', 'preserve', 'do not', 'do not stop', 'do not claim',
        'do not reply', 'objective is', 'goal is', 'end state should be',
        'final system should support', 'prohibited', 'forbidden', 'never'
    ]
    
    if any(indicator in sentence.lower() for indicator in requirement_indicators):
        # Additional check: make sure it's not just descriptive text
        if not any(descriptive in sentence.lower() for descriptive in ['you must understand', 'you must:', 'the objective is:', 'the goal is:', 'phase', 'mission']):
            is_requirement = True
    
    if is_requirement:
        requirements.append({
            'id': len(requirements) + 1,
            'text': sentence,
            'source_line': i,  # Approximate
            'phase': identify_phase(sentence, full_prd)
        })

# Save requirements to file
import json
with open('C:/YT-SHORTS/extracted_requirements.json', 'w', encoding='utf-8') as f:
    json.dump(requirements, f, indent=2)

print(f"Extracted {len(requirements)} potential requirements")

# Show first few for verification
for req in requirements[:10]:
    print(f"{req['id']} [{req['phase']}]: {req['text'][:150]}...")