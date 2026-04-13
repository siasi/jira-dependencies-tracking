---
title: Document action items implementation and debugging journey
type: compound-doc
status: pending
date: 2026-04-03
---

# Compound Documentation Plan: Action Items Implementation

## Purpose

Document the solution for adding action items and Slack notifications to assess_workload.py, including the debugging journey that uncovered multiple issues.

## What Was Solved

### Primary Feature
- Added action item extraction from data quality issues
- Implemented Slack bulk message generation grouped by manager
- Enhanced console output with checkbox format and manager mentions

### Bugs Discovered & Fixed During Implementation

1. **Team Key Mapping Mismatch** (Slack generation showing only 6 items vs 34 in console)
   - Problem: missing_teams array used display names but team_managers config used project keys
   - Solution: Created forward mapping to resolve display names to project keys
   - Impact: 6 → 25 action items in Slack messages

2. **Wrong Owner Attribution** (Console showing incorrect team as owner)
   - Problem: Used action['responsible_team'] instead of actual initiative owner
   - Solution: Look up owner from initiative_owner_teams data structure
   - Impact: Correct owner now displayed for all initiatives

3. **Discovery Initiative False Positives** (Discovery initiatives flagged for missing epics)
   - Problem: assess_workload.py didn't exclude [Discovery] initiatives from epic checks
   - Solution: Added is_discovery_initiative() helper matching check_planning.py pattern
   - Impact: 34 → 31 action items (3 Discovery initiatives correctly excluded)

4. **BOT Team Missing from Extraction** (27 false positive missing epic actions)
   - Problem: BOT team missing from config/jira_config.yaml teams list
   - Solution: Added BOT to extraction configuration
   - Impact: 31 → 4 action items (27 BOT-related false positives eliminated)

5. **Hardcoded Company-Specific Data** (Security issue)
   - Problem: Company URLs, manager names, Slack IDs in code/docstrings
   - Solution: Added get_jira_base_url() to read from config, sanitized examples
   - Impact: No sensitive data committed to public repo

## Files Modified

- `assess_workload.py` - Core implementation
  - extract_workload_actions()
  - generate_workload_slack_messages()
  - print_workload_report() updates
  - get_jira_base_url() for sanitization
- `templates/notification_slack.j2` - Added workload action types
- `config/jira_config.yaml` - Added BOT team (local, gitignored)

## Key Learnings

### Team Key Mapping Pattern
When dealing with team data that flows through multiple layers (display names → project keys → manager lookups):
- Always create bidirectional mappings (forward and reverse)
- Document which layer uses which identifier format
- Validate at boundaries where format changes

### Discovery Initiative Exemption Pattern
Validation rules that exempt certain initiative types should be:
- Consistent across all validation scripts
- Clearly documented with helper functions
- Named to indicate what they check (is_discovery_initiative, not just skip_validation)

### Configuration-Driven Extraction
Teams/components that should be extracted must be:
- Explicitly listed in extraction configuration
- Validated that config matches actual Jira project structure
- Documented in setup/README so teams aren't accidentally omitted

### Security: Sanitizing Company Data
When building open-source or shared tools:
- Never hardcode company-specific URLs, names, or IDs
- Use config files (gitignored) for company-specific data
- Sanitize docstring examples to use generic placeholders
- Read base URLs from config, not hardcode them

## Category Suggestion

`integration-issues` - This involves integration between multiple data structures (Jira extraction, team mappings, manager config) and uncovered issues in how they connect.

Alternative: `data-quality` - Multiple data quality issues discovered during implementation

## Prevention Strategies

1. **Team mapping validation**: Add test that verifies all teams in extraction config have corresponding manager entries
2. **Bidirectional mapping tests**: Test that forward and reverse mappings are inverses
3. **Config completeness check**: Script to validate that all teams referenced in Jira data exist in config files
4. **Sanitization lint rule**: Add pre-commit hook to catch hardcoded company URLs/names
5. **Discovery initiative tests**: Add test coverage for is_discovery_initiative() pattern

## Related Documentation

- check_planning.py - Original action item pattern
- docs/plans/2026-04-03-001-feat-action-items-workload-analysis-plan.md - Implementation plan
- PR #6: https://github.com/siasi/jira-dependencies-tracking/pull/6

## Next Steps

Run `/ce:compound` in a fresh session to generate comprehensive solution documentation in:
- `docs/solutions/integration-issues/action-items-team-mapping-debugging.md`
or
- `docs/solutions/data-quality/team-config-validation-patterns.md`

## Commit References

- 2978138 - Initial implementation
- c73bf5b - Fixed team key mapping
- 10647f5 - Fixed owner attribution
- 4b6adb1 - Discovery initiative exemption
- e53eac6 - Sanitized company-specific data
- 91177eb - Updated plan with Phase 2 tasks
