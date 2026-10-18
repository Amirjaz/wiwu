"""
{% vite 'src/site.ts' 'src/islands/checkout.tsx' %}: the script (and CSS) tags for Vite entries.
In development they come straight from the Vite dev server (with React fast refresh); in production
from the build's manifest, with each entry's CSS and its shared chunks preloaded.
{% asset 'images/front.webp' %}: a file from frontend/public. In production its address carries a short
hash of its content (?v=), so a file changed under the same name (a new photo, a rebuilt 3D model) is
fetched again rather than served from ArvanCloud's or a browser's week-long cache.
"""
import hashlib
import json
from pathlib import Path

from django import template
from django.conf import settings
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

register = template.Library()

_manifest = {'mtime': None, 'data': {}}
_versions = {}  # public file -> its content hash, per process (a deploy restarts the processes)

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


def _version(path):
    """The first 8 hex digits of a public file's MD5, from the build next to its manifest ('' if it
    isn't there)."""
    if path not in _versions:
        try:
            _versions[path] = hashlib.md5((Path(settings.VITE_MANIFEST).parent.parent / path).read_bytes()).hexdigest()[:8]
        except OSError:
            _versions[path] = ''
    return _versions[path]


@register.simple_tag
def asset(path):
    path = path.lstrip('/')
    if settings.VITE_DEV_SERVER:
        return format_html('{}/{}', settings.VITE_DEV_SERVER, path)
    version = _version(path)
    return format_html('{}/{}{}', settings.VITE_ASSETS_URL.rstrip('/'), path, f'?v={version}' if version else '')
