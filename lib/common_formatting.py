"""Common formatting utilities for console and markdown output."""


def make_clickable_link(text: str, url: str) -> str:
    """Create clickable hyperlink using ANSI escape codes for terminal output.

    Uses ANSI escape codes supported by modern terminals:
    - iTerm2 (macOS)
    - Terminal.app (macOS 10.14+)
    - GNOME Terminal (Linux)
    - Windows Terminal
    - VS Code integrated terminal
    - Alacritty, Kitty, and other modern terminals

    Note: In terminals without hyperlink support, the text will display normally
    without the link functionality.

    Args:
        text: Display text for the link
        url: URL to link to

    Returns:
        String with ANSI escape codes for clickable terminal link

    Example:
        >>> make_clickable_link("INIT-123", "https://jira.example.com/browse/INIT-123")
        '\\x1b]8;;https://jira.example.com/browse/INIT-123\\x1b\\\\INIT-123\\x1b]8;;\\x1b\\\\'
    """
    if not url:
        return text
    # ANSI escape code format: \033]8;;URL\033\\TEXT\033]8;;\033\\
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


def make_markdown_link(text: str, url: str) -> str:
    """Create markdown-formatted hyperlink.

    Args:
        text: Display text for the link
        url: URL to link to

    Returns:
        Markdown link string

    Example:
        >>> make_markdown_link("INIT-123", "https://jira.example.com/browse/INIT-123")
        '[INIT-123](https://jira.example.com/browse/INIT-123)'
    """
    if not url:
        return text
    return f"[{text}]({url})"
