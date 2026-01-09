"""
Simple Jinja2 template loader for prompts.

Loads .jinja2 templates from the templates directory and renders them
with provided context variables.
"""

from functools import lru_cache
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .templates import Template

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _validate_templates():
    """Validate all template constants have corresponding files. Fails fast at import."""
    for name in dir(Template):
        if not name.startswith("_"):
            template_name = getattr(Template, name)
            path = TEMPLATES_DIR / f"{template_name}.jinja2"
            if not path.exists():
                raise FileNotFoundError(f"Template missing: {path}")


_validate_templates()


@lru_cache(maxsize=1)
def _get_environment() -> Environment:
    """Create and cache the Jinja2 environment."""
    return Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(default=False),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render(template_name: str, **context) -> str:
    """
    Load and render a Jinja2 template.

    Args:
        template_name: Name of the template file (without .jinja2 extension)
        **context: Variables to pass to the template

    Returns:
        Rendered template string
    """
    env = _get_environment()
    template = env.get_template(f"{template_name}.jinja2")
    return template.render(**context)
