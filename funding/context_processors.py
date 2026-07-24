from .site_text import SITE_TEXT


def site_text(request):
    """Makes every static SITE_TEXT entry available in every template as `text.section.key`.

    Entries containing embedded {{ variables }} still need the {% text %} tag
    (see templatetags/site_text_tags.py) to actually resolve those variables —
    this processor only exposes the raw dict for direct/static lookups.
    """
    return {'text': SITE_TEXT}
