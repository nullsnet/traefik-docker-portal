import logging
from flask import Blueprint, request, Response
import requests
from favicon import _resolve_url, _resolve_redirects

favicon_bp = Blueprint('favicon', __name__)
_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
_TIMEOUT = 2
_CACHE_HEADERS = {
    'Cache-Control': 'public, max-age=86400',
}


def _proxy_response(url: str, verify=True) -> Response:
    try:
        resp = requests.get(url, timeout=_TIMEOUT, headers={'User-Agent': _USER_AGENT}, verify=verify)
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
    resp = _proxy_response(_resolve_url(internal_url, fetch_path))
    if resp.status_code == 200:
        return resp

    # Fall back to redirect-resolved URL (SPA with /web/ prefix etc.)
    base = _resolve_redirects(internal_url, _TIMEOUT, True)
    return _proxy_response(_resolve_url(base, fetch_path))


@favicon_bp.route('/favicon-url')
def proxy_favicon_url():
    target_url = request.args.get('url', '')
    favicon_path = request.args.get('path', '/favicon.ico')

    if not target_url:
        return Response('Missing url parameter', status=400)

    return _proxy_response(_resolve_url(target_url, favicon_path), verify=False)
