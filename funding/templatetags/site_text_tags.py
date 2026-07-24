from django import template
from django.template import Template as DjangoTemplate
from django.utils.safestring import mark_safe

from ..site_text import get_text

register = template.Library()


@register.simple_tag(takes_context=True)
def text(context, key_path):
    """Render a SITE_TEXT entry that contains embedded {{ variables }} (e.g.
    "Applications close on {{ program.deadline }}.") against the current
    template's own context, so those variables resolve normally.

    Static entries with no embedded variables don't need this tag — use
    {{ text.section.key }} directly instead (see context_processors.py).
    """
    raw = get_text(key_path)
    return mark_safe(DjangoTemplate(raw).render(context))
