---
title: feat: Add Dust bulk message generation for manager notifications
type: feat
status: completed
date: 2026-03-27
origin: docs/brainstorms/2026-03-27-dust-bulk-messages-brainstorm.md
---

# Add Dust Bulk Message Generation for Manager Notifications

## Overview

Extend `validate_initiative_status.py` to generate copy-paste ready Dust bulk messages for engineering managers. Messages will contain team-specific action items extracted from validation results. This is **Phase 1** of a larger refactoring toward template-based output generation.

**Key Capabilities:**
- Extract action items into flat, richly-annotated data structure
- Generate Dust-compatible bulk messages using Jinja2 templates
- Group messages by manager with Slack member IDs
- Output to both console and timestamped file
- Maintain existing console/markdown outputs unchanged (Phase 2 migration)

## Problem Statement / Motivation

**Current Pain Point:**
Engineering managers need visibility into action items requiring their team's attention. Currently they must:
1. Read the full validation report (console or markdown)
2. Manually identify their team's action items
3. Context-switch between multiple initiatives

**Business Value:**
- **Reduced friction:** Managers receive personalized, actionable DMs via Dust
- **Faster response:** Direct notification accelerates epic creation and RAG status updates
- **Better tracking:** Copy-paste format enables audit trail of what was sent when

**Technical Motivation:**
- Existing console/markdown outputs duplicate ~60% of formatting logic
- Adding a third output format (Dust) would triple the duplication
- Introducing extraction layer now enables future template migration (Phase 2)

## Proposed Solution

### Architecture Overview

```
validate_initiative_status.py
  ↓
Validation Logic (existing)
  ↓
ValidationResult (existing)
  ↓
extract_manager_actions() (NEW)
  → Returns List[Dict] with flat action items
  ↓
  ├→ print_validation_report() (existing - unchanged)
  ├→ generate_markdown_report() (existing - unchanged)
  └→ generate_dust_messages() (NEW)
       ↓
     templates/dust.j2 (NEW)
       ↓
     Console output + File (extracts/dust_messages_YYYY-MM-DD_HHMMSS.txt)
```

### Data Flow

1. **Validation** runs as before → produces `ValidationResult`
2. **Extraction** (new) → flattens `ValidationResult` into action items with metadata
3. **Rendering** (new for Dust, existing for console/markdown) → formats data for output
4. **Delivery** → Print to console + save to file

### Key Design Decisions (from brainstorm)

All design decisions are documented in the [origin brainstorm](../brainstorms/2026-03-27-dust-bulk-messages-brainstorm.md):

- **Data structure:** Flat list with rich metadata (enables flexible grouping per output format)
- **Configuration:** Extend `team_managers` to include `slack_id` alongside `notion_handle`
- **Templates:** Jinja2 templates in `templates/` directory
- **Message format:** Dust-compatible with emoji, Jira links, grouped by manager → initiative
- **Invocation:** Add `--dust` CLI flag
- **Output:** Console print + timestamped file in `extracts/` directory
- **Action types:** All four types (missing dependencies, missing RAG, missing assignee, ready to PLANNED)
- **Priority:** Implicit ordering (blocking issues before informational)
- **Empty lists:** Skip managers with no action items

## Technical Approach

### Phase 1: Extraction Layer + Dust Output (This Plan)

#### 1. Add Jinja2 Dependency

**Files:**
- Update project dependencies to include Jinja2

**Implementation:**
- Add `jinja2` to requirements or imports
- Document in README if virtual environment setup needed

**Testing:**
- Verify `import jinja2` works in test environment

---

#### 2. Update Configuration Structure

**File:** `team_mappings.yaml`

**Current Structure:**
```yaml
team_managers:
  "CBPPE": "@Ariel Reanho "
  "CONSOLE": "@Karina Rangel"
```

**New Structure:**
```yaml
team_managers:
  "CBPPE":
    notion_handle: "@Ariel Reanho "
    slack_id: "U01F3QUHP0B"
  "CONSOLE":
    notion_handle: "@Karina Rangel"
    slack_id: "U02ABC456"
  "CBNK":
    notion_handle: "@Joel Oughton"
    slack_id: "U03GHI789"
  "DNTT":
    notion_handle: "@Michael Steele"
    slack_id: "U04JKL012"
  "MAPS":
    notion_handle: "@Kevin Plattret"
    slack_id: "U05MNO345"
  "PAYINS":
    notion_handle: "@Karina Rangel"
    slack_id: "U02ABC456"
  "PX":
    notion_handle: "@Prabodh Kakodkar"
    slack_id: "U06PQR678"
  "RSK":
    notion_handle: "@Kevin Plattret"
    slack_id: "U05MNO345"
  "DOCS":
    notion_handle: "@Federico Casali"
    slack_id: "U07STU901"
  "Analytics":
    notion_handle: "@Joe Al-Kadhimi"
    slack_id: "U08VWX234"
```

**Backward Compatibility Strategy:**
- Update `_load_team_managers()` helper to handle both formats:
  - If value is string → return as `notion_handle`, `slack_id` = None
  - If value is dict → return both fields
- Existing console/markdown code continues working with `notion_handle`
- New Dust code uses `slack_id`

**Implementation:**
```python
def _load_team_managers() -> Dict[str, Dict[str, Optional[str]]]:
    """Load team managers with Notion handles and Slack IDs.

    Returns:
        Dict mapping project keys to manager info:
        {
            "CBPPE": {
                "notion_handle": "@Ariel Reanho ",
                "slack_id": "U01F3QUHP0B"
            }
        }

        Handles legacy string format for backward compatibility.
    """
    mappings_file = Path(__file__).parent / 'team_mappings.yaml'
    if not mappings_file.exists():
        return {}

    try:
        with open(mappings_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            raw_managers = data.get('team_managers', {})

            # Normalize to dict format
            normalized = {}
            for project_key, value in raw_managers.items():
                if isinstance(value, str):
                    # Legacy format: just Notion handle
                    normalized[project_key] = {
                        'notion_handle': value,
                        'slack_id': None
                    }
                elif isinstance(value, dict):
                    # New format: structured data
                    normalized[project_key] = {
                        'notion_handle': value.get('notion_handle', ''),
                        'slack_id': value.get('slack_id')
                    }

            return normalized
    except Exception:
        return {}
```

**Update Existing Callers:**
All existing code that calls `_load_team_managers()` needs updating to access `['notion_handle']`:

**Locations to update:**
- `validate_initiative_status.py:730-750` (console missing dependencies)
- `validate_initiative_status.py:764-784` (console missing RAG)
- `validate_initiative_status.py:796-816` (console missing assignee)
- `validate_initiative_status.py:1088-1095` (markdown missing assignee)
- `validate_initiative_status.py:1104-1111` (markdown missing RAG)
- `validate_initiative_status.py:1128-1146` (markdown missing dependencies)
- `validate_initiative_status.py:1321-1374` (markdown planned regressions missing dependencies)
- `validate_initiative_status.py:1378-1388` (markdown planned regressions missing RAG)

**Pattern to follow:**
```python
# OLD
team_managers = _load_team_managers()
manager_tag = team_managers.get(project_key, '')

# NEW
team_managers = _load_team_managers()
manager_info = team_managers.get(project_key, {})
manager_tag = manager_info.get('notion_handle', '')
```

**Fail-fast validation:**
Add startup check to ensure all teams have Slack IDs configured when using `--dust`:

```python
def _validate_dust_config(team_managers: Dict[str, Dict]) -> None:
    """Validate all teams have Slack IDs for Dust messaging.

    Raises:
        ValueError: If any team is missing slack_id
    """
    missing = [
        key for key, info in team_managers.items()
        if not info.get('slack_id')
    ]
    if missing:
        raise ValueError(
            f"Missing Slack IDs for teams: {', '.join(missing)}\n"
            f"Update team_mappings.yaml with slack_id for each team"
        )
```

**Testing:**
- Add test for backward compatibility with string format
- Add test for new dict format
- Add test for validation failure with missing Slack IDs
- Add test for partial config (some teams with IDs, some without)

---

#### 3. Create Extraction Function

**File:** `validate_initiative_status.py`

**New Function:**
```python
def extract_manager_actions(result: ValidationResult) -> List[Dict[str, Any]]:
    """Extract action items from ValidationResult into flat, annotated list.

    This function flattens the hierarchical ValidationResult into a list of
    individual action items, each annotated with all metadata needed for
    any output format (console, markdown, Dust, etc.).

    Args:
        result: Validation result containing categorized initiatives

    Returns:
        List of action item dictionaries with structure:
        {
            'initiative_key': 'INIT-1234',
            'initiative_title': 'Project Alpha',
            'initiative_status': 'Planned',
            'initiative_url': 'https://truelayer.atlassian.net/browse/INIT-1234',
            'section': 'planned_regressions',  # which report section
            'action_type': 'missing_dependencies',
            'priority': 1,  # lower = higher priority
            'responsible_team': 'RSK',
            'responsible_team_key': 'RSK',
            'responsible_manager_name': 'Kevin Plattret',
            'responsible_manager_notion': '@Kevin Plattret',
            'responsible_manager_slack_id': 'U05MNO345',
            'description': 'Create epic',
            'epic_key': None,  # or epic key if action is about specific epic
            'epic_title': None,
            'epic_rag': None
        }

    Action types included:
    - 'missing_dependencies': Team needs to create epic
    - 'missing_rag': Team needs to set RAG status on epic
    - 'missing_assignee': Initiative needs assignee
    - 'ready_to_planned': Initiative ready to move to PLANNED status

    Priority ordering (1=highest):
    1. missing_assignee (blocks planning)
    2. missing_dependencies (blocks execution)
    3. missing_rag (blocks visibility)
    4. ready_to_planned (informational)
    """
    actions = []
    team_mappings = _load_team_mappings()
    team_managers = _load_team_managers()

    # Priority mapping
    PRIORITY = {
        'missing_assignee': 1,
        'missing_dependencies': 2,
        'missing_rag': 3,
        'ready_to_planned': 4
    }

    # Helper to build base initiative context
    def _base_context(initiative: Dict, section: str) -> Dict:
        return {
            'initiative_key': initiative['key'],
            'initiative_title': initiative['summary'],
            'initiative_status': initiative.get('status', 'Unknown'),
            'initiative_url': f"https://truelayer.atlassian.net/browse/{initiative['key']}",
            'section': section
        }

    # Helper to add manager info
    def _add_manager_info(action: Dict, team_key: str, team_display: str) -> Dict:
        manager_info = team_managers.get(team_key, {})
        action['responsible_team'] = team_display
        action['responsible_team_key'] = team_key
        action['responsible_manager_name'] = manager_info.get('notion_handle', '').strip('@').strip()
        action['responsible_manager_notion'] = manager_info.get('notion_handle', '')
        action['responsible_manager_slack_id'] = manager_info.get('slack_id')
        return action

    # Process each section of ValidationResult

    # Section 1: dependency_mapping (Proposed initiatives with issues)
    for initiative in result.dependency_mapping:
        base = _base_context(initiative, 'dependency_mapping')
        owner_team = initiative.get('owner_team')

        for issue in initiative.get('issues', []):
            if issue['type'] == 'missing_assignee':
                # Owner team responsible for assignee
                if owner_team:
                    owner_key = team_mappings.get(owner_team, owner_team)
                    action = {
                        **base,
                        'action_type': 'missing_assignee',
                        'priority': PRIORITY['missing_assignee'],
                        'description': 'Set assignee',
                        'epic_key': None,
                        'epic_title': None,
                        'epic_rag': None
                    }
                    _add_manager_info(action, owner_key, owner_team)
                    actions.append(action)

            elif issue['type'] == 'epic_count_mismatch':
                # Missing dependencies - teams need to create epics
                teams_involved = issue.get('teams_involved', [])
                teams_with_epics = set(issue.get('teams_with_epics', []))

                for team_display in teams_involved:
                    # Skip owner team
                    if owner_team and team_display == owner_team:
                        continue

                    team_key = team_mappings.get(team_display, team_display)
                    if team_key not in teams_with_epics:
                        action = {
                            **base,
                            'action_type': 'missing_dependencies',
                            'priority': PRIORITY['missing_dependencies'],
                            'description': 'Create epic',
                            'epic_key': None,
                            'epic_title': None,
                            'epic_rag': None
                        }
                        _add_manager_info(action, team_key, team_display)
                        actions.append(action)

            elif issue['type'] == 'missing_rag':
                # Missing RAG status - team needs to set it
                for epic_info in issue.get('epics', []):
                    epic_key = epic_info.get('key', '')
                    team_key = epic_key.split('-')[0] if '-' in epic_key else None

                    if team_key:
                        # Find team display name
                        team_display = next(
                            (k for k, v in team_mappings.items() if v == team_key),
                            team_key
                        )

                        action = {
                            **base,
                            'action_type': 'missing_rag',
                            'priority': PRIORITY['missing_rag'],
                            'description': 'Set RAG status',
                            'epic_key': epic_info.get('key'),
                            'epic_title': epic_info.get('summary'),
                            'epic_rag': None
                        }
                        _add_manager_info(action, team_key, team_display)
                        actions.append(action)

    # Section 2: ready_to_plan (Proposed initiatives ready to move)
    for initiative in result.ready_to_plan:
        base = _base_context(initiative, 'ready_to_plan')
        owner_team = initiative.get('owner_team')

        if owner_team:
            owner_key = team_mappings.get(owner_team, owner_team)
            action = {
                **base,
                'action_type': 'ready_to_planned',
                'priority': PRIORITY['ready_to_planned'],
                'description': 'All criteria met - ready to move to PLANNED',
                'epic_key': None,
                'epic_title': None,
                'epic_rag': None
            }
            _add_manager_info(action, owner_key, owner_team)
            actions.append(action)

    # Section 3: planned_regressions (Planned/In Progress with issues)
    for initiative in result.planned_regressions:
        base = _base_context(initiative, 'planned_regressions')
        owner_team = initiative.get('owner_team')

        for issue in initiative.get('issues', []):
            if issue['type'] == 'missing_assignee':
                if owner_team:
                    owner_key = team_mappings.get(owner_team, owner_team)
                    action = {
                        **base,
                        'action_type': 'missing_assignee',
                        'priority': PRIORITY['missing_assignee'],
                        'description': 'Set assignee',
                        'epic_key': None,
                        'epic_title': None,
                        'epic_rag': None
                    }
                    _add_manager_info(action, owner_key, owner_team)
                    actions.append(action)

            elif issue['type'] == 'epic_count_mismatch':
                teams_involved = issue.get('teams_involved', [])
                teams_with_epics = set(issue.get('teams_with_epics', []))

                for team_display in teams_involved:
                    if owner_team and team_display == owner_team:
                        continue

                    team_key = team_mappings.get(team_display, team_display)
                    if team_key not in teams_with_epics:
                        action = {
                            **base,
                            'action_type': 'missing_dependencies',
                            'priority': PRIORITY['missing_dependencies'],
                            'description': 'Create epic',
                            'epic_key': None,
                            'epic_title': None,
                            'epic_rag': None
                        }
                        _add_manager_info(action, team_key, team_display)
                        actions.append(action)

            elif issue['type'] == 'missing_rag':
                for epic_info in issue.get('epics', []):
                    epic_key = epic_info.get('key', '')
                    team_key = epic_key.split('-')[0] if '-' in epic_key else None

                    if team_key:
                        team_display = next(
                            (k for k, v in team_mappings.items() if v == team_key),
                            team_key
                        )

                        action = {
                            **base,
                            'action_type': 'missing_rag',
                            'priority': PRIORITY['missing_rag'],
                            'description': 'Set RAG status',
                            'epic_key': epic_info.get('key'),
                            'epic_title': epic_info.get('summary'),
                            'epic_rag': None
                        }
                        _add_manager_info(action, team_key, team_display)
                        actions.append(action)

    return actions
```

**Testing:**
- Test extraction from each ValidationResult section
- Test action type identification and priority assignment
- Test manager info lookup and annotation
- Test handling of missing owner_team
- Test handling of unmapped teams
- Test empty ValidationResult
- Test deduplication if same action appears multiple times

**Test file:** `tests/test_validate_initiative_status.py`

**New tests to add:**
```python
def test_extract_manager_actions_missing_dependencies():
    """Test extraction of missing dependencies actions."""
    # Setup ValidationResult with epic_count_mismatch issue
    # Assert action_type, priority, responsible_team populated

def test_extract_manager_actions_missing_rag():
    """Test extraction of missing RAG actions."""
    # Setup ValidationResult with missing_rag issue
    # Assert epic_key, epic_title included

def test_extract_manager_actions_missing_assignee():
    """Test extraction of missing assignee actions."""
    # Setup ValidationResult with missing_assignee issue
    # Assert owner_team responsible

def test_extract_manager_actions_ready_to_planned():
    """Test extraction of ready to PLANNED actions."""
    # Setup ValidationResult with ready_to_plan initiatives
    # Assert correct action_type and priority

def test_extract_manager_actions_priority_ordering():
    """Test action priority values are correct."""
    # Create ValidationResult with all action types
    # Extract and verify priority field matches expected ordering

def test_extract_manager_actions_slack_id_lookup():
    """Test Slack ID lookup from team_managers."""
    # Mock team_managers with slack_id
    # Verify responsible_manager_slack_id populated

def test_extract_manager_actions_handles_missing_manager():
    """Test graceful handling when manager not in config."""
    # Team with no entry in team_managers
    # Should still create action with None slack_id

def test_extract_manager_actions_empty_result():
    """Test extraction from empty ValidationResult."""
    # All lists empty
    # Should return empty list
```

---

#### 4. Create Dust Template

**File:** `templates/dust.j2`

**Template Content:**
```jinja2
{# Dust bulk message template for engineering manager notifications #}
{# Input: messages (list of dicts with manager_name, slack_id, actions) #}
{% for message in messages -%}
Recipient: {{ message.slack_id }}
Message: Hi! Here are your action items from the latest initiative validation:

You have {{ message.total_actions }} action item{% if message.total_actions != 1 %}s{% endif %} across {{ message.total_initiatives }} initiative{% if message.total_initiatives != 1 %}s{% endif %}.

{% for initiative in message.initiatives -%}
<{{ initiative.url }}|{{ initiative.key }}>
{% for action in initiative.actions -%}
{% if action.action_type == 'missing_dependencies' -%}
:warning: Missing dependencies - {{ action.description }}
{% elif action.action_type == 'missing_rag' -%}
:warning: Missing RAG status - {{ action.description }}{% if action.epic_key %} on <https://truelayer.atlassian.net/browse/{{ action.epic_key }}|{{ action.epic_key }}>{% endif %}
{% elif action.action_type == 'missing_assignee' -%}
:raising_hand: Missing assignee - {{ action.description }}
{% elif action.action_type == 'ready_to_planned' -%}
:rocket: {{ action.description }}
{% endif %}
{% endfor %}

{% endfor -%}
---

{% endfor -%}
```

**Template Variables:**

Input structure to template:
```python
{
    'messages': [
        {
            'manager_name': 'Kevin Plattret',
            'slack_id': 'U05MNO345',
            'total_actions': 5,
            'total_initiatives': 3,
            'initiatives': [
                {
                    'key': 'INIT-1234',
                    'title': 'Project Alpha',
                    'url': 'https://truelayer.atlassian.net/browse/INIT-1234',
                    'actions': [
                        {
                            'action_type': 'missing_dependencies',
                            'description': 'Create epic',
                            'epic_key': None
                        }
                    ]
                }
            ]
        }
    ]
}
```

---

#### 5. Create Dust Generation Function

**File:** `validate_initiative_status.py`

**New Function:**
```python
def generate_dust_messages(result: ValidationResult, output_dir: Path) -> None:
    """Generate Dust-compatible bulk messages for engineering managers.

    Extracts action items from validation result, groups by manager,
    and renders using Jinja2 template. Outputs to console and file.

    Args:
        result: Validation result containing initiatives and issues
        output_dir: Directory to save output file (typically extracts/)

    Raises:
        ValueError: If team_managers config is missing Slack IDs
    """
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    from collections import defaultdict

    # Validate configuration
    team_managers = _load_team_managers()
    _validate_dust_config(team_managers)

    # Extract actions
    actions = extract_manager_actions(result)

    # Group by manager Slack ID
    manager_groups = defaultdict(lambda: {
        'manager_name': None,
        'slack_id': None,
        'initiatives': defaultdict(lambda: {
            'key': None,
            'title': None,
            'url': None,
            'actions': []
        })
    })

    for action in actions:
        slack_id = action['responsible_manager_slack_id']
        if not slack_id:
            # Skip actions for managers without Slack ID
            continue

        manager_name = action['responsible_manager_name']
        initiative_key = action['initiative_key']

        # Initialize manager entry
        if manager_groups[slack_id]['slack_id'] is None:
            manager_groups[slack_id]['manager_name'] = manager_name
            manager_groups[slack_id]['slack_id'] = slack_id

        # Initialize initiative entry
        if manager_groups[slack_id]['initiatives'][initiative_key]['key'] is None:
            manager_groups[slack_id]['initiatives'][initiative_key]['key'] = initiative_key
            manager_groups[slack_id]['initiatives'][initiative_key]['title'] = action['initiative_title']
            manager_groups[slack_id]['initiatives'][initiative_key]['url'] = action['initiative_url']

        # Add action to initiative
        manager_groups[slack_id]['initiatives'][initiative_key]['actions'].append({
            'action_type': action['action_type'],
            'description': action['description'],
            'epic_key': action.get('epic_key'),
            'epic_title': action.get('epic_title'),
            'priority': action['priority']
        })

    # Convert to template-friendly structure
    messages = []
    for slack_id, manager_data in manager_groups.items():
        initiatives = []
        total_actions = 0

        for initiative_key, initiative_data in manager_data['initiatives'].items():
            # Sort actions by priority within initiative
            sorted_actions = sorted(
                initiative_data['actions'],
                key=lambda a: a['priority']
            )
            total_actions += len(sorted_actions)

            initiatives.append({
                'key': initiative_data['key'],
                'title': initiative_data['title'],
                'url': initiative_data['url'],
                'actions': sorted_actions
            })

        # Sort initiatives by key
        initiatives.sort(key=lambda i: i['key'])

        messages.append({
            'manager_name': manager_data['manager_name'],
            'slack_id': slack_id,
            'total_actions': total_actions,
            'total_initiatives': len(initiatives),
            'initiatives': initiatives
        })

    # Sort messages by manager name for consistent output
    messages.sort(key=lambda m: m['manager_name'])

    # Setup Jinja2 environment
    template_dir = Path(__file__).parent / 'templates'
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(['html', 'xml']),
        trim_blocks=True,
        lstrip_blocks=True
    )

    # Render template
    template = env.get_template('dust.j2')
    output = template.render(messages=messages)

    # Print to console
    print("\n" + "="*60)
    print("DUST BULK MESSAGES")
    print("="*60)
    print("\nCopy the text below and paste into Dust chatbot:\n")
    print(output)
    print("="*60)

    # Save to file
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    output_file = output_dir / f'dust_messages_{timestamp}.txt'

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(output)

    print(f"\nDust messages saved to: {output_file}")
    print(f"Total managers: {len(messages)}")
    print(f"Total action items: {sum(m['total_actions'] for m in messages)}")
```

**Testing:**
- Test grouping by Slack ID
- Test initiative grouping within manager
- Test action sorting by priority
- Test Jinja2 template rendering
- Test file output with timestamp
- Test console output format
- Test handling of managers without Slack IDs (skip)
- Test empty actions list (no file created)

**Test file:** `tests/test_validate_initiative_status.py`

**New tests to add:**
```python
def test_generate_dust_messages_grouping(tmp_path):
    """Test Dust messages group actions by manager correctly."""
    # Create ValidationResult with actions for multiple managers
    # Generate messages
    # Assert each manager appears once
    # Assert all their actions are grouped together

def test_generate_dust_messages_priority_ordering(tmp_path):
    """Test actions within initiative are sorted by priority."""
    # Create ValidationResult with mixed priority actions
    # Generate messages
    # Assert actions appear in priority order (missing_assignee first)

def test_generate_dust_messages_file_output(tmp_path):
    """Test Dust messages are saved to timestamped file."""
    # Generate messages
    # Assert file exists in output_dir
    # Assert filename matches pattern dust_messages_YYYY-MM-DD_HHMMSS.txt

def test_generate_dust_messages_console_output(tmp_path, capsys):
    """Test Dust messages are printed to console."""
    # Generate messages
    # Capture console output
    # Assert contains Recipient: lines
    # Assert contains Message: content

def test_generate_dust_messages_skips_missing_slack_id(tmp_path):
    """Test managers without Slack ID are skipped."""
    # Create action with slack_id = None
    # Generate messages
    # Assert that manager not in output

def test_generate_dust_messages_validates_config(tmp_path):
    """Test validation error when Slack IDs missing."""
    # Mock team_managers with missing slack_id
    # Assert ValueError raised with clear message

def test_generate_dust_messages_emoji_formatting(tmp_path):
    """Test emoji are formatted correctly for Dust."""
    # Generate messages with different action types
    # Assert :warning:, :raising_hand:, :rocket: appear correctly

def test_generate_dust_messages_jira_links(tmp_path):
    """Test Jira links use Dust format with angle brackets."""
    # Generate messages
    # Assert links match pattern <https://url|text>
```

---

#### 6. Add CLI Flag

**File:** `validate_initiative_status.py`

**Update argument parser (around line 1479):**

```python
parser.add_argument(
    '--dust',
    action='store_true',
    help='Generate Dust bulk messages for manager notifications'
)
```

**Update main execution logic (around line 1520):**

```python
# After validation
result = validate_initiative_status(json_file)

# Console output (always)
print_validation_report(result, args.verbose)

# Markdown output (if requested)
if args.markdown:
    # existing markdown generation...
    generate_markdown_report(result, output_file, args.verbose)

# Dust output (if requested) - NEW
if args.dust:
    output_dir = json_file.parent
    generate_dust_messages(result, output_dir)
```

**Testing:**
- Test `--dust` flag is recognized
- Test Dust generation triggered when flag present
- Test Dust generation skipped when flag absent
- Test combination of `--verbose --markdown --dust`

**Test file:** `tests/test_validate_initiative_status.py`

```python
def test_cli_dust_flag_triggers_generation(tmp_path, monkeypatch, capsys):
    """Test --dust flag triggers Dust message generation."""
    # Create test JSON file
    # Mock validate_initiative_status
    # Run with --dust flag
    # Assert generate_dust_messages was called

def test_cli_dust_and_markdown_together(tmp_path):
    """Test --dust and --markdown can be used together."""
    # Create test JSON file
    # Run with both flags
    # Assert both outputs created

def test_cli_dust_without_verbose(tmp_path):
    """Test --dust works independently of --verbose."""
    # Run with just --dust
    # Assert Dust messages generated
```

---

#### 7. Update Existing Manager Lookups

**Files to update:** `validate_initiative_status.py`

**Locations (identified in research):**
- Lines 730-750: Console missing dependencies
- Lines 764-784: Console missing RAG
- Lines 796-816: Console missing assignee
- Lines 1088-1095: Markdown missing assignee
- Lines 1104-1111: Markdown missing RAG
- Lines 1128-1146: Markdown missing dependencies
- Lines 1321-1374: Markdown planned regressions missing dependencies
- Lines 1378-1388: Markdown planned regressions missing RAG

**Update pattern:**

```python
# OLD
team_managers = _load_team_managers()
manager_tag = team_managers.get(project_key, '')
manager_suffix = f" {manager_tag}" if manager_tag else ""

# NEW
team_managers = _load_team_managers()
manager_info = team_managers.get(project_key, {})
manager_tag = manager_info.get('notion_handle', '')
manager_suffix = f" {manager_tag}" if manager_tag else ""
```

**Testing:**
Run existing test suite to ensure no regressions:
```bash
pytest tests/test_validate_initiative_status.py -v
```

All 53 existing tests should still pass after these changes.

---

#### 8. Create Templates Directory

**Structure:**
```
jira-dependencies-tracking/
├── templates/
│   └── dust.j2
├── validate_initiative_status.py
├── team_mappings.yaml
└── tests/
    └── test_validate_initiative_status.py
```

**Implementation:**
```bash
mkdir -p templates/
```

---

#### 9. Documentation Updates

**File:** `README.md`

**Add section:** "Dust Manager Notifications"

```markdown
### Dust Manager Notifications

Generate copy-paste ready messages for sending bulk Slack DMs via Dust:

```bash
# Generate Dust messages
python validate_initiative_status.py --dust

# Output: Console preview + file in extracts/dust_messages_YYYY-MM-DD_HHMMSS.txt
```

**Format:**
- Grouped by engineering manager
- Each message includes Slack member ID (Recipient:)
- Action items organized by initiative
- Ready to paste into Dust chatbot

**Configuration:**
Update `team_mappings.yaml` with Slack member IDs:

```yaml
team_managers:
  "CBPPE":
    notion_handle: "@Ariel Reanho "
    slack_id: "U01F3QUHP0B"
```

**File:** `CLAUDE.md` (optional)

Add note about template-based outputs for future developers:
```markdown
### Output Generation Pattern

Dust message generation uses Jinja2 templates (`templates/dust.j2`).
Future: Migrate console/markdown outputs to templates (Phase 2).
```

---

### Phase 2: Template Migration (Future Work)

**Not included in this plan - deferred to separate effort:**

1. Create `templates/console.j2` - Port console output format
2. Create `templates/markdown.j2` - Port markdown format
3. Refactor `print_validation_report()` to use extraction + template
4. Refactor `generate_markdown_report()` to use extraction + template
5. Remove duplicated formatting code
6. Verify byte-for-byte output compatibility
7. Update tests for refactored functions

**Rationale for deferring:**
- Phase 1 proves the extraction + template pattern
- Existing console/markdown outputs are working and tested
- Risk of regression is high if done together
- Incremental approach validates architecture before full migration

## System-Wide Impact

### Interaction Graph

**Dust Generation Flow:**
1. User runs script with `--dust` flag
2. `main()` → `validate_initiative_status()` → produces `ValidationResult`
3. `main()` → `generate_dust_messages()` → calls:
   - `_load_team_managers()` → reads YAML config
   - `_validate_dust_config()` → checks Slack IDs present
   - `extract_manager_actions()` → flattens ValidationResult, calls:
     - `_load_team_mappings()` → reads YAML config
     - `_load_team_managers()` → reads YAML config (again)
   - Jinja2 `Environment.get_template()` → reads `templates/dust.j2`
   - Jinja2 `template.render()` → generates message text
   - `print()` → console output
   - File write → saves to `extracts/`

**Side Effects:**
- Creates timestamped file in `extracts/` directory
- Prints to stdout (console)
- No database writes, no API calls, no network operations

**Existing Code Dependencies:**
- `_load_team_managers()` - must be backward compatible
- `_load_team_mappings()` - unchanged
- `ValidationResult` class - unchanged (read-only)

### Error & Failure Propagation

**Config Errors (Fail Fast):**
```
User runs --dust
  ↓
_validate_dust_config() raises ValueError
  ↓
Script exits with error message: "Missing Slack IDs for teams: RSK, CONSOLE"
  ↓
User updates team_mappings.yaml
  ↓
User reruns script successfully
```

**Template Errors (Fail Fast):**
```
Jinja2 cannot find templates/dust.j2
  ↓
jinja2.exceptions.TemplateNotFound raised
  ↓
Script exits with error: "Template 'dust.j2' not found"
  ↓
User creates templates/ directory or fixes path
```

**Data Errors (Degrade Gracefully):**
```
Manager missing Slack ID in config
  ↓
extract_manager_actions() returns action with slack_id=None
  ↓
generate_dust_messages() skips that manager in grouping
  ↓
Warning printed: "Skipped N actions (managers without Slack IDs)"
  ↓
Dust messages generated for remaining managers
```

**Runtime Errors:**
- YAML parsing errors → fail fast (config error)
- File write permission errors → fail fast (system error)
- Empty ValidationResult → degrades gracefully (no messages, empty file)

### State Lifecycle Risks

**No persistent state:** This is a read-only reporting tool.

**File State:**
- Each run creates new timestamped file
- No file overwrites or updates
- No file locking needed (single-threaded)
- Old files remain until manually deleted

**Memory State:**
- ValidationResult built in memory
- Actions list built in memory
- Template rendering in memory
- Garbage collected after script exit

**No database state:** No transactions, no rollbacks needed

### API Surface Parity

**New Public Functions:**
- `extract_manager_actions(result: ValidationResult) -> List[Dict]`
- `generate_dust_messages(result: ValidationResult, output_dir: Path) -> None`

**Modified Functions:**
- `_load_team_managers()` - Return type changed from `Dict[str, str]` to `Dict[str, Dict]`
  - **Impact:** All callers must update to access `['notion_handle']`
  - **Locations:** 8 call sites in console/markdown generation

**Helper Functions Added:**
- `_validate_dust_config(team_managers: Dict) -> None`

**CLI Interface:**
- New flag: `--dust` (boolean, optional)
- Existing flags unchanged

**No external APIs:** No REST endpoints, no SDK, no public library

### Integration Test Scenarios

**Cross-Layer Scenario 1: End-to-End Dust Generation**
```python
def test_dust_generation_end_to_end(tmp_path):
    """Test complete flow from JSON file to Dust messages."""
    # Create JSON file with initiatives
    # Run validate_initiative_status with --dust
    # Assert:
    #   - ValidationResult created correctly
    #   - Actions extracted
    #   - Dust messages generated
    #   - File created with correct content
    #   - Console output matches file content
```

**Cross-Layer Scenario 2: Config Loading → Validation → Generation**
```python
def test_config_impacts_dust_output(tmp_path):
    """Test configuration changes flow through to Dust messages."""
    # Create custom team_mappings.yaml with specific Slack IDs
    # Create JSON with initiatives
    # Generate Dust messages
    # Assert Slack IDs from config appear in output
```

**Cross-Layer Scenario 3: Missing Config Handling**
```python
def test_missing_slack_ids_prevents_dust_generation(tmp_path):
    """Test validation catches missing Slack IDs early."""
    # Create team_mappings.yaml with missing slack_id
    # Try to generate Dust messages
    # Assert ValueError raised before any file writes
```

**Cross-Layer Scenario 4: Multiple Output Formats**
```python
def test_markdown_and_dust_together(tmp_path):
    """Test --markdown and --dust flags work together."""
    # Create JSON file
    # Run with both flags
    # Assert:
    #   - Markdown file created
    #   - Dust file created
    #   - Console shows both outputs
    #   - No interference between formats
```

**Cross-Layer Scenario 5: Backward Compatibility**
```python
def test_old_config_format_still_works_for_console(tmp_path):
    """Test legacy string format team_managers works for console output."""
    # Create team_mappings.yaml with old string format
    # Run without --dust flag
    # Assert:
    #   - Console output works normally
    #   - Manager tags appear correctly
    #   - No errors about missing slack_id
```

## Acceptance Criteria

### Functional Requirements

- [ ] `--dust` CLI flag triggers Dust message generation
- [ ] Dust messages grouped by manager (Slack ID)
- [ ] Within each manager: actions grouped by initiative
- [ ] Within each initiative: actions sorted by priority
- [ ] All 4 action types included (missing deps, missing RAG, missing assignee, ready to PLANNED)
- [ ] Emoji formatted correctly (`:warning:`, `:raising_hand:`, `:rocket:`)
- [ ] Jira links use Dust format (`<https://url|text>`)
- [ ] Output printed to console
- [ ] Output saved to timestamped file in `extracts/`
- [ ] Managers without Slack IDs are skipped (no errors)
- [ ] Empty action lists produce no output file
- [ ] Configuration validation fails fast if Slack IDs missing

### Non-Functional Requirements

- [ ] Extraction function completes in <1 second for typical dataset (~100 initiatives)
- [ ] Template rendering completes in <100ms
- [ ] Backward compatible: existing console/markdown outputs unchanged
- [ ] Existing 53 tests continue passing
- [ ] Code follows CLAUDE.md conventions (functional style, short functions)

### Quality Gates

- [ ] All new functions have tests (unit + integration)
- [ ] Test coverage for extraction logic ≥90%
- [ ] Test coverage for Dust generation ≥90%
- [ ] All tests passing: `pytest tests/test_validate_initiative_status.py -v`
- [ ] No regression in existing outputs (visual inspection)
- [ ] README updated with Dust usage instructions
- [ ] Code reviewed (self-review or peer review)

## Testing Strategy

### Unit Tests (New)

**Test File:** `tests/test_validate_initiative_status.py`

**Categories:**

1. **Config Loading Tests:**
   - `test_load_team_managers_dict_format()` - New dict format
   - `test_load_team_managers_string_format()` - Legacy compatibility
   - `test_load_team_managers_mixed_formats()` - Some dict, some string
   - `test_validate_dust_config_all_ids_present()` - Validation passes
   - `test_validate_dust_config_missing_ids()` - Validation fails with clear error

2. **Extraction Tests:**
   - `test_extract_manager_actions_missing_dependencies()`
   - `test_extract_manager_actions_missing_rag()`
   - `test_extract_manager_actions_missing_assignee()`
   - `test_extract_manager_actions_ready_to_planned()`
   - `test_extract_manager_actions_priority_ordering()`
   - `test_extract_manager_actions_slack_id_lookup()`
   - `test_extract_manager_actions_handles_missing_manager()`
   - `test_extract_manager_actions_empty_result()`

3. **Generation Tests:**
   - `test_generate_dust_messages_grouping()`
   - `test_generate_dust_messages_priority_ordering()`
   - `test_generate_dust_messages_file_output()`
   - `test_generate_dust_messages_console_output()`
   - `test_generate_dust_messages_skips_missing_slack_id()`
   - `test_generate_dust_messages_validates_config()`
   - `test_generate_dust_messages_emoji_formatting()`
   - `test_generate_dust_messages_jira_links()`

4. **CLI Tests:**
   - `test_cli_dust_flag_triggers_generation()`
   - `test_cli_dust_and_markdown_together()`
   - `test_cli_dust_without_verbose()`

### Integration Tests (New)

5. **End-to-End Tests:**
   - `test_dust_generation_end_to_end()` - Full flow
   - `test_config_impacts_dust_output()` - Config → output
   - `test_missing_slack_ids_prevents_dust_generation()` - Early validation
   - `test_markdown_and_dust_together()` - Multiple outputs
   - `test_old_config_format_still_works_for_console()` - Backward compat

### Regression Tests (Existing)

**Verify no changes to:**
- Console output format and content
- Markdown output format and content
- ValidationResult structure
- Manager tag lookups in console/markdown

**Approach:**
- Run full existing test suite
- Visual spot-check console output with/without `--dust`
- Compare markdown files before/after changes

### Mock Data

**Mock Slack IDs:**
```python
MOCK_TEAM_MANAGERS = {
    "CBPPE": {
        "notion_handle": "@Ariel Reanho ",
        "slack_id": "U_MOCK_CBPPE"
    },
    "RSK": {
        "notion_handle": "@Kevin Plattret",
        "slack_id": "U_MOCK_RSK"
    },
    "CONSOLE": {
        "notion_handle": "@Karina Rangel",
        "slack_id": "U_MOCK_CONSOLE"
    }
}
```

**Mock ValidationResult:**
```python
def mock_validation_result_with_actions():
    return ValidationResult(
        dependency_mapping=[{
            'key': 'INIT-1234',
            'summary': 'Test Initiative',
            'status': 'Proposed',
            'owner_team': 'Payments Risk',
            'issues': [
                {
                    'type': 'epic_count_mismatch',
                    'teams_involved': ['Payments Risk', 'Console'],
                    'teams_with_epics': ['Payments Risk']
                }
            ]
        }],
        ready_to_plan=[],
        planned_regressions=[],
        # ... other fields
    )
```

## Dependencies & Risks

### Dependencies

**External:**
- **Jinja2** - Template engine (add to requirements)
  - Risk: Low (stable, widely used)
  - Mitigation: Pin version in requirements

**Internal:**
- `team_mappings.yaml` - Must be updated with Slack IDs
  - Risk: Medium (manual data entry, potential errors)
  - Mitigation: Validation function catches missing IDs at runtime

**Codebase:**
- `ValidationResult` class - Read-only dependency
  - Risk: Low (well-tested, stable structure)
- `_load_team_mappings()` - Unchanged
  - Risk: Low
- `_load_team_managers()` - Modified return type
  - Risk: Medium (breaks existing callers if not updated)
  - Mitigation: Update all 8 call sites in same commit

### Risks

#### Risk 1: Config Migration Errors
**Description:** Updating `team_mappings.yaml` structure could break existing code

**Likelihood:** Medium
**Impact:** High (breaks console/markdown outputs)

**Mitigation:**
- Implement backward compatibility in `_load_team_managers()`
- Test both old and new config formats
- Update all callers in single atomic commit
- Document migration in commit message

#### Risk 2: Template Syntax Errors
**Description:** Jinja2 template bugs could cause runtime failures

**Likelihood:** Low
**Impact:** Medium (Dust generation fails, but doesn't break validation)

**Mitigation:**
- Test template rendering with diverse data
- Add error handling for template rendering
- Provide clear error messages pointing to template file

#### Risk 3: Missing Slack IDs
**Description:** Manual Slack ID entry could be incomplete or incorrect

**Likelihood:** High (first run)
**Impact:** Low (validation catches it, clear error message)

**Mitigation:**
- Fail-fast validation with clear error messages
- List all missing teams in error output
- Skip managers without IDs (degrade gracefully after initial setup)

#### Risk 4: Extraction Logic Bugs
**Description:** Complex extraction logic could have edge cases

**Likelihood:** Medium
**Impact:** Medium (incorrect action items sent to managers)

**Mitigation:**
- Comprehensive unit tests for each action type
- Integration tests with realistic data
- Start with dry-run/preview before sending to Dust
- Console output provides preview before copy-paste

#### Risk 5: Performance Degradation
**Description:** Extraction + templating could slow down script

**Likelihood:** Low
**Impact:** Low (informational tool, no hard time constraints)

**Mitigation:**
- Profile extraction function with large datasets
- Optimize if needed (early return, lazy evaluation)
- Extraction is O(n) where n = number of issues (acceptable)

## Implementation Checklist

### Pre-Implementation

- [ ] Read origin brainstorm document thoroughly
- [ ] Review existing validation logic and data structures
- [ ] Set up test environment with Jinja2 installed
- [ ] Create feature branch: `git checkout -b feat/dust-bulk-messages`

### Development Steps

#### Configuration

- [ ] Update `team_mappings.yaml` with Slack IDs for all teams
- [ ] Modify `_load_team_managers()` for backward compatibility
- [ ] Add `_validate_dust_config()` function
- [ ] Test config loading with both formats
- [ ] Update all existing `_load_team_managers()` call sites (8 locations)

#### Extraction Layer

- [ ] Implement `extract_manager_actions()` function
- [ ] Test extraction for each action type
- [ ] Test priority ordering
- [ ] Test manager info lookup
- [ ] Test edge cases (empty result, missing teams)

#### Template & Generation

- [ ] Create `templates/` directory
- [ ] Create `templates/dust.j2` template
- [ ] Implement `generate_dust_messages()` function
- [ ] Test grouping and sorting logic
- [ ] Test Jinja2 rendering
- [ ] Test file output with timestamp
- [ ] Test console output format

#### CLI Integration

- [ ] Add `--dust` argument to parser
- [ ] Wire up flag to generation function
- [ ] Test flag recognition
- [ ] Test combination with other flags

#### Testing

- [ ] Write unit tests for config functions (5 tests)
- [ ] Write unit tests for extraction (8 tests)
- [ ] Write unit tests for generation (8 tests)
- [ ] Write unit tests for CLI (3 tests)
- [ ] Write integration tests (5 tests)
- [ ] Run existing test suite for regressions
- [ ] Visual verification of console/markdown outputs

#### Documentation

- [ ] Update README with Dust usage instructions
- [ ] Document Slack ID configuration in README
- [ ] Add inline code comments for complex logic
- [ ] Update CLAUDE.md with template pattern note (optional)

### Post-Implementation

- [ ] Run full test suite: `pytest tests/ -v`
- [ ] Manual test with real dataset
- [ ] Generate sample Dust messages and verify format
- [ ] Commit with descriptive message following conventions
- [ ] Update TODO.md if applicable

## Success Metrics

**Quantitative:**
- 29 new tests added and passing
- 53 existing tests continue passing
- Zero regressions in console/markdown output
- Extraction completes in <1 second for 100 initiatives
- Code coverage ≥90% for new functions

**Qualitative:**
- Dust message format is clear and actionable
- Managers can identify their action items immediately
- Copy-paste workflow is smooth (no manual editing needed)
- Error messages guide user to fix configuration
- Code is maintainable (follows CLAUDE.md conventions)

**User Feedback (Post-Deployment):**
- Managers find Dust messages helpful (subjective)
- Time to respond to action items decreases (if tracked)
- Fewer questions about "what do I need to do?" (anecdotal)

## Future Considerations

### Phase 2: Template Migration (Tracked Separately)

After Dust integration is stable and validated:

1. **Extract console output logic** to `templates/console.j2`
2. **Extract markdown output logic** to `templates/markdown.j2`
3. **Refactor existing functions** to use extraction + templates
4. **Remove duplicated code** (~60% reduction in LOC)
5. **Verify byte-for-byte output compatibility**
6. **Update tests** for refactored functions

**Benefits:**
- DRY principle fully realized
- Easier to add new output formats
- Formatting changes isolated to templates
- Reduced maintenance burden

**Estimated Effort:** Medium (2-3 days)

### Other Future Enhancements

**Discovery Initiative Handling (Open Question):**
- Should Dust messages treat discovery initiatives differently?
- Separate section? Special emoji? Different priority?
- Defer decision until early usage feedback

**Message Personalization:**
- Add manager's name to greeting: "Hi Kevin!"
- Customize tone based on action urgency
- Add context about why action is needed

**Historical Tracking:**
- Compare current Dust messages to previous run
- Highlight new vs. repeat action items
- Track which actions were resolved

**Slack Integration (Alternative to Dust):**
- Direct Slack API integration (requires bot setup)
- See `/docs/SLACK_INTEGRATION.md` for design
- Automatic sending vs. copy-paste

**Email Notifications:**
- Alternative to Slack/Dust for managers without Slack
- Use same extraction logic + email template

## Sources & References

### Origin

- **Brainstorm document:** [docs/brainstorms/2026-03-27-dust-bulk-messages-brainstorm.md](../brainstorms/2026-03-27-dust-bulk-messages-brainstorm.md) - Key decisions carried forward:
  1. **Incremental refactoring approach** - Phase 1 adds Dust without touching existing outputs (risk mitigation)
  2. **Flat data structure** - Enables flexible grouping per output format
  3. **Jinja2 templates** - Clean separation of logic and presentation
  4. **Configuration extension** - Slack IDs added to `team_managers` section
  5. **Fail-fast validation** - Missing Slack IDs caught at startup

### Internal References

- **Architecture decisions:** `validate_initiative_status.py:1-100` (ValidationResult class, data structures)
- **Console output patterns:** `validate_initiative_status.py:646-1022` (existing formatting logic)
- **Markdown output patterns:** `validate_initiative_status.py:1024-1448` (duplicate formatting logic)
- **Configuration loading:** `validate_initiative_status.py:418-450` (YAML parsing patterns)
- **Testing patterns:** `tests/test_validate_initiative_status.py:1-1672` (comprehensive test coverage)
- **CLI patterns:** `validate_initiative_status.py:1479-1563` (argparse setup)
- **DRY principle application:** `docs/solutions/code-quality/cli-error-handling-duplication.md` (prior refactoring)

### External References

- **Jinja2 documentation:** https://jinja.palletsprojects.com/
- **Jinja2 template syntax:** https://jinja.palletsprojects.com/en/3.1.x/templates/
- **Slack message formatting:** https://api.slack.com/reference/surfaces/formatting
- **Dust documentation:** (User-provided context - bulk messaging via Dust chatbot)

### Related Work

- **Previous plans:**
  - `docs/plans/2026-03-06-initiative-filtering.md` (initiative filtering logic)
  - `docs/plans/2026-03-06-jira-dependencies-tracking-design.md` (overall system design)
- **Related documentation:**
  - `docs/SLACK_INTEGRATION.md` (alternative Slack bot approach)
  - `CLAUDE.md` (coding standards and conventions)
  - `README.md` (current usage documentation)

## Notes

**Implementation Approach:**
- Start with config updates and backward compatibility
- Build extraction layer with comprehensive tests
- Add Dust generation incrementally
- Keep existing outputs unchanged throughout

**Testing Philosophy:**
- Test extraction logic separately from rendering
- Use mock data to avoid environment dependencies
- Verify backward compatibility explicitly
- Integration tests cover cross-layer scenarios

**Code Quality:**
- Follow functional style (explicit parameters, immutability)
- Keep functions short (<50 lines where possible)
- Document complex logic with inline comments
- Use type hints for clarity

**User Experience:**
- Fail fast on configuration errors with clear messages
- Provide console preview before file save
- Include helpful summary stats (X managers, Y actions)
- Make copy-paste workflow seamless
