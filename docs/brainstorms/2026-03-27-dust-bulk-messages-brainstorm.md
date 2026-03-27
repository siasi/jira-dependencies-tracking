---
date: 2026-03-27
topic: dust-bulk-messages
---

# Dust Bulk Message Integration for Manager Notifications

## What We're Building

**Phase 1: Extraction Layer + Dust Output**

Refactor `validate_initiative_status.py` to:
1. Extract action items into a flat, richly-annotated data structure
2. Generate Dust-compatible bulk messages using Jinja2 templates
3. Keep existing console/markdown outputs unchanged (migrate in Phase 2)

**Dust Output Features:**
- Copy-paste ready format for Dust bulk messaging
- Grouped by manager, then by initiative
- Includes all 4 action types (missing dependencies, missing RAG, missing assignee, ready to PLANNED)
- Friendly tone with emoji and Jira links
- Prints to console + saves to file

## Why This Approach

**Considered:**
- **Simple function approach** - Quick but duplicates logic between outputs
- **Template-only for Dust** - Doesn't solve broader formatting issues across console/markdown
- **Big-bang refactor** - Risky, could break working console/markdown outputs

**Chosen: Incremental extraction + templates**
- Separates data extraction from presentation (DRY principle)
- Jinja2 templates make formatting easy to modify without touching code
- Incremental rollout minimizes risk to existing working outputs
- Proves the pattern with Dust before migrating console/markdown
- Foundation for future output formats (email, API, etc.)

## Key Decisions

### Data Structure

**Format:** Flat list of action items with rich metadata

Each action item contains:
```python
{
    'initiative_key': 'INIT-1234',
    'initiative_title': 'Project Alpha',
    'initiative_status': 'Planned',
    'initiative_url': 'https://truelayer.atlassian.net/browse/INIT-1234',
    'section': 'planned_regressions',  # which report section
    'action_type': 'missing_dependencies',
    'priority': 1,  # implicit ordering
    'responsible_team': 'RSK',
    'responsible_manager': 'Manager C',
    'slack_member_id': 'U01ABC123',
    'description': 'Create epic',
    'epic_key': None  # or epic key if relevant
}
```

**Why flat structure:**
- Console/Markdown need to group by section → initiative
- Dust needs to group by manager → initiative
- Each output format filters, groups, and sorts as needed
- Maximum flexibility for different output requirements

### Configuration

**Extend `team_mappings.yaml`:**

Update `team_managers` section to include both Notion handle and Slack member ID:

```yaml
team_managers:
  "CBPPE":
    notion_handle: "@Manager B "
    slack_id: "U01F3QUHP0B"
  "CONSOLE":
    notion_handle: "@Manager A"
    slack_id: "U02ABC456"
  # ... other teams
```

**Slack ID Lookup:** Manual (one-time setup per manager)

### Templates

**Location:** `templates/` directory at project root

**Files:**
- `dust.j2` - Dust bulk message format (Phase 1)
- `console.j2` - Console output (Phase 2)
- `markdown.j2` - Markdown report (Phase 2)

**Template Engine:** Jinja2

### Dust Message Format

**Structure:**
```
Recipient: U01F3QUHP0B
Message: Hi! Here are your action items from the latest initiative validation:

You have 5 action items across 3 initiatives.

INIT-1234
:warning: Missing dependencies - Create epic

INIT-5678
:raising_hand: Missing assignee

---

Recipient: U02ABC456
Message: Hi! Here are your action items...

---
```

**Format Details:**
- **Delimiter:** `---` between messages
- **Batch mode:** All messages in one paste
- **Greeting:** Friendly tone ("Hi! Here are your action items...")
- **Summary:** Count of actions and initiatives at top
- **Grouping:** By initiative, then by action (ordered by priority)
- **Context:** Minimal - just initiative key
- **Empty lists:** Skip managers with no action items

### Emoji Mapping

- **Missing dependencies:** `:warning:`
- **Missing RAG status:** `:warning:`
- **Missing assignee:** `:raising_hand:`
- **Ready to PLANNED:** `:rocket:`

### Link Format

**Jira Issues:** `<https://truelayer.atlassian.net/browse/INIT-1234|INIT-1234>`

- **Base URL:** `https://truelayer.atlassian.net/browse`
- **Link text:** Issue key only (not title)
- **Format:** Slack/Dust angle bracket syntax with pipe separator

### Action Types Included

All four action types:

1. **Missing dependencies** - Teams need to create epics for cross-team initiatives
2. **Missing RAG status** - Teams need to set RAG status on their epics
3. **Missing assignee** - Initiatives need an assignee before they can be planned
4. **Ready to move to PLANNED** - Proposed initiatives that meet all criteria

### Priority Ordering

**Strategy:** Implicit ordering (no explicit scores)

**Order:**
1. Blocking issues (missing dependencies, missing RAG, missing assignee)
2. Ready to PLANNED (non-blocking, informational)

Within each initiative, actions are ordered by impact on initiative progress.

### Invocation

**CLI Flag:** `--dust`

**Usage:**
```bash
# Generate Dust messages only
python validate_initiative_status.py --dust

# Generate multiple outputs
python validate_initiative_status.py --verbose --markdown --dust
```

### Output Destination

**Both console and file:**

1. **Console:** Print for immediate preview
2. **File:** Save to `extracts/dust_messages_YYYY-MM-DD_HHMMSS.txt`

**Benefits:**
- Console gives immediate feedback
- File makes it easy to review full content before copying
- File provides history of what was sent when
- Consistent with existing `--markdown` behavior

## Implementation Plan

### Phase 1: Extraction + Dust (Current)

1. **Add Jinja2 dependency**
   - Update requirements or add to imports
   - Document in README if needed

2. **Create templates directory**
   - `mkdir templates/`
   - Create `templates/dust.j2` with message format

3. **Update configuration**
   - Modify `team_mappings.yaml` structure
   - Convert `team_managers` from string to dict with `notion_handle` and `slack_id`
   - Document new format in comments

4. **Create extraction function**
   - `extract_manager_actions(result: ValidationResult) -> List[Dict]`
   - Iterate through all result categories (healthy, planned_regressions, proposed_ready, etc.)
   - Build flat list of action items with all metadata
   - Handle missing dependencies, missing RAG, missing assignee, ready to PLANNED

5. **Create Dust generation function**
   - `generate_dust_messages(result: ValidationResult, output_dir: Path) -> None`
   - Call extraction function
   - Group actions by `slack_member_id`, then by `initiative_key`
   - Skip managers with no actions
   - Render Jinja2 template
   - Print to console
   - Save to file with timestamp

6. **Add CLI flag**
   - Add `--dust` argument to argument parser
   - Wire up to call `generate_dust_messages()` when flag is present

7. **Write tests**
   - Test extraction logic with mock ValidationResult
   - Test Dust message generation with mock Slack IDs
   - Test grouping and ordering
   - Test empty action list handling
   - Test file output

### Phase 2: Template Migration (Future)

1. **Create console template**
   - `templates/console.j2`
   - Port existing console output format to Jinja2

2. **Create markdown template**
   - `templates/markdown.j2`
   - Port existing markdown format to Jinja2

3. **Refactor console output**
   - Update `print_validation_report()` to use extraction + template
   - Verify output matches existing format byte-for-byte
   - Update tests

4. **Refactor markdown output**
   - Update `generate_markdown_report()` to use extraction + template
   - Verify output matches existing format
   - Update tests

5. **Clean up**
   - Remove old formatting code
   - Consolidate duplicate logic
   - Update documentation

## Open Questions

### Discovery Initiatives
**Question:** Should managers be notified about discovery initiatives differently?

**Context:** Discovery initiatives skip epic/RAG validation but still need assignees. Should Dust messages:
- Include them with a special note?
- Exclude them entirely?
- Group them separately?

**Status:** Keeping open for now - will decide based on early usage feedback

## Testing Strategy

**Approach:** Use mock Slack IDs in tests

**Example mock data:**
```python
MOCK_TEAM_MANAGERS = {
    "CBPPE": {
        "notion_handle": "@Manager B ",
        "slack_id": "U_MOCK_CBPPE"
    },
    "RSK": {
        "notion_handle": "@Manager C",
        "slack_id": "U_MOCK_RSK"
    }
}
```

**Benefits:**
- No dependency on real Slack IDs
- Tests remain stable across environments
- Clear that test data is fake

## Next Steps

→ `/ce:plan` for detailed implementation plan with file changes

## Related Documentation

- [Slack Integration Design](../SLACK_INTEGRATION.md) - Original brainstorming for custom Slack app approach
- [CLAUDE.md](../../CLAUDE.md) - Project coding standards and workflow
