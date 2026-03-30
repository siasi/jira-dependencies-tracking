# Console Template Formatting Tests

## Purpose

The `test_console_template_formatting.py` test suite ensures that the console.j2 template maintains proper formatting, preventing regressions related to:
- Indentation issues
- Missing newlines
- Items running together on the same line

## Tests Coverage

### 1. Action Label Indentation
**Test:** `test_action_labels_have_proper_indentation`
- Ensures all "Action:" labels have exactly 3 spaces of indentation
- Prevents issues where labels appear flush left or over-indented

### 2. Newlines After Action Labels
**Test:** `test_action_labels_followed_by_newline`
- Verifies that Action labels are followed by newlines before checkbox items
- Prevents checkboxes from appearing on the same line as the Action label

### 3. Checkbox Items Separation
**Test:** `test_checkbox_items_on_separate_lines`
- Ensures each checkbox item appears on its own line
- Detects when multiple checkboxes are concatenated on one line

### 4. Epic Status Header Indentation
**Test:** `test_epic_status_headers_have_proper_indentation`
- Verifies "Epics with RED/YELLOW status" headers have 3 spaces of indentation
- Prevents headers from losing their indentation

### 5. Epic Items Separation
**Test:** `test_epic_items_on_separate_lines`
- Ensures each epic item is on its own line
- Prevents multiple epics from running together

### 6. Missing RAG Status Separation
**Test:** `test_missing_rag_status_items_on_separate_lines`
- Verifies RAG status action items are on separate lines
- Each team's RAG status checkbox should be on its own line

### 7. No Excessive Blank Lines
**Test:** `test_no_excessive_blank_lines`
- Prevents more than 3 consecutive blank lines
- Maintains reasonable whitespace throughout the output

### 8. Consistent Indentation
**Test:** `test_consistent_indentation_throughout`
- All section headers use the same indentation (3 spaces)
- Ensures visual consistency across the entire report

### 9. Missing Dependencies Formatting
**Test:** `test_missing_dependencies_checkboxes_properly_formatted`
- Verifies "create epic" checkboxes are properly indented
- Each team's checkbox should be on its own line

## Common Formatting Issues Caught

These tests catch Jinja2 template issues such as:

1. **`{%- if` vs `{% if`**: The `-` strips preceding whitespace, including indentation
2. **`-%}` at end of tags**: Strips whitespace after the tag, including newlines
3. **`{%- endfor %}` vs `{% endfor %}`**: The `-` can strip newlines between loop items

## Running the Tests

```bash
# Run just the formatting tests
python3 -m pytest tests/test_console_template_formatting.py -v

# Run with coverage
python3 -m pytest tests/test_console_template_formatting.py --cov=templates --cov-report=term-missing
```

## Adding New Tests

When adding new sections to the console template that include:
- Action labels
- Epic status headers  
- Checkbox lists
- Any indented sections

Add corresponding tests to verify proper formatting.

## Historical Context

These tests were added after fixing multiple formatting regressions where:
- Jinja2 whitespace control operators (`{%-` and `-%}`) were stripping indentation and newlines
- Action labels were appearing flush left instead of indented
- Multiple checkboxes and epic items were running together on single lines
- The report was difficult to read due to formatting issues

The tests ensure these issues don't recur during future template modifications.
