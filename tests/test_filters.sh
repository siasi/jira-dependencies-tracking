#!/bin/bash
# Comprehensive test script for status and quarter filters

set -e  # Exit on error

echo "================================"
echo "Filter Testing Suite"
echo "================================"
echo ""

# Test 1: No filters (all initiatives)
echo "Test 1: No filters - extracting all initiatives"
python3 jira_extract.py extract --output test1_all.json 2>&1 | grep -E "(Applying filters|Summary:)" || echo "  No filters applied (expected)"
TOTAL1=$(jq '.summary.total_initiatives' test1_all.json)
STATUSES1=$(jq -r '.initiatives[].status' test1_all.json | sort | uniq -c | sort -rn)
echo "  Total initiatives: $TOTAL1"
echo "  Status breakdown:"
echo "$STATUSES1" | sed 's/^/    /'
echo ""

# Test 2: Quarter filter only (default behavior: excludes Done)
echo "Test 2: Quarter filter only --quarter '26 Q2'"
python3 jira_extract.py extract --quarter "26 Q2" --output test2_quarter.json 2>&1 | grep -E "Applying filters"
TOTAL2=$(jq '.summary.total_initiatives' test2_quarter.json)
STATUSES2=$(jq -r '.initiatives[].status' test2_quarter.json | sort | uniq -c | sort -rn)
QUARTERS2=$(jq -r '.initiatives[].quarter' test2_quarter.json | sort | uniq -c)
echo "  Total initiatives: $TOTAL2"
echo "  Status breakdown:"
echo "$STATUSES2" | sed 's/^/    /'
echo "  Quarter breakdown:"
echo "$QUARTERS2" | sed 's/^/    /'
echo ""

# Test 3: Status filter only (In Progress)
echo "Test 3: Status filter only --status 'In Progress'"
python3 jira_extract.py extract --status "In Progress" --output test3_status_in_progress.json 2>&1 | grep -E "Applying filters"
TOTAL3=$(jq '.summary.total_initiatives' test3_status_in_progress.json)
STATUSES3=$(jq -r '.initiatives[].status' test3_status_in_progress.json | sort | uniq -c)
echo "  Total initiatives: $TOTAL3"
echo "  Status breakdown:"
echo "$STATUSES3" | sed 's/^/    /'
echo ""

# Test 4: Status filter with negation (!Done)
echo "Test 4: Status filter with negation --status '!Done'"
python3 jira_extract.py extract --status "!Done" --output test4_status_not_done.json 2>&1 | grep -E "Applying filters"
TOTAL4=$(jq '.summary.total_initiatives' test4_status_not_done.json)
STATUSES4=$(jq -r '.initiatives[].status' test4_status_not_done.json | sort | uniq -c | sort -rn)
echo "  Total initiatives: $TOTAL4"
echo "  Status breakdown:"
echo "$STATUSES4" | sed 's/^/    /'
echo ""

# Test 5: Both filters (quarter + status)
echo "Test 5: Both filters --quarter '26 Q2' --status 'In Progress'"
python3 jira_extract.py extract --quarter "26 Q2" --status "In Progress" --output test5_both.json 2>&1 | grep -E "Applying filters"
TOTAL5=$(jq '.summary.total_initiatives' test5_both.json)
STATUSES5=$(jq -r '.initiatives[].status' test5_both.json | sort | uniq -c)
QUARTERS5=$(jq -r '.initiatives[].quarter' test5_both.json | sort | uniq -c)
echo "  Total initiatives: $TOTAL5"
echo "  Status breakdown:"
echo "$STATUSES5" | sed 's/^/    /'
echo "  Quarter breakdown:"
echo "$QUARTERS5" | sed 's/^/    /'
echo ""

# Test 6: Quarter + negation status
echo "Test 6: Quarter + negation --quarter '26 Q2' --status '!Done'"
python3 jira_extract.py extract --quarter "26 Q2" --status "!Done" --output test6_quarter_not_done.json 2>&1 | grep -E "Applying filters"
TOTAL6=$(jq '.summary.total_initiatives' test6_quarter_not_done.json)
STATUSES6=$(jq -r '.initiatives[].status' test6_quarter_not_done.json | sort | uniq -c | sort -rn)
echo "  Total initiatives: $TOTAL6"
echo "  Status breakdown:"
echo "$STATUSES6" | sed 's/^/    /'
echo ""

# Verify JQL queries
echo "================================"
echo "JQL Query Verification"
echo "================================"
echo ""
echo "Test 1 (No filters):"
jq -r '.queries.initiatives' test1_all.json | sed 's/^/  /'
echo ""
echo "Test 2 (Quarter only):"
jq -r '.queries.initiatives' test2_quarter.json | sed 's/^/  /'
echo ""
echo "Test 3 (Status: In Progress):"
jq -r '.queries.initiatives' test3_status_in_progress.json | sed 's/^/  /'
echo ""
echo "Test 4 (Status: !Done):"
jq -r '.queries.initiatives' test4_status_not_done.json | sed 's/^/  /'
echo ""
echo "Test 5 (Both: Quarter + In Progress):"
jq -r '.queries.initiatives' test5_both.json | sed 's/^/  /'
echo ""
echo "Test 6 (Both: Quarter + !Done):"
jq -r '.queries.initiatives' test6_quarter_not_done.json | sed 's/^/  /'
echo ""

# Validate expectations
echo "================================"
echo "Validation Checks"
echo "================================"
echo ""

# Check 1: Test 2 should equal Test 6 (both use quarter + !Done)
if [ "$TOTAL2" -eq "$TOTAL6" ]; then
    echo "✓ Test 2 (quarter only) == Test 6 (quarter + !Done): $TOTAL2 initiatives"
else
    echo "✗ MISMATCH: Test 2 ($TOTAL2) != Test 6 ($TOTAL6)"
fi

# Check 2: Test 3 should have only "In Progress" status
IN_PROGRESS_ONLY=$(jq -r '.initiatives[].status' test3_status_in_progress.json | sort | uniq)
if [ "$IN_PROGRESS_ONLY" == "In Progress" ]; then
    echo "✓ Test 3 contains only 'In Progress' initiatives"
else
    echo "✗ Test 3 contains multiple statuses: $IN_PROGRESS_ONLY"
fi

# Check 3: Test 1 should be >= Test 4 (all vs !Done)
if [ "$TOTAL1" -ge "$TOTAL4" ]; then
    echo "✓ Test 1 (all: $TOTAL1) >= Test 4 (!Done: $TOTAL4)"
else
    echo "✗ Test 1 ($TOTAL1) < Test 4 ($TOTAL4) - unexpected!"
fi

# Check 4: No "Done" status in tests 2, 4, 6
HAS_DONE_2=$(jq -r '.initiatives[].status' test2_quarter.json | grep -c "^Done$" || echo "0")
HAS_DONE_4=$(jq -r '.initiatives[].status' test4_status_not_done.json | grep -c "^Done$" || echo "0")
HAS_DONE_6=$(jq -r '.initiatives[].status' test6_quarter_not_done.json | grep -c "^Done$" || echo "0")

if [ "$HAS_DONE_2" -eq 0 ] && [ "$HAS_DONE_4" -eq 0 ] && [ "$HAS_DONE_6" -eq 0 ]; then
    echo "✓ No 'Done' status found in tests 2, 4, 6 (as expected)"
else
    echo "✗ Found 'Done' status in: Test2=$HAS_DONE_2, Test4=$HAS_DONE_4, Test6=$HAS_DONE_6"
fi

echo ""
echo "================================"
echo "Test suite complete!"
echo "================================"
echo ""
echo "Cleaning up test files..."
rm -f test1_all.json test2_quarter.json test3_status_in_progress.json \
      test4_status_not_done.json test5_both.json test6_quarter_not_done.json

echo "✓ Done"
