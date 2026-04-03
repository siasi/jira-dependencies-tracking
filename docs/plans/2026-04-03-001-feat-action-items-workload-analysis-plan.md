---
title: Add action items and Slack notifications to analyze_workload.py
type: feat
status: active
date: 2026-04-03
---

# Add action items and Slack notifications to analyze_workload.py

## Overview

Extend `analyze_workload.py` to track data quality issues as actionable items with manager assignments and Slack notification support, matching the pattern established in `validate_planning.py`. Then refactor shared code between both scripts into centralized utilities to eliminate duplication.

## Problem Statement / Motivation

**Current State:**
- `analyze_workload.py` shows data quality issues with `--show-quality` flag but doesn't track them as actionable items
- No manager attribution for quality issues
- No Slack notification capability
- Significant code duplication between `validate_planning.py` and `analyze_workload.py` for:
  - Action item extraction logic
  - Manager information loading
  - Slack message generation
  - Template rendering setup

**Desired State:**
- Data quality issues formatted as action items with checkboxes and manager mentions
- `--slack` option to generate Slack notification file grouped by manager
- Shared utilities in `lib/` for action extraction, Slack generation, and manager info loading
- Both scripts use consistent patterns and reusable components

## Proposed Solution

### Phase 1: Implement Action Items in analyze_workload.py

Add action item extraction and formatting to `analyze_workload.py` following the exact pattern from `validate_planning.py`:

1. **Extract action items from data quality issues**
   - Create `extract_workload_actions()` function
   - Convert quality issues to flat action item list
   - Include all metadata (initiative, team, manager, priority)

2. **Format console output with action items**
   - Update `--show-quality` output to show checkbox format
   - Include manager Notion handles from `team_managers`
   - Group by initiative with action lists

3. **Add --slack flag**
   - Generate Slack messages grouped by manager
   - Save to timestamped file in `data/`
   - Reuse Jinja2 template pattern

### Phase 2: Refactor Shared Code

Extract duplicated code into `lib/` modules:

1. **lib/action_items.py** (NEW)
   - `extract_action_items()` - Generic extraction interface
   - `ActionItem` dataclass for type safety
   - Priority constants and action type definitions

2. **lib/manager_info.py** (NEW)
   - `load_team_managers()` - Centralized manager loading
   - `validate_slack_config()` - Config validation
   - Handle backward compatibility (legacy string format)

3. **lib/slack_messages.py** (NEW)
   - `generate_slack_messages()` - Generic Slack generation
   - Group by manager logic
   - File output handling

4. **Update both scripts** to use shared utilities

## Technical Considerations

### Action Types for analyze_workload.py

Define action types matching data quality issues:

```python
ACTION_TYPES = {
    'missing_owner': {
        'priority': 1,
        'description': 'Set owner_team for initiative',
        'emoji': ':raising_hand:'
    },
    'missing_strategic_objective': {
        'priority': 2,
        'description': 'Set strategic objective',
        'emoji': ':dart:'
    },
    'invalid_strategic_objective': {
        'priority': 3,
        'description': 'Fix invalid strategic objective value',
        'emoji': ':warning:'
    },
    'missing_epics': {
        'priority': 4,
        'description': 'Create epic',
        'emoji': ':warning:'
    }
}
```

### Action Item Data Structure

Follow validate_planning.py pattern:

```python
{
    'initiative_key': 'INIT-1482',
    'initiative_title': '[AMZ] Direct Debit Safeguarding...',
    'initiative_status': 'In Progress',
    'initiative_url': 'https://truelayer.atlassian.net/browse/INIT-1482',
    'section': 'data_quality',
    'action_type': 'missing_owner',
    'priority': 1,
    'responsible_team': 'CBP',
    'responsible_team_key': 'CBPPE',
    'responsible_manager_name': 'Ariel Rehano',
    'responsible_manager_notion': '@Ariel Rehano',
    'responsible_manager_slack_id': 'U03HN9A9XGA',
    'description': 'Set owner_team for initiative',
    'epic_key': None,
    'epic_title': None,
    'epic_rag': None
}
```

### Console Output Format

Match validate_planning.py checkbox format:

```
INIT-1482: [AMZ] Direct Debit Safeguarding Risk Mitigation

   ⚠️  Missing owner_team - Action:
       [ ] Set the owner_team for the initiative

INIT-1499: [Discovery] Global user ID problem
   Owner: User Network

   ⚠️  Missing dependencies - Action:
       [ ] Payments Risk (RSK) to create epic @Kevin Plattern
```

### Slack Message Format

Reuse `notification_slack.j2` template with same structure:

```
Recipient: U03HN9A9XGA
Message: Hi Ariel! Here are your action items from the latest workload analysis:

You have 3 action items across 2 initiatives.

INIT-1482: <https://truelayer.atlassian.net/browse/INIT-1482>
:raising_hand: Missing owner - Set owner_team

INIT-1491: <https://truelayer.atlassian.net/browse/INIT-1491>
:raising_hand: Missing assignee - Set assignee
:warning: Missing dependencies - Create epic

---
```

### Refactoring Strategy

**Extraction Order:**
1. Start with `lib/manager_info.py` - lowest-level, no dependencies
2. Then `lib/action_items.py` - depends only on manager_info
3. Then `lib/slack_messages.py` - depends on both above
4. Update `validate_planning.py` first (smaller changes)
5. Update `analyze_workload.py` last (benefits from tested refactoring)

**Backward Compatibility:**
- Keep existing function signatures in both scripts
- Add new internal functions that delegate to lib/
- Deprecation warnings for direct usage (future cleanup)

**Testing Strategy:**
- Test each lib/ module independently
- Test both scripts still work after refactoring
- Compare output before/after refactoring (should be identical)

## Implementation Phases

### Phase 1: Add Action Items to analyze_workload.py

**Files to modify:**
- `analyze_workload.py`

**Tasks:**

1. **Create extract_workload_actions() function**
   ```python
   def extract_workload_actions(analysis: Dict, team_managers: Dict) -> List[Dict[str, Any]]:
       """Extract action items from workload analysis data quality issues.

       Returns list of action item dicts with structure:
       {
           'initiative_key': str,
           'initiative_title': str,
           'initiative_url': str,
           'action_type': str,
           'priority': int,
           'responsible_team': str,
           'responsible_manager_notion': str,
           'responsible_manager_slack_id': str,
           'description': str,
           ...
       }
       """
       # Extract from:
       # - analysis['initiatives_without_owner']
       # - analysis['initiatives_missing_strategic_objective']
       # - analysis['initiatives_invalid_strategic_objective']
       # - analysis['initiatives_without_epics']
   ```

2. **Update print_workload_report() for action item format**
   - Add action item display logic when `show_quality=True`
   - Format as checkboxes with manager mentions
   - Group by initiative, show all actions per initiative
   - Sort by priority within each initiative

3. **Add generate_workload_slack_messages() function**
   ```python
   def generate_workload_slack_messages(analysis: Dict, output_dir: Path) -> None:
       """Generate Slack bulk messages for workload quality action items."""
       # 1. Validate all teams have slack_id
       # 2. Extract actions using extract_workload_actions()
       # 3. Group by manager → team → initiative → actions
       # 4. Sort by priority
       # 5. Render using notification_slack.j2
       # 6. Save to data/slack_messages_workload_YYYY-MM-DD_HHMMSS.txt
   ```

4. **Add --slack argument to argparse**
   ```python
   parser.add_argument(
       '--slack',
       action='store_true',
       help='Generate Slack bulk messages for workload quality action items'
   )
   ```

5. **Add action type constants and helper functions**
   ```python
   # Action type definitions
   WORKLOAD_ACTION_TYPES = {
       'missing_owner': {'priority': 1, 'description': '...'},
       # ...
   }

   def _base_workload_context(initiative: Dict, section: str) -> Dict:
       """Build base initiative context."""

   def _add_manager_info_workload(action: Dict, team_key: str) -> Dict:
       """Enrich action with manager metadata."""
   ```

**Success Criteria:**
- [ ] `python3 analyze_workload.py --quarter "26 Q2" --show-quality` displays action items with checkboxes
- [ ] Manager Notion handles appear in action items
- [ ] `python3 analyze_workload.py --quarter "26 Q2" --slack` generates Slack message file
- [ ] Slack messages grouped by manager with correct formatting
- [ ] All existing tests pass
- [ ] New tests added for action extraction

### Phase 2: Extract Shared Manager Info Module

**Files to create:**
- `lib/manager_info.py`

**Files to modify:**
- `validate_planning.py`
- `analyze_workload.py`

**Tasks:**

1. **Create lib/manager_info.py**
   ```python
   """Manager information loading and validation."""
   from pathlib import Path
   from typing import Dict, Optional
   import yaml

   def load_team_managers(config_path: Optional[Path] = None) -> Dict[str, Dict[str, Optional[str]]]:
       """Load team manager information from team_mappings.yaml.

       Returns:
           Dict mapping project_key to manager info:
           {
               'CBPPE': {
                   'notion_handle': '@Ariel Rehano',
                   'slack_id': 'U03HN9A9XGA'
               },
               ...
           }

       Handles backward compatibility:
       - Legacy format: "CBPPE": "@Ariel Rehano"
       - New format: "CBPPE": {"notion_handle": "@Ariel", "slack_id": "U..."}
       """

   def validate_slack_config(team_managers: Dict[str, Dict]) -> None:
       """Validate all teams have slack_id configured.

       Raises:
           ValueError: If any team missing slack_id
       """

   def get_manager_info(team_key: str, team_managers: Dict) -> Dict[str, str]:
       """Get manager info for team, returning empty dict if not found."""
   ```

2. **Update validate_planning.py to use lib/manager_info**
   - Replace `_load_team_managers()` with `from lib.manager_info import load_team_managers`
   - Replace `_validate_slack_config()` with import
   - Update all call sites
   - Keep old functions as deprecated wrappers (optional, for safety)

3. **Update analyze_workload.py to use lib/manager_info**
   - Import `load_team_managers` from lib.manager_info
   - Remove local manager loading logic from `load_team_mappings()`
   - Update return tuple to use shared function

**Success Criteria:**
- [ ] `lib/manager_info.py` module created with all functions
- [ ] Both scripts import and use shared module
- [ ] All existing tests pass
- [ ] New tests for lib/manager_info module
- [ ] Backward compatibility maintained (legacy format works)

### Phase 3: Extract Shared Action Items Module

**Files to create:**
- `lib/action_items.py`

**Files to modify:**
- `validate_planning.py`
- `analyze_workload.py`

**Tasks:**

1. **Create lib/action_items.py**
   ```python
   """Action item extraction and formatting."""
   from dataclasses import dataclass
   from typing import Dict, List, Optional, Any
   from lib.manager_info import get_manager_info

   @dataclass
   class ActionItem:
       """Structured action item with all metadata."""
       initiative_key: str
       initiative_title: str
       initiative_status: str
       initiative_url: str
       section: str
       action_type: str
       priority: int
       responsible_team: str
       responsible_team_key: str
       responsible_manager_name: str
       responsible_manager_notion: str
       responsible_manager_slack_id: str
       description: str
       epic_key: Optional[str] = None
       epic_title: Optional[str] = None
       epic_rag: Optional[str] = None

       def to_dict(self) -> Dict[str, Any]:
           """Convert to dictionary for template rendering."""

   def build_base_context(initiative: Dict, section: str, base_url: str) -> Dict:
       """Build base initiative context for action items."""

   def enrich_with_manager_info(
       action: Dict,
       team_key: str,
       team_display: str,
       team_managers: Dict
   ) -> Dict:
       """Enrich action dict with manager metadata."""

   def sort_actions_by_priority(actions: List[Dict]) -> List[Dict]:
       """Sort actions by priority (1=highest)."""
   ```

2. **Update validate_planning.py extract_manager_actions()**
   - Import action_items helpers
   - Use shared `build_base_context()` and `enrich_with_manager_info()`
   - Reduce duplication in action building

3. **Update analyze_workload.py extract_workload_actions()**
   - Use shared helpers from action_items module
   - Consistent structure across both scripts

**Success Criteria:**
- [ ] `lib/action_items.py` module created with ActionItem dataclass
- [ ] Helper functions extracted and reusable
- [ ] Both scripts use shared functions
- [ ] All existing tests pass
- [ ] New tests for lib/action_items module

### Phase 4: Extract Shared Slack Messages Module

**Files to create:**
- `lib/slack_messages.py`

**Files to modify:**
- `validate_planning.py`
- `analyze_workload.py`

**Tasks:**

1. **Create lib/slack_messages.py**
   ```python
   """Slack bulk message generation."""
   from pathlib import Path
   from typing import Dict, List
   from collections import defaultdict
   from datetime import datetime
   from lib.template_renderer import get_template_environment
   from lib.manager_info import validate_slack_config

   def group_actions_by_manager(actions: List[Dict]) -> List[Dict]:
       """Group actions by manager → team → initiative.

       Returns list of manager message dicts:
       [
           {
               'manager_name': 'Ariel Rehano',
               'slack_id': 'U03HN9A9XGA',
               'total_actions': 5,
               'total_initiatives': 3,
               'teams': [
                   {
                       'team_name': 'CBP',
                       'team_key': 'CBPPE',
                       'initiatives': [
                           {
                               'key': 'INIT-1234',
                               'title': '...',
                               'url': '...',
                               'actions': [...]
                           }
                       ]
                   }
               ]
           }
       ]
       """

   def generate_slack_file(
       actions: List[Dict],
       output_dir: Path,
       filename_prefix: str = 'slack_messages'
   ) -> Path:
       """Generate Slack bulk messages file from action items.

       Args:
           actions: Flat list of action item dicts
           output_dir: Directory to save file (e.g., data/)
           filename_prefix: Prefix for output file

       Returns:
           Path to generated file
       """
       # 1. Validate config (all teams have slack_id)
       # 2. Group by manager
       # 3. Render template
       # 4. Write to timestamped file
       # 5. Print summary to console
   ```

2. **Update validate_planning.py generate_slack_messages()**
   - Replace grouping logic with `group_actions_by_manager()`
   - Replace file generation with `generate_slack_file()`
   - Keep function signature for backward compatibility

3. **Update analyze_workload.py generate_workload_slack_messages()**
   - Use shared `generate_slack_file()` function
   - Pass workload-specific filename prefix

4. **Update notification_slack.j2 template** (if needed)
   - Ensure template works for both validation and workload actions
   - Add any missing action type emojis

**Success Criteria:**
- [ ] `lib/slack_messages.py` module created
- [ ] Both scripts use shared Slack generation
- [ ] Slack files generated with correct format
- [ ] All existing tests pass
- [ ] New tests for lib/slack_messages module

### Phase 5: Testing & Documentation

**Tasks:**

1. **Create comprehensive tests**
   ```
   tests/lib/test_manager_info.py
   tests/lib/test_action_items.py
   tests/lib/test_slack_messages.py
   ```
   - Test each module independently
   - Test backward compatibility
   - Test error handling (missing config, invalid data)
   - Test edge cases (empty results, missing managers)

2. **Integration tests**
   - Test validate_planning.py still works after refactoring
   - Test analyze_workload.py with new action items
   - Compare output before/after refactoring

3. **Update documentation**
   - Add docstrings to all new functions
   - Update CLAUDE.md if needed
   - Create solution document: `docs/solutions/refactoring/action-items-extraction-pattern.md`

4. **Manual testing**
   ```bash
   # Test analyze_workload with action items
   python3 analyze_workload.py --quarter "26 Q2" --show-quality

   # Test Slack generation
   python3 analyze_workload.py --quarter "26 Q2" --slack

   # Test validate_planning still works
   python3 validate_planning.py --quarter "26 Q2" --slack
   ```

**Success Criteria:**
- [ ] All tests pass (existing + new)
- [ ] Code coverage maintained or improved
- [ ] Documentation complete
- [ ] Manual testing confirms correct behavior

## Acceptance Criteria

### Phase 1: Action Items in analyze_workload.py
- [x] `--show-quality` displays action items in checkbox format
- [x] Manager Notion handles appear in action items (e.g., "@Ariel Rehano")
- [x] Action items grouped by initiative with priority sorting
- [x] `--slack` flag generates Slack message file in `data/` directory
- [x] Slack messages grouped by manager with correct structure
- [x] Console output shows summary: "Total managers: X, Total action items: Y"

### Phase 2: Shared Manager Info Module
- [ ] `lib/manager_info.py` created with load/validate functions
- [ ] Both scripts use shared module
- [ ] Backward compatibility maintained (legacy string format works)
- [ ] All existing tests pass
- [ ] New tests for manager_info module (>80% coverage)

### Phase 3: Shared Action Items Module
- [ ] `lib/action_items.py` created with ActionItem dataclass
- [ ] Helper functions extracted and reusable
- [ ] Both scripts use shared functions
- [ ] All existing tests pass
- [ ] New tests for action_items module (>80% coverage)

### Phase 4: Shared Slack Messages Module
- [ ] `lib/slack_messages.py` created with grouping/generation functions
- [ ] Both scripts use shared Slack generation
- [ ] Slack file format consistent across both scripts
- [ ] All existing tests pass
- [ ] New tests for slack_messages module (>80% coverage)

### Phase 5: Testing & Documentation
- [ ] All tests pass (100% of existing tests)
- [ ] Code coverage >80% for new lib/ modules
- [ ] Documentation complete (docstrings, CLAUDE.md updated)
- [ ] Solution document created for future reference
- [ ] Manual testing confirms correct behavior

## Success Metrics

**Code Quality:**
- Lines of duplicated code reduced by >200 lines
- Number of modules with manager loading logic: 2 → 1
- Number of modules with Slack generation logic: 2 → 1
- Test coverage for lib/ modules: >80%

**Functionality:**
- Action items displayed in both scripts with consistent format
- Slack messages generated from both scripts with same structure
- Manager information centralized and validated
- Zero regression in existing functionality

## Dependencies & Risks

**Dependencies:**
- Existing `lib/template_renderer.py` module
- Existing `templates/notification_slack.j2` template
- Existing `config/team_mappings.yaml` structure

**Risks:**

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking existing scripts during refactoring | High | Phase approach - refactor incrementally, test after each phase |
| Backward compatibility with legacy config format | Medium | Maintain support for both string and dict formats in manager loading |
| Slack message format changes | Low | Reuse existing template, only extend with new action types |
| Test coverage gaps | Medium | Write tests for each lib/ module before updating scripts |

## Sources & References

### Internal References

**Existing Patterns:**
- `/Users/stefano.iasi/git/jira-dependencies-tracking/validate_planning.py:583-908` - extract_manager_actions() pattern
- `/Users/stefano.iasi/git/jira-dependencies-tracking/validate_planning.py:911-1061` - generate_slack_messages() pattern
- `/Users/stefano.iasi/git/jira-dependencies-tracking/lib/template_renderer.py` - Jinja2 setup
- `/Users/stefano.iasi/git/jira-dependencies-tracking/lib/common_formatting.py` - Link formatting helpers

**Configuration:**
- `/Users/stefano.iasi/git/jira-dependencies-tracking/config/team_mappings.yaml` - Manager info structure

**Templates:**
- `/Users/stefano.iasi/git/jira-dependencies-tracking/templates/notification_slack.j2` - Slack message format

**Institutional Learnings:**
- `docs/solutions/code-quality/cli-error-handling-duplication.md` - DRY principle application
- `docs/brainstorms/SLACK_INTEGRATION.md` - Slack integration design
- `docs/plans/2026-03-27-001-feat-dust-bulk-messages-integration-plan.md` - Action extraction pattern
- `docs/plans/2026-03-30-001-refactor-toolkit-consistency-reorganization-plan.md` - Shared module architecture

### Related Work

**Previous Commits:**
- feat(analyze_workload): add --show-quality flag for data quality issues (088f0b7)
- refactor(analyze_workload): remove CSV format from console report (c103811)
