import os
import re
import logging
import json
import requests
from flask import Flask, render_template, jsonify, make_response, request, Response

PORT = int(os.environ.get('PORTAL_PORT', 5001))
TRAEFIK_API_URL = os.environ.get('TRAEFIK_API_URL', 'http://traefik:8080')
DOMAIN_SUFFIX = os.environ.get('DOMAIN_SUFFIX', '')
PAGE_TITLE = os.environ.get('PAGE_TITLE', 'Traefik Service Portal')
PAGE_HEADING = os.environ.get('PAGE_HEADING', 'Service Portal 🚀')
LINK_TARGET = os.environ.get('LINK_TARGET', '_self')

logging.basicConfig(level=os.environ.get('LOG_LEVEL', 'INFO').upper())
app = Flask(__name__)

# Global cache for internal URLs and favicon paths
_internal_urls: dict[str, str] = {}
_favicon_paths: dict[str, str | None] = {}


@app.route('/static/manifest.json')
def manifest():
    resp = make_response(render_template('manifest_body.json', title=PAGE_TITLE, heading=PAGE_HEADING))
    resp.mimetype = 'application/json'
    return resp


def extract_hosts_from_rule(rule: str) -> list[str]:
    hosts = re.findall(r'Host\(`([^`]+)`\)', rule)
    return hosts


def build_urls(hosts: list[str]) -> list[str]:
    urls = []
    for host in hosts:
        if host.startswith('.'):
            continue
        if DOMAIN_SUFFIX and not host.startswith('localhost'):
            suffix = f'.{DOMAIN_SUFFIX}'
            if not host.endswith(suffix):
                first_dot = host.find('.')
                if first_dot > 0:
                    host = host[:first_dot] + suffix
        scheme = 'https' if '.' in host or host.startswith('localhost') else 'http'
        urls.append(f'{scheme}://{host}')
    return urls


INTERNAL_PROVIDERS = {'internal'}
INTERNAL_SERVICE_PREFIXES = ('api@', 'dashboard@')
FAVICON_PATTERN = re.compile(
    r'<link[^>]*rel=(?:\"|\'|)(?:icon|shortcut\s*icon)[^>]*href=(?:\"|\'|)([^\"\'\s>]+)',
    re.IGNORECASE,
)
PROVIDER_ICONS = {'docker': '🐳', 'file': '📄'}
DEFAULT_PROVIDER_ICON = '🐋'


def fetch_favicon_from_url(base_url: str) -> str | None:
    """Fetch HTML from internal URL and extract favicon path, then return public URL."""
    try:
        resp = requests.get(base_url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        if resp.status_code == 200:
            match = FAVICON_PATTERN.search(resp.text)
            if match:
                path = match.group(1)
                # Normalize path: remove leading ./ and ensure it starts with /
                path = '/' + path.lstrip('./')
                # Verify the favicon exists at this path
                fav_resp = requests.get(f'{base_url}{path}', timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
                if fav_resp.status_code == 200 and len(fav_resp.content) > 0:
                    return path
                # Some services (e.g., jellyfin) serve static files under /web/
                alt_path = '/web' + path
                alt_resp = requests.get(f'{base_url}{alt_path}', timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
                if alt_resp.status_code == 200 and len(alt_resp.content) > 0:
                    return alt_path
    except requests.RequestException:
        pass
    # Fallback: try /favicon.ico directly
    try:
        favicon_resp = requests.get(f'{base_url}/favicon.ico', timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        if favicon_resp.status_code == 200 and len(favicon_resp.content) > 0:
            return '/favicon.ico'
    except requests.RequestException:
        pass
    return None


def is_internal_router(data: dict) -> bool:
    if data.get('provider', '') in INTERNAL_PROVIDERS:
        return True
    service = data.get('service', '')
    for prefix in INTERNAL_SERVICE_PREFIXES:
        if service.startswith(prefix):
            return True
    return False


def get_services():
    global _internal_urls, _favicon_paths
    try:
        routers_resp = requests.get(f'{TRAEFIK_API_URL}/api/http/routers', timeout=5)
        routers_resp.raise_for_status()
        router_data = routers_resp.json()
        services_resp = requests.get(f'{TRAEFIK_API_URL}/api/http/services', timeout=5)
        services_resp.raise_for_status()
        services_data = services_resp.json()
    except requests.RequestException as e:
        logging.error(f'Failed to fetch from Traefik API: {e}')
        return [], f'Could not connect to Traefik API: {e}'

    # Build service name -> internal URL mapping
    _internal_urls.clear()
    for svc in services_data:
        lb = svc.get('loadBalancer', {})
        servers = lb.get('servers', [])
        if servers:
            name = svc['name']
            _internal_urls[name] = servers[0]['url']
            if '@' in name:
                base_name = name.split('@')[0]
                _internal_urls[base_name] = servers[0]['url']

    services_map = {}
    for data in router_data:
        if is_internal_router(data):
            continue

        hosts = extract_hosts_from_rule(data.get('rule', ''))
        urls = build_urls(hosts)
        service_name = data.get('service', 'N/A')

        if service_name not in services_map:
            provider = data.get('provider', 'N/A')
            services_map[service_name] = {
                'name': service_name,
                'urls': urls,
                'status': data.get('status', 'unknown'),
                'provider': provider,
                'provider_icon': PROVIDER_ICONS.get(provider.split('@')[0], DEFAULT_PROVIDER_ICON),
                'favicon_path': None,
            }
        else:
            existing = services_map[service_name]
            for u in urls:
                if u not in existing['urls']:
                    existing['urls'].append(u)

    # Fetch favicons from internal URLs
    _favicon_paths.clear()
    for svc_name, svc_info in services_map.items():
        internal_url = _internal_urls.get(svc_name)
        if internal_url:
            favicon_path = fetch_favicon_from_url(internal_url)
            _favicon_paths[svc_name] = favicon_path
            if favicon_path:
                svc_info['favicon_path'] = favicon_path

    result = [s for s in services_map.values() if s['urls']]
    result.sort(key=lambda x: x['name'])
    return result, None


@app.route('/')
def index():
    services_list, error = get_services()

    return render_template(
        'index.html',
        title=PAGE_TITLE,
        heading=PAGE_HEADING,
        routers=services_list,
        error=error,
        link_target=LINK_TARGET,
    )


@app.route('/api/services')
def api_services():
    services_list, error = get_services()
    if error:
        return jsonify({'error': error}), 500
    return jsonify(services_list)


@app.route('/favicon/<service_name>')
def proxy_favicon(service_name: str):
    """Proxy favicon from internal URL to bypass Authelia."""
    # Refresh cache if empty
    if not _internal_urls:
        get_services()

    internal_url = _internal_urls.get(service_name)
    favicon_path = _favicon_paths.get(service_name)

    if not internal_url or not favicon_path:
        return Response('Not found', status=404)

    # Clean up favicon path (remove query params for fetch, add back for URL)
    fetch_path = favicon_path.split('?')[0]
    try:
        resp = requests.get(f'{internal_url}/{fetch_path.lstrip("/")}', timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        if resp.status_code == 200 and len(resp.content) > 0:
            return Response(resp.content, status=200, headers={
                'Content-Type': resp.headers.get('Content-Type', 'image/png'),
                'Cache-Control': 'public, max-age=86400',
            })
    except requests.RequestException as e:
        logging.warning(f'Failed to proxy favicon for {service_name}: {e}')
    return Response('Not found', status=404)


if __name__ == '__main__':
    logging.info(f'Traefik API URL: {TRAEFIK_API_URL}')
    logging.info(f'Portal port: {PORT}')

    services, error = get_services()
    if error:
        logging.warning(f'Could not fetch initial data: {error}')
    else:
        enabled = sum(1 for s in services if s['status'] == 'enabled')
        logging.info(f'Discovered {len(services)} services ({enabled} enabled):')
        for svc in services:
            urls_str = ', '.join(svc['urls']) if svc['urls'] else '(no URL)'
            logging.info(f'  [{svc["status"]}] {svc["name"]} -> {urls_str}')

    app.run(host='0.0.0.0', port=PORT)
