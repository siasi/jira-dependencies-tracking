---
title: Tech Leadership Initiative Priority Validation
type: brainstorm
date: 2026-04-08
status: draft
---

# Tech Leadership Initiative Priority Validation

## What We're Building

A new validation tool (`validate_tech_leadership.py`) that provides visibility into team commitments to Tech Leadership initiatives and ensures teams respect relative initiative priorities.

**Core Problem:**
Tech Leadership initiatives represent the technical backlog requiring cross-team coordination. Sometimes teams commit to lower-priority initiatives while not committing to higher-priority ones, or teams don't commit to any Tech Leadership initiatives they're expected to contribute to.

**Solution:**
A standalone validation script that:
- Loads Tech Leadership initiative priorities from a config file
- Validates team commitments against those priorities
- Flags priority conflicts as warnings with manager action items
- Generates focused reports (console + optional Slack notifications)

## Why This Approach

### Standalone Script vs Extension

**Decision:** Create `validate_tech_leadership.py` as a separate script rather than extending `check_planning.py` or `assess_workload.py`.

**Rationale:**
1. **Distinct concern:** Tech Leadership priority tracking is conceptually different from product planning validation
2. **Clear naming:** `validate_tech_leadership.py --quarter "26 Q2"` makes intent explicit
3. **Independent evolution:** Can evolve Tech Leadership validation without affecting product planning
4. **Separation of concerns:** Product planning validation checks readiness; Tech Leadership validation checks strategic alignment

**Trade-off accepted:**
- Initial code duplication (action items, Slack generation)
- Will be addressed by Phase 2 refactoring (extracting shared utilities to `lib/`)
- Aligns with existing plan to create `lib/manager_info.py`, `lib/action_items.py`, `lib/slack_messages.py`

### Config-Based Priorities vs Jira Field

**Decision:** Store priorities in `config/tech_leadership_priorities.yaml` as a simple ordered list.

**Rationale:**
1. **Flexibility:** Easy to reorder priorities without touching Jira
2. **Speed:** No need to update custom fields, wait for sync, or coordinate with Jira admins
3. **Simplicity:** Just a YAML list of initiative keys in priority order
4. **Gitops:** Priority changes are versioned and reviewable in git

**Trade-off accepted:**
- Config must be kept in sync with current quarter's initiatives
- Mitigation: Show warnings for missing/unlisted initiatives

### Warning + Action Items vs Hard Blocking

**Decision:** Flag priority conflicts as warnings and generate manager action items, not hard validation errors.

**Rationale:**
1. **Flexibility:** Allows justified exceptions (e.g., team expertise, capacity constraints)
2. **Non-blocking:** Doesn't halt planning; provides visibility for discussion
3. **Accountability:** Managers receive action items to review and justify decisions
4. **Gradual adoption:** Teams can start using it without breaking existing workflows

## Key Decisions

### 1. How Tech Leadership Initiatives Are Identified

**Method:** `owner_team == "Tech Leadership"`

**Details:**
- Uses existing `owner_team` field from Jira data
- No new custom fields needed
- "Tech Leadership" is a display name (not a project key)
- No mapping in `team_mappings.yaml` (intentional)

### 2. What Defines a "Commitment"

**Definition:** Team has created an epic with non-red RAG status (green, yellow, or amber).

**Not committed:**
- No epic created
- Epic exists but RAG is red (blocked/at risk)
- Epic exists but RAG is missing/null

**Rationale:**
- Red RAG means blocked - not a real commitment
- Yellow/green/amber means team is working on it or ready to work
- Aligns with existing RAG validation logic in `check_planning.py`

### 3. Priority Conflict Detection

**Rules:**
1. Team commits to initiative B (lower priority) but not initiative A (higher priority) → conflict
2. Team appears in `teams_involved` for at least one Tech Leadership initiative but has zero green/yellow epics → missing commitment

**Display:** Group by team, show pattern
- Example: "Team X: Committed to #5, #7 but not #1, #2, #3"
- Overview format rather than individual conflicts
- More readable than listing every conflict

### 4. Configuration Structure

**File:** `config/tech_leadership_priorities.yaml`

**Format:**
```yaml
# Tech Leadership initiative priorities for 26 Q2
# Listed in priority order (first = highest priority)
quarter: "26 Q2"
priorities:
  - INIT-1234  # Highest priority
  - INIT-5678
  - INIT-9012
  - INIT-3456  # Lowest priority
```

**Handling edge cases:**
- Initiative in config not found in quarter data → show warning and skip
- Tech Leadership initiative not in config → show warning in report (not prioritized)
- Empty list → fail with error (must have priorities to validate)

### 5. Report Structure

**Four sections:**

#### Section 1: Priority Conflicts
- **Purpose:** Show teams committing to lower-priority initiatives while skipping higher-priority ones
- **Format:** Group by team, show commitment pattern
- **Example:**
  ```
  Team X (Manager: @Jane Smith)
    Committed to: INIT-5678 (#2), INIT-9012 (#3)
    Missing higher priorities: INIT-1234 (#1)
  ```

#### Section 2: Missing Commitments
- **Purpose:** Show teams expected to contribute but with zero green/yellow epics
- **Format:** List teams with expected initiatives they're not committing to
- **Example:**
  ```
  Team Y (Manager: @John Doe)
    Expected in: INIT-1234, INIT-5678, INIT-9012
    Committed to: None (no green/yellow epics)
  ```

#### Section 3: Initiative Health Dashboard
- **Purpose:** Initiative-centric view showing which teams committed
- **Format:** For each Tech Leadership initiative, show expected vs actual commitments
- **Example:**
  ```
  INIT-1234 (Priority #1): Platform Resilience
    Expected teams: Team X, Team Y, Team Z
    Committed: Team Z (green), Team Y (yellow)
    Missing: Team X
  ```

#### Section 4: Action Items for Managers
- **Purpose:** Actionable checklist grouped by manager
- **Format:** Same pattern as `check_planning.py` action items
- **Example:**
  ```
  @Jane Smith (Team X):
    [ ] Review commitment to INIT-5678 (#2) vs INIT-1234 (#1) priority
    [ ] Justify why INIT-1234 is not committed or update epic RAG status
  ```

### 6. Data Quality Issues

**Missing `teams_involved`:**
- Flag as data quality issue
- Show warning in report header
- Exclude from priority conflict validation (can't validate without expectations)
- Still show in Initiative Health Dashboard with actual contributors

**Rationale:**
- Aligns with existing validation philosophy: fix data quality first
- Makes gaps visible without failing validation
- Encourages fixing root cause (missing data in Jira)

### 7. Command-Line Interface

**Basic usage:**
```bash
# Console report for current quarter
python validate_tech_leadership.py --quarter "26 Q2"

# Generate Slack messages
python validate_tech_leadership.py --quarter "26 Q2" --slack

# Verbose output for debugging
python validate_tech_leadership.py --quarter "26 Q2" --verbose
```

**Flags:**
- `--quarter "YY QN"` - Required. Quarter to validate (e.g., "26 Q2")
- `--slack` - Generate Slack bulk messages file (grouped by manager)
- `--verbose` - Include verbose output with additional details
- `--config PATH` - Custom config path (default: `config/tech_leadership_priorities.yaml`)

**Output:**
- Console: Color-coded report with four sections
- Slack: Timestamped file in `data/slack_messages_tech_leadership_YYYY-MM-DD_HHMMSS.txt`
- Exit codes:
  - `0` - No priority conflicts or missing commitments
  - `1` - Conflicts or missing commitments found
  - `2` - Configuration error (missing file, invalid format, empty priorities)

### 8. Integration with Existing Features

**Approach:** Standalone mode only (for now)

**What this means:**
- Does NOT integrate with `check_planning.py` output
- Does NOT add sections to HTML dashboard
- Does NOT extend existing Slack messages
- Focused, single-purpose tool

**Future integration opportunities:**
- Could add summary to workload dashboard HTML
- Could merge Slack messages with planning validation messages
- Could be combined in a "mega validation" mode

**Rationale for standalone:**
- Simpler to implement and test
- Clearer separation of concerns
- Easier to adopt gradually
- Reduces complexity in existing scripts

### 9. Discovery Initiative Handling

**Rule:** Exclude Discovery initiatives from priority validation

**Implementation:**
- Check if initiative summary starts with `[Discovery]`
- Skip priority validation even if listed in config
- Do not flag as conflict or missing commitment
- Aligns with `check_planning.py` pattern

### 10. Multi-Team Manager Grouping

**Rule:** One Slack message per manager (consolidate all teams)

**Implementation:**
- Group action items by manager Slack ID
- Create subsections for each team the manager oversees
- Manager sees complete picture across all their teams
- Follows existing `check_planning.py` pattern

### 11. Completed Initiative Filtering

**Rule:** Silently filter Done/Cancelled initiatives

**Implementation:**
- Auto-exclude initiatives with status "Done" or "Cancelled"
- No warnings shown if they appear in priority config
- Keeps output focused on active work
- Allows priority config to be reused across quarters

### 12. Multiple Epic RAG Handling

**Rule:** All epics must be non-red for team to be considered committed

**Implementation:**
- If team has multiple epics for same initiative, check all RAG statuses
- If ANY epic is red → team is NOT committed
- All epics must be green/yellow/amber for commitment
- Conservative approach ensures quality commitments

## Technical Architecture

### File Structure

**New files:**
```
validate_tech_leadership.py           # Main script
config/tech_leadership_priorities.yaml # Priority configuration
templates/tech_leadership_console.j2   # Console report template
templates/tech_leadership_slack.j2     # Slack message template (or reuse existing)
tests/test_validate_tech_leadership.py # Test suite
```

**Shared modules (from Phase 2 refactoring):**
```
lib/manager_info.py      # Load team managers, validate Slack config
lib/action_items.py      # Action item extraction and formatting
lib/slack_messages.py    # Slack message generation
lib/jira_url.py          # Jira base URL from config
```

### Data Flow

1. **Load quarter data:**
   - Use `lib/file_utils.py` to find latest extraction or snapshot
   - Parse JSON data structure

2. **Load priority config:**
   - Read `config/tech_leadership_priorities.yaml`
   - Validate format and quarter match

3. **Filter Tech Leadership initiatives:**
   - Select initiatives where `owner_team == "Tech Leadership"`
   - Cross-reference with priority config
   - Flag unlisted initiatives

4. **Analyze team commitments:**
   - For each initiative in priority list:
     - Get expected teams from `teams_involved`
     - Get actual commitments from `contributing_teams`
     - Check epic RAG status (non-red = committed)
   - Build commitment matrix (team × initiative)

5. **Detect conflicts:**
   - For each team:
     - Find initiatives they committed to (sorted by priority)
     - Find initiatives they're expected in but didn't commit to
     - Identify higher-priority gaps
   - Group conflicts by team

6. **Generate action items:**
   - Extract conflicts and missing commitments as action items
   - Enrich with manager information from `team_mappings.yaml`
   - Sort by priority

7. **Render output:**
   - Console: Jinja2 template with four sections
   - Slack (optional): Group by manager, generate timestamped file

### Code Reuse Strategy

**Reuse from `check_planning.py`:**
- Quarter filtering logic
- Data quality checking patterns
- Action item extraction structure
- Slack message generation flow
- Template rendering setup

**Extract to shared modules (aligns with Phase 2 plan):**
- Manager info loading → `lib/manager_info.py`
- Action item building → `lib/action_items.py`
- Slack file generation → `lib/slack_messages.py`
- Jira URL construction → `lib/jira_url.py`

**New logic specific to Tech Leadership:**
- Priority config loading and validation
- Commitment matrix building
- Priority conflict detection
- Initiative health dashboard

## Resolved Questions

### 1. Should Discovery initiatives be excluded from Tech Leadership validation?

**Decision:** Exclude Discovery initiatives

**Rationale:** Discovery work is exploratory and shouldn't be prioritized the same way as delivery work. Even if a Discovery initiative appears in the priority config, skip validation for it. This aligns with the existing `check_planning.py` pattern where Discovery initiatives are exempt from epic validation.

### 2. How to handle multi-team managers?

**Decision:** One message per manager (consolidate all teams)

**Rationale:** Follow the existing `check_planning.py` pattern where managers who oversee multiple teams receive one Slack message with team subsections. This gives managers a complete picture of all their teams' commitments in one place.

### 3. Should initiatives with status "Done" or "Cancelled" be excluded from priority validation?

**Decision:** Filter silently (no warnings)

**Rationale:** Automatically exclude Done/Cancelled initiatives from validation without showing warnings. This keeps the output clean and focused on active work. If stale initiatives appear in the priority config, they're simply ignored rather than flagged.

### 4. What if a team has multiple epics for the same initiative with different RAG statuses?

**Decision:** All epics must be non-red

**Rationale:** If any epic is red, the team is not considered committed. This conservative approach ensures quality commitments - all workstreams must be on track (green/yellow), not just some. A single red epic indicates blocking issues that prevent the team from truly committing to the initiative.

## Success Criteria

**Functionality:**
- [ ] Correctly identifies Tech Leadership initiatives (`owner_team == "Tech Leadership"`)
- [ ] Loads priorities from config file (simple ordered list)
- [ ] Detects priority conflicts (committed to lower priority, not higher priority)
- [ ] Detects missing commitments (in teams_involved but no green/yellow epics)
- [ ] Generates four report sections (conflicts, missing, initiative health, action items)
- [ ] Console output displays with color coding and hyperlinks
- [ ] `--slack` flag generates timestamped message file grouped by manager
- [ ] Handles edge cases gracefully (missing initiatives, unlisted initiatives, empty teams_involved)

**Quality:**
- [ ] Test coverage >80%
- [ ] All edge cases tested
- [ ] No hardcoded company-specific data (uses config for Jira URLs)
- [ ] Follows Four Rules of Simple Design
- [ ] Clear error messages with field names
- [ ] Fast execution (<5 seconds for 100 initiatives)

**Documentation:**
- [ ] README.md section explaining Tech Leadership validation
- [ ] Example config file with comments
- [ ] Docstrings on all functions
- [ ] Solution document after implementation

**User Experience:**
- [ ] Clear, actionable console output
- [ ] Manager action items are specific and checkable
- [ ] Slack messages are concise and include all context (initiative links, priority numbers)
- [ ] Exit codes allow scripting and CI integration

## Next Steps

1. **Proceed to planning** - Run `/ce:plan` to create detailed implementation plan
2. **Consider Phase 2 alignment** - Coordinate with existing plan to extract shared utilities to `lib/` modules

## Related Work

**Existing patterns to follow:**
- `/Users/stefano.iasi/git/jira-dependencies-tracking/check_planning.py` - Validation structure, action items
- `/Users/stefano.iasi/git/jira-dependencies-tracking/assess_workload.py` - Data loading, team commitment analysis
- `/Users/stefano.iasi/git/jira-dependencies-tracking/docs/plans/2026-04-03-001-feat-action-items-workload-analysis-plan.md` - Phase 2 refactoring plan

**Dependencies:**
- Existing data extraction (`scan.py`)
- Existing config structure (`config/jira_config.yaml`, `config/team_mappings.yaml`)
- Existing template infrastructure (`lib/template_renderer.py`)
