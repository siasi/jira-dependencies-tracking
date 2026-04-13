#!/bin/bash
set -e

echo "=== Smoke Test Suite ==="

echo "1. Testing data extraction..."
python3 extract.py --help > /dev/null

echo "2. Testing planning validation..."
python3 validate_planning.py --help > /dev/null

echo "3. Testing workload analysis..."
python3 analyze_workload.py --help > /dev/null

echo "4. Testing installed commands (if available)..."
if command -v jem-scan &> /dev/null; then
    jem-scan --help > /dev/null
    echo "   jem-scan: OK"
fi

if command -v jem-check-planning &> /dev/null; then
    jem-check-planning --help > /dev/null
    echo "   jem-check-planning: OK"
fi

if command -v jem-assess-workload &> /dev/null; then
    jem-assess-workload --help > /dev/null
    echo "   jem-assess-workload: OK"
fi

echo "5. Testing config loading..."
python3 -c "from src.config import load_config; load_config()"

echo "6. Testing template rendering..."
python3 -c "from lib.template_renderer import get_template_environment; get_template_environment()"

echo "7. Testing file utils..."
python3 -c "from lib.file_utils import find_most_recent_data_file; find_most_recent_data_file()"

echo "8. Testing common formatting..."
python3 -c "from lib.common_formatting import make_clickable_link; print(make_clickable_link('TEST', 'http://example.com'))"

echo ""
echo "=== All Smoke Tests Passed ==="
