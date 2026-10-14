"""
{% vite 'src/site.ts' 'src/islands/checkout.tsx' %}: the script (and CSS) tags for Vite entries.
In development they come straight from the Vite dev server (with React fast refresh); in production
from the build's manifest, with each entry's CSS and its shared chunks preloaded.
{% asset 'images/front.webp' %}: a file from frontend/public.
"""
import json

from django import template
from django.conf import settings
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

register = template.Library()

_manifest = {'mtime': None, 'data': {}}

_REFRESH = """<script type="module">
import RefreshRuntime from '{dev}/@react-refresh'
RefreshRuntime.injectIntoGlobalHook(window)
window.$RefreshReg$ = () => {{}}
window.$RefreshSig$ = () => (type) => type
window.__vite_plugin_react_preamble_installed__ = true
</script>"""


def _load_manifest():
    path = settings.VITE_MANIFEST
    mtime = path.stat().st_mtime
    if mtime != _manifest['mtime']:
        _manifest['data'] = json.loads(path.read_text(encoding='utf-8'))
        _manifest['mtime'] = mtime
    return _manifest['data']


def _url(file):
    return settings.VITE_ASSETS_URL.rstrip('/') + '/' + file


@register.simple_tag
def vite(*entries):
    dev = settings.VITE_DEV_SERVER
    if dev:
        tags = [_REFRESH.format(dev=dev), f'<script type="module" src="{dev}/@vite/client"></script>']
        tags += [f'<script type="module" src="{dev}/{entry}"></script>' for entry in entries]
        return mark_safe('\n'.join(tags))

    manifest = _load_manifest()
    css, preload, scripts = [], [], []

    def walk(key, top):
        chunk = manifest[key]
        for file in chunk.get('css', []):
            if file not in css:
                css.append(file)
        for imported in chunk.get('imports', []):
            if manifest[imported]['file'] not in preload:
                preload.append(manifest[imported]['file'])
            walk(imported, False)
        if top:
            scripts.append(chunk['file'])

    for entry in entries:
        walk(entry, True)
    return format_html_join('\n', '<link rel="stylesheet" href="{}">', ((_url(f),) for f in css)) + \
        format_html_join('\n', '<link rel="modulepreload" href="{}">', ((_url(f),) for f in preload)) + \
        format_html_join('\n', '<script type="module" src="{}"></script>', ((_url(f),) for f in scripts))


@register.simple_tag
def asset(path):
    base = settings.VITE_DEV_SERVER or settings.VITE_ASSETS_URL.rstrip('/')
    return format_html('{}/{}', base, path.lstrip('/'))
