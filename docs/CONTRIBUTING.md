# Contributing

## Adding a New Script

When adding a new analysis script:

1. **Naming**: Use verb-noun pattern (e.g., `report_blockers.py`, `track_velocity.py`)
2. **Location**: Place in root directory (for easy execution)
3. **Imports**: Use `from lib.X import Y` for shared utilities
4. **Templates**: Create `<name>_console.j2` and `<name>_markdown.j2` in templates/
5. **Output**: Support `--markdown FILENAME` option for markdown output
6. **Hyperlinks**: Use `make_clickable_link()` from `lib.common_formatting`
7. **Data loading**: Use `get_data_file_or_exit()` from `lib.file_utils`
8. **Tests**: Add tests in `tests/test_<name>.py`
9. **Documentation**: Update README.md with new command

## Code Standards

Follow guidelines in CLAUDE.md:
- Write meaningful tests with assertions for all code
- Avoid duplicated test assertions
- Maintain evolving test coverage
- Apply Four Rules of Simple Design:
  1. Code works (passes tests)
  2. Reveals intent
  3. No duplication
  4. Minimal elements
- Prefer functional style:
  - Use explicit parameters
  - Prefer immutability
  - Prefer declarative over imperative
  - Minimize state

## Architecture

- Modularize by concern, not by technical layer
- One responsibility per module
- Low inter-module coupling
- Short functions, no overengineering

## Testing

- Write and pass tests before finalizing
- Run full test suite: `pytest tests/ -v`
- Each commit should include tests
- Do not change test assertions during refactoring
- Do not skip failing tests

## Error Handling

- **Scripts only** (not library code):
  - Fail fast on config errors (startup/validation)
  - Degrade gracefully on data issues (runtime)
  - Clear error messages with field names
  - No silent failures

## Commit Strategy

Each commit:
- Self-contained
- Includes tests
- Uses 50/70 commit message format
  - First line: max 50 chars
  - Body: wrapped at 70 chars

## Common Utilities

When writing scripts, use these shared utilities:

### Formatting
```python
from lib.common_formatting import make_clickable_link, make_markdown_link

# Console output with ANSI hyperlinks
link = make_clickable_link("INIT-123", "https://jira.example.com/browse/INIT-123")

# Markdown output
md_link = make_markdown_link("INIT-123", "https://jira.example.com/browse/INIT-123")
```

### Template Rendering
```python
from lib.template_renderer import render_console_template, render_markdown_template

# Render console template
output = render_console_template('my_console.j2', data=data, verbose=args.verbose)

# Render markdown template
md_output = render_markdown_template('my_markdown.j2', data=data)
```

### File Discovery
```python
from lib.file_utils import get_data_file_or_exit

# Auto-discover or use specified file
data_file = get_data_file_or_exit(args.data_file)
```

## Template Guidelines

### Console Templates
- Use ANSI hyperlinks via `{{ text|hyperlink(url) }}` filter
- Keep indentation consistent
- Use emoji for visual scanning (✅, ⚠️, ❌, 🔍)

### Markdown Templates
- Use markdown links: `[text](url)`
- Structure with headers (##, ###)
- Use tables for tabular data
- Include horizontal rules (---) for section separation

## Review Process

1. Run tests: `pytest tests/ -v`
2. Check for code duplication
3. Verify documentation updated
4. Run scripts manually with test data
5. Check output formatting (console and markdown)
