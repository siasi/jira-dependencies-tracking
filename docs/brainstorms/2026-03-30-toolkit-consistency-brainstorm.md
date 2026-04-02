---
date: 2026-03-30
topic: toolkit-consistency
---

# Toolkit Consistency & Organization

## What We're Building

A consistent, well-organized engineering manager toolkit that has clear identity, logical structure, standardized outputs, and a sensible data flow. This refactor addresses the organic growth of the codebase into a more intentional design.

**Origin observations:** docs/brainstorms/2026-03-30-tookit-consistency.md

## Why This Approach

The toolkit has evolved from a single script to multiple scripts serving different use cases (planning validation, workload analysis, future delivery tracking). Rather than continue organic growth, we're establishing consistent patterns now before adding new capabilities.

**Priorities:**
1. Clean up current chaos first (naming, organization, consistency)
2. Fix data extraction strategy
3. Defer individual manager features (--team option) until foundation is solid

## Key Decisions

### 1. Repository Identity & Structure

**Decision:** Rename to `jira-em-toolkit` and reorganize into clear hierarchy

**Structure:**
```
jira-em-toolkit/
├── config/
│   ├── team_mappings.yaml
│   ├── strategic_objectives.yaml (future split)
│   └── jira_config.yaml (future)
├── lib/
│   ├── jira_client.py (extract common code)
│   ├── template_renderer.py (shared template logic)
│   └── common_formatting.py (hyperlinks, etc.)
├── scripts/
│   ├── extract.py (was jira_extract.py)
│   ├── validate_planning.py (was validate_initiative_status.py)
│   ├── analyze_workload.py (was analyse_workload.py)
│   └── track_delivery.py (future)
├── templates/
│   ├── planning_console.j2
│   ├── planning_markdown.j2
│   ├── workload_console.j2
│   └── workload_markdown.j2
└── docs/
    ├── brainstorms/
    └── plans/
```

**Naming pattern:** Verb-noun structure for all scripts
- `extract.py` - Extract data from Jira
- `validate_planning.py` - Validate planning readiness
- `analyze_workload.py` - Analyze team workload

**Rationale:** Clear hierarchy separates configuration, reusable code, executable scripts, and templates. Verb-noun naming makes purpose immediately clear.

### 2. Output Consistency

**Decision:** Standardize output formats across all scripts

**Standards:**
- **Default:** Console output with ANSI hyperlinks for all Jira keys
- **Markdown:** `--markdown FILE` writes markdown to specified file (never stdout)
- **CSV:** Only where it makes sense (not standardized across all scripts)
- **Templates:** All formatting uses Jinja2 templates (no inline formatting in Python)
- **Hyperlinks:** Every Jira key (INIT-*, EPIC-*) is clickable in all output formats
  - Console: ANSI escape codes (`\033]8;;URL\033\\TEXT\033]8;;\033\\`)
  - Markdown: `[KEY](URL)` format
  - CSV: Plain keys (URLs in separate column if needed)

**Rationale:** Consistent user experience across all tools. Hyperlinks save time navigating to Jira. Jinja2 templates separate presentation from logic.

### 3. Data Extraction Strategy

**Decision:** Extract all data once, filter in processing scripts

**Implementation:**
- `extract.py` always extracts: Proposed, Planned, In Progress, Blocked initiatives
- Each processing script filters internally based on its needs:
  - `validate_planning.py`: Only Proposed/Planned for target quarter
  - `analyze_workload.py`: All In Progress + Planned initiatives
  - `track_delivery.py` (future): Only In Progress initiatives
- Keep existing logic to auto-discover most recent data file (no need to specify --data-file)
- Single JSON file as source of truth for all reports

**Rationale:** Single extraction is faster and ensures consistency across reports. Filtering in scripts keeps each tool focused on its use case. Auto-discovery maintains current workflow.

### 4. Individual Manager Features

**Decision:** Defer until after cleanup is complete

**Future capability:** Add `--team TEAM_KEY` option to filter by team ownership
- Personal view for individual engineering managers
- Still useful to run centrally for cross-team visibility
- Requires solid foundation first

**Rationale:** Focus on consistency and organization before adding new capabilities. Don't build on shaky foundation.

## Implementation Phases

### Phase 1: Repository Structure (Low Risk)
- Create new directory structure (config/, lib/, scripts/, templates/)
- Move files to new locations
- Update import paths
- Rename repository
- Update documentation

**Risk:** Import path updates could break things if not thorough

### Phase 2: Script Renaming (Low Risk)
- Rename scripts to verb-noun pattern
- Update any references in docs/scripts
- Add backwards-compatibility symlinks if needed

**Risk:** Minimal - mostly file renames

### Phase 3: Output Standardization (Medium Risk)
- Extract common formatting code to lib/
- Ensure all scripts use Jinja2 templates
- Standardize --markdown option behavior across scripts
- Add hyperlinks to any scripts missing them
- Remove inconsistent output options

**Risk:** Need to test all output formats thoroughly

### Phase 4: Data Extraction Refactor (Medium Risk)
- Modify extract.py to always get all statuses
- Update each script to filter internally
- Verify auto-discovery logic works with new structure
- Test that each script gets correct subset of data

**Risk:** Logic changes could filter incorrectly

### Phase 5: Testing & Documentation (Low Risk)
- Update all documentation
- Test end-to-end workflows
- Update README with new structure
- Document new patterns for future scripts

**Risk:** Minimal - just documentation

## Open Questions

- Should we split team_mappings.yaml into multiple files (team_mappings.yaml, strategic_objectives.yaml, manager_info.yaml)?
- Do we need backwards-compatibility symlinks for old script names during transition?
- Should templates have more descriptive names (e.g., `planning_report_console.j2` vs `planning_console.j2`)?
- What's the migration path for existing users? Can they continue using old commands?

## Success Criteria

- [ ] All scripts follow verb-noun naming pattern
- [ ] Configuration files centralized in config/
- [ ] Shared code extracted to lib/
- [ ] All templates in templates/ directory
- [ ] Every script outputs ANSI hyperlinks in console mode
- [ ] --markdown FILE behavior consistent across scripts
- [ ] extract.py gets all initiative data
- [ ] Each processing script filters internally
- [ ] Auto-discovery of recent data file works
- [ ] All existing workflows still work
- [ ] Documentation updated

## Next Steps

→ `/ce:plan` to create detailed implementation plan with file moves, refactoring steps, and testing strategy
