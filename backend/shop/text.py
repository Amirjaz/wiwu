"""
The light markup of policy pages and FAQ answers, so the client can edit them in the panel without
HTML: a blank line between paragraphs, '## ' for a heading, '- ' for list items, **bold**.
Everything else is escaped.
"""
import re

from django.utils.html import escape
from django.utils.safestring import mark_safe


def _inline(text):
    return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', escape(text))


def render(source):
    html = []
    for block in re.split(r'\n\s*\n', (source or '').strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        if lines[0].startswith('## '):
            html.append(f'<h2>{_inline(lines[0][3:])}</h2>')
            lines = lines[1:]
            if not lines:
                continue
        if all(line.startswith('- ') for line in lines):
            html.append('<ul>' + ''.join(f'<li>{_inline(line[2:])}</li>' for line in lines) + '</ul>')
        else:
            html.append('<p>' + '<br>'.join(_inline(line) for line in lines) + '</p>')
    return mark_safe('\n'.join(html))
