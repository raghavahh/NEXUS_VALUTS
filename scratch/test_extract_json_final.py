import sys
sys.path.insert(0, 'C:/YT-SHORTS')
from core.llm_router import extract_json
import json

def test_extract_json_with_thinking():
    # Test case 1 from test_config.py
    raw = \"Here's thinking process:\\n1. Think\\n`json\\n{\\\"test\\\": 42}\\n`\\nExtra text\"
    clean = extract_json(raw)
    data = json.loads(clean)
    assert data[\"test\"] == 42, f\"Expected {{\\\"test\\\": 42}}, got {data}\"
    print(\"Test 1 passed\")
    
    # Test case 2 from test_config.py
    raw_no_markdown = \"Thinking:\\n- Analyze\\n{\\\"key\\\": \\\"value\\\"}\\nDone\"
    clean2 = extract_json(raw_no_markdown)
    data2 = json.loads(clean2)
    assert data2[\"key\"] == \"value\", f\"Expected {{\\\"key\\\": \\\"value\\\"}}, got {data2}\"
    print(\"Test 2 passed\")
    
    print(\"All extract_json tests passed.\")

if __name__ == '__main__':
    test_extract_json_with_thinking()
