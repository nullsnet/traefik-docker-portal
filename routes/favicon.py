import logging
from flask import Blueprint, request, Response
import requests

favicon_bp = Blueprint('favicon', __name__)
_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
_CACHE_HEADERS = {
    'Cache-Control': 'public, max-age=86400',
}


def _proxy_response(url: str, verify=True) -> Response:
    try:
        resp = requests.get(url, timeout=2, headers={'User-Agent': _USER_AGENT}, verify=verify)
        if resp.status_code == 200 and len(resp.content) > 0:
            return Response(resp.content, status=200, headers={
                'Content-Type': resp.headers.get('Content-Type', 'image/png'),
                **_CACHE_HEADERS,
            })
    except requests.RequestException as e:
        logging.warning(f'Failed to proxy favicon from {url}: {e}')
    return Response('Not found', status=404)


@favicon_bp.route('/favicon/<service_name>')
def proxy_favicon(service_name: str):
    from app import favicon_svc
    if not favicon_svc.get_internal_urls():
        from services import get_services
        get_services(favicon_svc)

    internal_url = favicon_svc.get_internal_urls().get(service_name)
    favicon_path = favicon_svc.get_cached_path(service_name)

    if not internal_url or not favicon_path:
        return Response('Not found', status=404)

    fetch_path = favicon_path.split('?')[0]

    # Try original URL first (static files at root)
    resp = _proxy_response(f'{internal_url.rstrip("/")}{fetch_path}')
    if resp.status_code == 200:
        return resp

    # Fall back to redirect-resolved URL (SPA with /web/ prefix etc.)
    try:
        resolved = requests.head(
            internal_url, timeout=2, allow_redirects=True,
            headers={'User-Agent': _USER_AGENT},
        )
        base = resolved.url.rstrip('/')
    except requests.RequestException:
        base = internal_url.rstrip('/')

    return _proxy_response(f'{base}/{fetch_path.lstrip("/")}')


@favicon_bp.route('/favicon-url')
def proxy_favicon_url():
    target_url = request.args.get('url', '')
    favicon_path = request.args.get('path', '/favicon.ico')

    if not target_url:
        return Response('Missing url parameter', status=400)

    if favicon_path.startswith('http://') or favicon_path.startswith('https://'):
        full_url = favicon_path
    else:
        base = target_url.rstrip('/')
        fav = favicon_path.lstrip('/')
        full_url = f'{base}/{fav}'

    return _proxy_response(full_url, verify=False)
