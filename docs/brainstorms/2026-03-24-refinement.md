# Initiative Planning Readiness Validation

## Problem Statement

Get clarity about initiative planning readiness by analyzing Jira data and classifying initiatives into clear maturity states with actionable next steps.

## Scope and Filtering

### Data Extraction Level (jira_scan.py)
- **Quarter filter**: Set in `config.yaml` (e.g., `quarter: "26 Q2"`)
- **Status filter**: `status = 'Proposed'`
- Extraction creates filtered JSON snapshots for validation

### Validation Level (validate_initiative_status.py)
- **Teams filter**: Hardcoded to `teams_involved >= 2` (multi-team initiatives only)
- **Rationale**: Single-team initiatives don't have cross-team dependencies to validate
- Validates pre-filtered JSON data (assumes correct quarter)

## Core Validation Logic

### Epic Count Requirement
**Rule**: Count of unique teams with epics = (teams_involved - 1)

**Explanation:**
- The leading team (owner_team) doesn't need to create epics for themselves
- Each non-owner team can create any number of epics
- What matters is the number of teams that have created at least one epic

**Example:**
- Initiative has 3 teams: Team A (owner), Team B, Team C
- Required: 2 teams must have created epics (3 - 1 = 2)
- Valid scenarios:
  - Team B: 1 epic, Team C: 1 epic ✓
  - Team B: 2 epics, Team C: 1 epic ✓
  - Team B: 5 epics, Team C: 0 epics ✗ (only 1 team)

### RAG Status Requirement
**Rule**: All epics must have RAG status set, **except epics from the owner team**

**Explanation:**
- Owner team epics don't need RAG status (they're not dependencies)
- Only non-owner team epics require RAG status
- Missing RAG status from non-owner teams blocks planning discussion

### Assignee Requirement
**Rule**: Assignee is checked **only after** all non-owner epics are GREEN

**Explanation:**
- Assignee is the final gate before moving to "Planned" status
- Don't check assignee for initiatives with RED/YELLOW epics
- Don't check assignee for initiatives missing epics or RAG status

## Report Structure (5 Sections)

### Section 1: 📋 Dependency Mapping in Progress
**Criteria**: Missing epics OR missing RAG status (from non-owner teams)

**Help text**: "Action required: Create missing epics and set initial RAG status"

**Shows:**
- Initiatives with epic count mismatch (need more teams to create epics)
- Initiatives with missing RAG status on non-owner epics
- Specific teams that need to create epics
- Specific epics that need RAG status set

---

### Section 2: 🔴 Can't be completed in the quarter
**Criteria**: Has at least 1 non-owner epic with RAG status = RED

**Help text**: "Teams cannot commit - deprioritize other work to proceed"

**Shows:**
- Initiatives with RED epics
- Which epics are RED and why this blocks the quarter
- This is a valid outcome (not all initiatives can be planned)

---

### Section 3: 🟡 Low confidence for planning - require discussion
**Criteria**: No RED epics AND at least 1 non-owner epic with RAG status = YELLOW

**Help text**: "Low confidence - evaluate re-sequencing or reprioritization"

**Shows:**
- Initiatives with YELLOW epics (no RED)
- Which epics need clarification
- Requires discussion to build confidence

---

### Section 4: 👤 Ready - Awaiting Owner
**Criteria**: All non-owner epics are GREEN AND no assignee set

**Help text**: "Action required: Assign initiative owner to proceed"

**Shows:**
- Initiatives ready for planning but need owner assignment
- Final check before moving to "Planned" status

---

### Section 5: ✅ Ready to Move to Planned
**Criteria**: All non-owner epics are GREEN AND assignee is set

**Help text**: "Action required: Update status to Planned in Jira (bulk keys provided below)"

**Shows:**
- Initiatives ready to move from "Proposed" to "Planned"
- Comma-separated list of keys for bulk Jira update

## Additional Features

### Verbose Mode (--verbose flag)
**Shows additional sections:**
- **Planned Initiatives with Issues**: Initiatives already in "Planned" status that have regressed (no longer meet criteria)
- **Not Analyzed**: Initiatives with other statuses (Rejected, In Progress, Done, etc.) or single-team initiatives

**Default behavior**: These sections are hidden (focus on main workflow)

### Markdown Export (--markdown flag)
**Purpose**: Export report to Notion-friendly markdown format

**Usage:**
```bash
# Auto-generate filename with timestamp
python validate_initiative_status.py --markdown

# Specify custom filename
python validate_initiative_status.py --markdown report.md
```

**Format:**
- Structured headers (##, ###)
- Clickable Jira links: `[KEY](URL)`
- Checkboxes for action items: `- [ ]`
- All 5 sections with same structure as console output
- Includes verbose sections if --verbose flag is used

### Flexible Data Source
**Supports multiple input sources:**
- Latest extraction (auto-detect from data/ directory)
- Specific JSON file path
- Specific snapshot file

**Usage:**
```bash
# Use latest extraction
python validate_initiative_status.py

# Validate specific file
python validate_initiative_status.py data/jira_extract_20260324.json

# Validate specific snapshot
python validate_initiative_status.py data/snapshots/snapshot_baseline_20260324.json
```

### Team Mappings (team_mappings.yaml)
**Purpose**: Map display names from "Teams Involved" field to project keys from epics

**Format:**
```yaml
team_mappings:
  "Core Banking": "CBNK"
  "Console": "CONSOLE"
  "MAP": "MAPS"
```

**Why needed**: Teams Involved uses display names, epics use project keys - mapping ensures accurate matching

## What's Explicitly Removed

### Exit Codes
- **Removed**: Script always exits with code 0
- **Rationale**: Validation issues are informational, not CI/CD failures
- Script doesn't "fail" when initiatives have issues - it reports their status

### JQL Query Display
- **Removed**: Don't show JQL query in validation report
- **Rationale**: JQL is an extraction concern, not validation concern
- Quarter filtering happens at extraction level, validation doesn't need to know about it

## Summary

This validation tool provides a clear, actionable view of initiative planning readiness by:
1. Filtering to multi-team initiatives (teams >= 2)
2. Classifying into 5 distinct maturity states
3. Showing specific actions needed to progress
4. Supporting multiple output formats (console, markdown)
5. Allowing detailed inspection with verbose mode  