---
title: "Hardcoded company data in workload analysis causing security exposure"
date: "2026-04-03"
category: "logic-errors"
component: "analyze_workload"
tags:
  - "data-sanitization"
  - "configuration-management"
  - "jira-integration"
  - "action-items"
severity: "high"
status: "resolved"
---

# Hardcoded Company Data Sanitization and Discovery Initiative Handling

## Problem

The `analyze_workload.py` script had three distinct issues that were discovered during implementation of the action items feature:

1. **Incorrect initiative owner display**: Action items showed the wrong team as the initiative owner (displayed "User Network" when actual owner was "Tech Leadership")
2. **Discovery initiatives incorrectly flagged**: Discovery initiatives were being flagged for missing epics when they should be exempt from this validation
3. **Security exposure from hardcoded data**: Script contained hardcoded company-specific URLs, manager names, Slack IDs, and team identifiers

## Root Cause (Technical Explanation)

### Issue 1: Incorrect Initiative Owner Display (commit 10647f5)

**Root Cause**: Data model confusion between action responsibility and initiative ownership. When displaying data quality issues for missing epics, the code incorrectly used `action['responsible_team']` to display the initiative owner. However, for `missing_epics` action types, `responsible_team` refers to the team that needs to CREATE the epic (the contributing team), not the team that OWNS the initiative. This resulted in displaying "Owner: User Network" when the actual owner was "Tech Leadership".

**Technical Detail**: The bug was in the `print_workload_report()` function at lines 1014-1017. The code iterated through actions looking for `action['responsible_team']`, which conflated two distinct concepts:
- Initiative owner (stored in `initiative_owner_teams` dict)
- Team responsible for the action (stored in `action['responsible_team']`)

### Issue 2: Discovery Initiatives Incorrectly Flagged for Missing Epics (commit 4b6adb1)

**Root Cause**: Missing business rule implementation. Discovery initiatives (prefixed with `[Discovery]`) are exploratory by nature and don't require contributing team epics. However, the epic validation logic treated all initiatives uniformly, resulting in 3 false-positive action items for Discovery initiatives (INIT-1499, INIT-1488, INIT-1165).

**Technical Detail**: The `analyze_workload()` function lacked a check for Discovery initiatives before validating epic completeness (around line 332). The validation rule at line 332 needed an additional condition to skip Discovery initiatives, similar to how `validate_planning.py` already handled them.

### Issue 3: Hardcoded Company-Specific Data Security Issue (commit e53eac6)

**Root Cause**: Security vulnerability from hardcoded sensitive data. The code contained:
- Hardcoded Jira URL (`https://truelayer.atlassian.net`)
- Real manager names in docstring examples ("Ariel Rehano")
- Real Slack IDs in docstring examples ("U03HN9A9XGA")
- Real team names in examples ("CBP", "CBPPE")

**Technical Detail**: The `extract_workload_actions()` function constructed Jira URLs using a hardcoded base URL at line 572, and docstrings contained real production data. This violated security best practices by exposing company-specific identifiers in code.

## Solution (Step-by-Step Fix with Code Examples)

### Fix 1: Display Correct Initiative Owner (commit 10647f5)

**Step 1**: Replace the loop-based approach with direct dictionary lookup using `initiative_owner_teams`.

**Before** (lines 1014-1017):
```python
# Find any action with owner info
for action in init_actions:
    if action['responsible_team']:
        print(f"   Owner: {action['responsible_team']}")
        break
```

**After** (lines 1014-1017):
```python
# Get actual owner from initiative_owner_teams
owner_key = initiative_owner_teams.get(init_key, '')
if owner_key:
    owner_display = reverse_team_mappings.get(owner_key, owner_key)
    print(f"   Owner: {owner_display}")
```

**Key Changes**:
- Use `initiative_owner_teams[init_key]` to get the actual initiative owner
- Apply reverse team mapping to convert project key to display name
- Eliminates conflation between action responsibility and initiative ownership

### Fix 2: Exclude Discovery Initiatives from Epic Checks (commit 4b6adb1)

**Step 1**: Add a helper function to detect Discovery initiatives.

**Added** (lines 76-89):
```python
def is_discovery_initiative(initiative: Dict) -> bool:
    """Check if an initiative is a discovery initiative.

    Discovery initiatives (prefixed with [Discovery]) are exempt from
    certain validation checks like missing epics.

    Args:
        initiative: Initiative dict with 'summary' field

    Returns:
        True if summary starts with "[Discovery]", False otherwise
    """
    summary = initiative.get('summary', '')
    return summary.startswith('[Discovery]')
```

**Step 2**: Apply the Discovery check before epic validation.

**Before** (line 332):
```python
# Check for epic count mismatch (only if owner is not in excluded teams)
if teams_involved and (not normalized_owner or normalized_owner not in excluded_teams):
```

**After** (lines 341-350):
```python
# Discovery initiatives are exempt from epic checks
is_discovery = is_discovery_initiative(initiative)
teams_involved = normalize_teams_involved(initiative.get('teams_involved'))
# ... (teams_with_epics calculation)

# Check for epic count mismatch (only if owner is not in excluded teams and not a discovery initiative)
if not is_discovery and teams_involved and (not normalized_owner or normalized_owner not in excluded_teams):
```

**Impact**: Reduced false positives from 34 to 31 action items (console) and 25 to 22 (Slack).

### Fix 3: Remove Hardcoded Company-Specific Data (commit e53eac6)

**Step 1**: Create a dynamic Jira URL resolver that reads from config/environment.

**Added** (lines 20-47):
```python
def get_jira_base_url() -> str:
    """Get Jira base URL from config or environment variable.

    Returns:
        Jira base URL (e.g., 'https://company.atlassian.net')
    """
    # Try environment variable first
    if env_url := os.getenv('JIRA_BASE_URL'):
        return env_url.rstrip('/')

    # Fall back to config file
    config_file = Path(__file__).parent / 'config' / 'jira_config.yaml'
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                if instance := config.get('jira', {}).get('instance'):
                    # Instance may have trailing slash, normalize it
                    base = instance.rstrip('/')
                    # Add https:// if not present
                    if not base.startswith('http'):
                        base = f'https://{base}'
                    return base
        except Exception:
            pass

    # Fallback to generic placeholder for safety
    return 'https://your-company.atlassian.net'
```

**Step 2**: Replace hardcoded URL with dynamic lookup.

**Before** (line 572):
```python
def _base_context(initiative: Dict, section: str) -> Dict:
    return {
        'initiative_key': initiative['key'],
        'initiative_title': initiative['summary'],
        'initiative_status': initiative.get('status', 'Unknown'),
        'initiative_url': f"https://truelayer.atlassian.net/browse/{initiative['key']}",
        'section': section
    }
```

**After** (lines 603-610):
```python
# Helper to build base initiative context
jira_base_url = get_jira_base_url()
def _base_context(initiative: Dict, section: str) -> Dict:
    return {
        'initiative_key': initiative['key'],
        'initiative_title': initiative['summary'],
        'initiative_status': initiative.get('status', 'Unknown'),
        'initiative_url': f"{jira_base_url}/browse/{initiative['key']}",
        'section': section
    }
```

**Step 3**: Sanitize docstring examples with generic placeholders.

**Before** (lines 531-543):
```python
{
    'initiative_key': 'INIT-1234',
    'initiative_title': 'Project Alpha',
    'initiative_url': 'https://truelayer.atlassian.net/browse/INIT-1234',
    'responsible_team': 'CBP',
    'responsible_team_key': 'CBPPE',
    'responsible_manager_name': 'Ariel Rehano',
    'responsible_manager_notion': '@Ariel Rehano',
    'responsible_manager_slack_id': 'U03HN9A9XGA',
}
```

**After** (lines 562-575):
```python
{
    'initiative_key': 'INIT-XXXX',
    'initiative_title': 'Initiative Title',
    'initiative_url': 'https://company.atlassian.net/browse/INIT-XXXX',
    'responsible_team': 'Team Display Name',
    'responsible_team_key': 'TEAMKEY',
    'responsible_manager_name': 'Manager Name',
    'responsible_manager_notion': '@Manager Name',
    'responsible_manager_slack_id': 'UXXXXXXXXXX',
}
```

**Security Benefits**:
- No company URLs in code
- No real manager names/IDs exposed
- Jira base URL read from gitignored config file
- Falls back to JIRA_BASE_URL environment variable
- Generic placeholder if both sources unavailable

## Investigation Steps

### Investigation for Fix 1 (Owner Display Bug)
1. **Observed symptom**: Console output showed "Owner: User Network" for an initiative actually owned by "Tech Leadership"
2. **Traced data flow**: Followed how owner information flows through the action items pipeline:
   - Initiative data → `initiative_owner_teams` dict (correct source)
   - Action data → `action['responsible_team']` (team responsible for THIS action)
3. **Identified conflation**: For `missing_epics` actions, `responsible_team` = team that needs to create epic (contributor), NOT the initiative owner
4. **Verified fix**: Changed to use `initiative_owner_teams[init_key]` as the authoritative source for owner display
5. **Result**: Owner now displays correctly for all action types

### Investigation for Fix 2 (Discovery Initiatives)
1. **Observed symptom**: 34 action items generated, including 3 for Discovery initiatives
2. **Checked business rules**: Reviewed `validate_planning.py` and found existing `is_discovery_initiative()` helper that exempts Discovery initiatives from certain checks
3. **Identified gap**: `analyze_workload.py` lacked the same Discovery exemption in epic validation logic
4. **Applied pattern**: Implemented identical `is_discovery_initiative()` check before epic validation
5. **Verified impact**: Action items reduced from 34 to 31 (console) and 25 to 22 (Slack)
6. **Confirmed examples**: INIT-1499, INIT-1488, INIT-1165 (all prefixed with `[Discovery]`) no longer flagged

### Investigation for Fix 3 (Security Hardcoding)
1. **Audited code**: Searched for hardcoded company-specific strings
2. **Found exposures**:
   - `https://truelayer.atlassian.net` in URL construction
   - Real manager names in docstrings
   - Real Slack IDs in docstrings
   - Real team identifiers in examples
3. **Designed solution**: Three-tier fallback for Jira URL:
   - JIRA_BASE_URL environment variable (highest priority)
   - `config/jira_config.yaml` (gitignored, safe)
   - Generic placeholder (fallback)
4. **Sanitized documentation**: Replaced all real data in docstrings with generic placeholders (XXXX patterns)
5. **Noted limitation**: One hardcoded URL remains in `templates/notification_slack.j2` (line 21, pre-existing), deferred to Phase 2 to avoid breaking `validate_planning.py`
6. **Verified security**: No company-specific data remains in analyze_workload.py

### Common Testing Approach
All three fixes were validated by:
1. Running analyze_workload.py with `--show-quality` flag
2. Comparing action item counts before/after
3. Verifying console output displays correctly
4. Checking that no regressions occurred in existing functionality

## Prevention Strategies

### 1. Configuration Management
- **Externalize all environment-specific data**: Never hardcode URLs, company names, team names, or other organization-specific data in source code
- **Use configuration hierarchy**: Implement a clear precedence order (environment variables → config files → safe defaults) to make configuration flexible and testable
- **Provide example files**: Always commit `.example` files for configuration (e.g., `jira_config.yaml.example`, `team_mappings.yaml.example`) while gitignoring actual config files
- **Safe fallback values**: When configuration is missing, use generic placeholders (e.g., `https://your-company.atlassian.net`) rather than real company data

### 2. Data Sanitization in Code
- **Avoid hardcoded business logic**: Use configuration files to define business rules like "which initiatives to exclude from validation" (e.g., Discovery initiatives)
- **Helper functions for data access**: Create dedicated functions (like `get_jira_base_url()`) to centralize data retrieval and make it easier to change sources
- **Validate docstrings and comments**: Review code documentation for hardcoded examples - use generic placeholders instead
- **Code review checklist**: Include "no hardcoded company data" as a mandatory review criterion

### 3. Domain Logic Separation
- **Special case handlers**: Create clear, named helper functions for business rule exceptions (e.g., `is_discovery_initiative()`) rather than inline conditionals
- **Document exceptions explicitly**: When certain entities are exempt from rules, make this explicit in function names and docstrings
- **Configuration over code**: Move special-case lists to configuration files when they might change (e.g., initiative prefixes to exclude)

### 4. Data Flow Correctness
- **Clear data contracts**: When passing data between functions (e.g., action items), clearly document which fields contain what data and their purpose
- **Semantic naming**: Use names that reflect data meaning (e.g., `initiative_owner_teams` vs `responsible_team` in actions) to prevent confusion
- **Lookup dictionaries**: Maintain separate lookup dictionaries for different data dimensions (owner, contributors, etc.) to avoid mixing concerns

## Best Practices

### 1. Configuration Architecture
```python
# GOOD: Layered configuration with safe defaults
def get_jira_base_url() -> str:
    # 1. Environment variable (highest priority)
    if env_url := os.getenv('JIRA_BASE_URL'):
        return env_url.rstrip('/')

    # 2. Config file
    config_file = Path(__file__).parent / 'config' / 'jira_config.yaml'
    if config_file.exists():
        # ... load from file

    # 3. Safe fallback (lowest priority)
    return 'https://your-company.atlassian.net'

# BAD: Hardcoded values
JIRA_URL = 'https://realcompany.atlassian.net'
```

### 2. Business Rule Handling
```python
# GOOD: Explicit, testable, documented
def is_discovery_initiative(initiative: Dict) -> bool:
    """Check if an initiative is a discovery initiative.

    Discovery initiatives (prefixed with [Discovery]) are exempt from
    certain validation checks like missing epics.
    """
    summary = initiative.get('summary', '')
    return summary.startswith('[Discovery]')

# Then use it clearly:
if not is_discovery and teams_involved:
    # ... validation logic

# BAD: Inline magic strings
if not initiative['summary'].startswith('[Discovery]') and teams_involved:
    # ... validation logic
```

### 3. Data Structure Design
```python
# GOOD: Separate concerns with clear mappings
initiative_owner_teams = {}        # Map: initiative_key → owner_team
initiative_contributing_teams = {} # Map: initiative_key → [contributing_teams]
reverse_team_mappings = {}         # Map: project_key → display_name

# When displaying, use the right source:
owner_display = reverse_team_mappings.get(initiative_owner_teams[init_key], owner_key)

# BAD: Overloading action fields
owner_display = action['responsible_team']  # This is the team creating the epic!
```

### 4. Gitignore Strategy
```gitignore
# Ignore actual configs with sensitive data
config/*.yaml
config/.env

# But preserve examples
!config/*.yaml.example
!config/.env.example

# Ignore generated outputs that may contain company data
data/
/*.md
!README.md
/*.html
/*.csv
```

### 5. Template and Documentation Hygiene
- Use `{{ jira_base_url }}` template variables instead of hardcoded URLs in templates
- Parameterize all environment-specific values in documentation
- Review commit messages for accidentally included sensitive data before pushing

## Testing Recommendations

### 1. Configuration Tests
```python
def test_get_jira_base_url_from_env():
    """Test Jira URL is read from environment variable."""
    with mock.patch.dict(os.environ, {'JIRA_BASE_URL': 'https://test.example.com/'}):
        assert get_jira_base_url() == 'https://test.example.com'

def test_get_jira_base_url_fallback():
    """Test Jira URL falls back to safe default when config missing."""
    with mock.patch.dict(os.environ, {}, clear=True):
        with mock.patch('pathlib.Path.exists', return_value=False):
            url = get_jira_base_url()
            assert url == 'https://your-company.atlassian.net'
            assert 'real-company' not in url  # No leaked company data
```

### 2. Business Rule Tests
```python
def test_discovery_initiative_excluded_from_epic_checks():
    """Test that [Discovery] initiatives skip missing epic validation."""
    test_data = {
        'initiatives': [
            {
                'key': 'INIT-1',
                'summary': '[Discovery] Explore new feature',
                'status': 'In Progress',
                'owner_team': 'TeamA',
                'teams_involved': ['TeamA', 'TeamB'],
                'contributing_teams': []  # No epics, but should not be flagged
            }
        ]
    }

    result = analyze_workload(json_file, {}, [], {}, quarter='26 Q2')
    assert len(result['initiatives_without_epics']) == 0

def test_normal_initiative_requires_epics():
    """Test that normal initiatives are flagged for missing epics."""
    test_data = {
        'initiatives': [
            {
                'key': 'INIT-1',
                'summary': 'Regular initiative',  # No [Discovery] prefix
                'status': 'In Progress',
                'owner_team': 'TeamA',
                'teams_involved': ['TeamA', 'TeamB'],
                'contributing_teams': []  # Missing epics - should be flagged
            }
        ]
    }

    result = analyze_workload(json_file, {}, [], {}, quarter='26 Q2')
    assert len(result['initiatives_without_epics']) == 1
    assert 'TeamB' in result['initiatives_without_epics'][0]['missing_teams']
```

### 3. Data Flow Tests
```python
def test_action_items_show_correct_owner():
    """Test that action items display initiative owner, not action responsible team."""
    test_data = {
        'initiatives': [
            {
                'key': 'INIT-1',
                'summary': 'Test Initiative',
                'status': 'In Progress',
                'owner_team': 'TeamA',  # Real owner
                'teams_involved': ['TeamA', 'TeamB'],
                'contributing_teams': []  # TeamB needs to create epic
            }
        ]
    }

    result = analyze_workload(json_file, team_mappings, [], {}, quarter='26 Q2')
    actions = extract_workload_actions(result, team_managers, reverse_team_mappings)

    # For missing_epics actions
    epic_actions = [a for a in actions if a['action_type'] == 'missing_epics']
    assert len(epic_actions) == 1

    # Responsible team is TeamB (who needs to create epic)
    assert epic_actions[0]['responsible_team'] == 'TeamB'

    # But initiative owner is TeamA
    assert result['initiative_owner_teams']['INIT-1'] == 'TeamA'

    # Console output should show TeamA as owner, not TeamB
```

### 4. Sanitization Tests
```python
def test_no_hardcoded_company_data_in_output():
    """Test that generated output contains no hardcoded company references."""
    result = analyze_workload(json_file, {}, [], {}, quarter='26 Q2')
    actions = extract_workload_actions(result, {}, {})

    for action in actions:
        # URLs should use configured base, not hardcoded
        assert 'real-company-name' not in action['initiative_url']

def test_action_urls_use_configured_base():
    """Test that action item URLs use configuration, not hardcoded values."""
    with mock.patch('analyze_workload.get_jira_base_url', return_value='https://test.example.com'):
        result = analyze_workload(json_file, {}, [], {}, quarter='26 Q2')
        actions = extract_workload_actions(result, {}, {})

        for action in actions:
            assert action['initiative_url'].startswith('https://test.example.com/browse/')
```

### 5. Regression Test Suite
Create a regression test that validates all three fixes together:
```python
def test_workload_analysis_regression():
    """Regression test for hardcoded data, Discovery exclusion, and owner display."""
    # Tests all three fixes in one comprehensive scenario
    test_data = {
        'initiatives': [
            # Discovery initiative with missing epics (should be excluded)
            {'key': 'INIT-1', 'summary': '[Discovery] Test', 'status': 'In Progress',
             'owner_team': 'TeamA', 'teams_involved': ['TeamA', 'TeamB'],
             'contributing_teams': []},
            # Normal initiative with missing epics (should be flagged)
            {'key': 'INIT-2', 'summary': 'Regular initiative', 'status': 'In Progress',
             'owner_team': 'TeamA', 'teams_involved': ['TeamA', 'TeamC'],
             'contributing_teams': []},
        ]
    }

    with mock.patch('analyze_workload.get_jira_base_url', return_value='https://test.example.com'):
        result = analyze_workload(json_file, team_mappings, [], {}, quarter='26 Q2')
        actions = extract_workload_actions(result, team_managers, reverse_team_mappings)

        # 1. Discovery initiative excluded from epic checks
        epic_issues = [i for i in result['initiatives_without_epics'] if i['key'] == 'INIT-1']
        assert len(epic_issues) == 0, "Discovery initiatives should not be flagged for missing epics"

        # 2. URLs use configuration
        for action in actions:
            assert action['initiative_url'].startswith('https://test.example.com/browse/')

        # 3. Owner display is correct
        init2_actions = [a for a in actions if a['initiative_key'] == 'INIT-2']
        assert result['initiative_owner_teams']['INIT-2'] == 'TeamA'
        # Responsible team in action is TeamC (who needs to create epic)
        assert any(a['responsible_team'] == 'TeamC' for a in init2_actions)
```

## Related Documentation

### Core Documentation
- **README.md** - Main project documentation covering setup, usage, and features
- **ARCHITECTURE.md** - Architecture principles and design patterns
- **CLAUDE.md** - Project coding standards and workflow rules

### Implementation Plans
- **docs/plans/2026-04-03-001-feat-action-items-workload-analysis-plan.md** - Detailed implementation plan for adding action items and Slack notifications to analyze_workload.py
- **docs/plans/2026-04-03-002-compound-action-items-solution-plan.md** - Documentation plan capturing the debugging journey

### Related Features
- **docs/plans/2026-03-21-001-feat-initiative-status-validation-plan.md** - Planning validation tool design
- **docs/plans/2026-03-31-001-feat-initiative-sign-off-exceptions-plan.md** - Initiative exceptions configuration
- **docs/plans/2026-03-30-001-refactor-toolkit-consistency-reorganization-plan.md** - Toolkit consistency and shared module architecture

### Brainstorms & Design Documents
- **docs/brainstorms/2026-03-21-initiative-status-validation-brainstorm.md** - Original validation tool design decisions
- **docs/brainstorms/SLACK_INTEGRATION.md** - Comprehensive Slack integration design
- **docs/brainstorms/2026-03-31-initiative-sign-off-exceptions-brainstorm.md** - Manager-approved exceptions pattern

### Solution Documents
- **docs/solutions/code-quality/cli-error-handling-duplication.md** - DRY principle application for error handling

## Related Commits

From the action items implementation journey (2026-04-03):
- `a9f5b0f` - docs: add compound documentation plan for action items solution
- `91177eb` - docs: update plan with sanitization tasks for Phase 2
- `e53eac6` - fix: remove hardcoded company-specific data from analyze_workload.py
- `4b6adb1` - feat(analyze_workload): exclude Discovery initiatives from epic checks
- `10647f5` - fix(analyze_workload): display correct initiative owner in action items
- `c73bf5b` - fix(analyze_workload): resolve team key mismatch in Slack generation
- `2978138` - feat(analyze_workload): add action items and Slack notifications

## Files Modified

- **analyze_workload.py:76-89** - Added `is_discovery_initiative()` helper function
- **analyze_workload.py:20-47** - Added `get_jira_base_url()` for dynamic configuration
- **analyze_workload.py:341-350** - Applied Discovery check before epic validation
- **analyze_workload.py:603-610** - Updated URL construction to use configuration
- **analyze_workload.py:562-575** - Sanitized docstring examples
- **analyze_workload.py:1014-1017** - Fixed owner display logic

## Impact

- **Security**: Eliminated hardcoded company-specific data exposure
- **Accuracy**: Reduced false positive action items from 34 to 31 (console) and 25 to 22 (Slack)
- **Correctness**: Initiative owners now display correctly in all contexts
- **Maintainability**: Configuration is now externalized and easily changeable
