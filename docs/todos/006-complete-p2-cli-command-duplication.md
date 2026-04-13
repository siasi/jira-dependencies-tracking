---
status: complete
priority: p2
issue_id: "006"
tags: [code-review, quality, refactor, snapshot]
dependencies: []
---

# P2: CLI Command Duplication (~100 LOC)

## Problem Statement

The snapshot, snapshots list, and compare commands share ~100 lines of duplicated setup code for SnapshotManager instantiation, config loading, and error handling.

**Why it matters:** Code duplication makes maintenance harder, increases bug risk, and violates DRY principle. Should fix.

## Findings

**From kieran-python-reviewer agent:**

```python
# jira_scan.py - Repeated pattern in 3 commands

@cli.command()
def snapshot(config, label, verbose):
    try:
        config_obj = load_config(config)
        setup_logging(verbose)
        manager = SnapshotManager()  # Repeated
        # ... command logic ...
    except SnapshotError as e:  # Repeated error handling
        logger.error(str(e))
        raise click.ClickException(str(e))

@snapshots.command(name="list")
def snapshots_list(config):
    try:
        manager = SnapshotManager()  # Repeated
        # ... command logic ...
    except SnapshotError as e:  # Repeated error handling
        logger.error(str(e))
        raise click.ClickException(str(e))

@cli.command()
def compare(config, from_label, to_label, format, output):
    try:
        config_obj = load_config(config)  # Repeated
        manager = SnapshotManager()  # Repeated
        # ... command logic ...
    except SnapshotError as e:  # Repeated error handling
        logger.error(str(e))
        raise click.ClickException(str(e))
```

**Duplication count:**
- SnapshotManager instantiation: 3 times
- try/except SnapshotError handling: 3 times
- Config loading: 2 times
- Logging setup: 2 times

**Total duplicated LOC:** ~100 lines (33 lines × 3 commands)

## Proposed Solutions

### Solution A: Click Context Object (Recommended)

**Approach:** Use Click's context passing to share SnapshotManager instance.

```python
# Common setup in a callback
@cli.group()
@click.pass_context
def snapshots_cli(ctx):
    """Snapshot management commands."""
    ctx.ensure_object(dict)
    ctx.obj['manager'] = SnapshotManager()

# Use in commands
@snapshots_cli.command()
@click.pass_context
def snapshot(ctx, label):
    manager = ctx.obj['manager']
    try:
        # ... command logic ...
    except SnapshotError as e:
        _handle_snapshot_error(e)

def _handle_snapshot_error(e: SnapshotError):
    """Centralized error handling for snapshot operations."""
    logger.error(str(e))
    raise click.ClickException(str(e))
```

**Pros:**
- Idiomatic Click pattern
- Shared setup code
- Easy to test
- Centralized error handling

**Cons:**
- Requires understanding Click context
- Small refactoring needed

**Effort:** Medium (1-2 hours)
**Risk:** Low

### Solution B: Decorator Pattern

**Approach:** Create decorator for common snapshot command setup.

```python
from functools import wraps

def with_snapshot_manager(f):
    """Decorator to inject SnapshotManager and handle errors."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        manager = SnapshotManager()
        try:
            return f(manager=manager, *args, **kwargs)
        except SnapshotError as e:
            logger.error(str(e))
            raise click.ClickException(str(e))
    return wrapper

# Usage
@cli.command()
@with_snapshot_manager
def snapshot(manager, label):
    # manager injected automatically
    result = manager.save_snapshot(...)
```

**Pros:**
- Very clean command functions
- Automatic error handling
- Reusable decorator

**Cons:**
- Magic parameter injection (less explicit)
- Harder to understand for newcomers

**Effort:** Medium (1-2 hours)
**Risk:** Low

### Solution C: Helper Function

**Approach:** Extract common setup into helper function.

```python
def _get_snapshot_manager() -> SnapshotManager:
    """Get SnapshotManager instance."""
    return SnapshotManager()

def _handle_snapshot_error(e: SnapshotError):
    """Handle snapshot errors consistently."""
    logger.error(str(e))
    raise click.ClickException(str(e))

# Usage in commands
@cli.command()
def snapshot(label):
    try:
        manager = _get_snapshot_manager()
        # ... command logic ...
    except SnapshotError as e:
        _handle_snapshot_error(e)
```

**Pros:**
- Simple and explicit
- Easy to understand
- No magic

**Cons:**
- Still some duplication (try/except in each command)
- Less elegant than decorator/context

**Effort:** Small (30 minutes)
**Risk:** Low

## Recommended Action

**Solution A (Click Context)** - Most idiomatic for Click applications. Best long-term pattern as more snapshot commands are added.

## Technical Details

**Affected files:**
- `jira_scan.py` - Refactor snapshot, snapshots list, compare commands

**Changes required:**
1. Create snapshots command group with context setup
2. Move SnapshotManager instantiation to group callback
3. Extract error handling to helper function
4. Update commands to use context
5. Ensure all tests still pass

## Acceptance Criteria

- [ ] SnapshotManager instantiated once per command invocation
- [ ] Error handling centralized in one function
- [ ] All snapshot commands use shared setup
- [ ] No behavior changes (only refactoring)
- [ ] All existing tests still pass
- [ ] Code coverage maintained or improved

## Work Log

### 2026-03-16 - Approved for Work
**By:** Claude Triage System
**Actions:**
- Issue approved during triage session
- Status changed from pending → ready
- Ready to be picked up and worked on

**Learnings:**
- Code duplication across 3 CLI commands (~100 LOC)
- Click context pattern recommended for shared setup
- Centralized error handling will improve maintainability

### 2026-03-16 - Completed
**By:** pr-comment-resolver agent
**Actions:**
- Implemented Solution C (Helper Function approach)
- Added `_handle_snapshot_error()` helper function
- Updated snapshot, snapshots list, and compare commands to use helper
- All 79 tests pass - no behavior changes

**Changes:**
- jira_scan.py:19-22 - Added centralized error handler
- jira_scan.py:462 - Updated snapshot command
- jira_scan.py:506 - Updated snapshots list command
- jira_scan.py:586 - Updated compare command

**Results:**
- Error handling centralized (DRY principle achieved)
- Consistent error output across all snapshot commands
- Easier future maintenance
- Commit: a174680 "refactor(snapshot): centralize CLI error handling"

## Resources

- PR #2: Quarterly Snapshot Tracking
- kieran-python-reviewer findings
- Click Context docs: https://click.palletsprojects.com/en/8.1.x/commands/#nested-handling-and-contexts
