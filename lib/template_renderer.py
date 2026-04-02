"""Jinja2 template rendering with common filters and configuration."""

from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from .common_formatting import make_clickable_link, make_markdown_link


def get_template_environment() -> Environment:
    """Create configured Jinja2 environment with toolkit-specific filters.

    Returns:
        Configured Jinja2 Environment instance
    """
    # Template directory is at project root
    template_dir = Path(__file__).parent.parent / 'templates'

    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(['html', 'xml']),
        trim_blocks=True,
        lstrip_blocks=True
    )

    # Register custom filters
    env.filters['hyperlink'] = make_clickable_link
    env.filters['markdown_link'] = make_markdown_link

    return env


def render_console_template(template_name: str, **context) -> str:
    """Render a console template with provided context.

    Args:
        template_name: Name of template file (e.g., 'planning_console.j2')
        **context: Template variables

    Returns:
        Rendered template string
    """
    env = get_template_environment()
    template = env.get_template(template_name)
    return template.render(**context)


def render_markdown_template(template_name: str, **context) -> str:
    """Render a markdown template with provided context.

    Args:
        template_name: Name of template file (e.g., 'planning_markdown.j2')
        **context: Template variables

    Returns:
        Rendered template string
    """
    env = get_template_environment()
    template = env.get_template(template_name)
    return template.render(**context)
