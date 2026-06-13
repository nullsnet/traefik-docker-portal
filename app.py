import os
import re
import logging
import json
import requests
from flask import Flask, render_template, jsonify, make_response

PORT = int(os.environ.get('PORTAL_PORT', 5001))
TRAEFIK_API_URL = os.environ.get('TRAEFIK_API_URL', 'http://traefik:8080')
DOMAIN_SUFFIX = os.environ.get('DOMAIN_SUFFIX', '')
PAGE_TITLE = os.environ.get('PAGE_TITLE', 'Traefik Service Portal')
PAGE_HEADING = os.environ.get('PAGE_HEADING', 'Service Portal 🚀')
LINK_TARGET = os.environ.get('LINK_TARGET', '_self')

logging.basicConfig(level=os.environ.get('LOG_LEVEL', 'INFO').upper())
app = Flask(__name__)


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


def fetch_favicon_from_url(base_url: str) -> str | None:
    """Fetch HTML from internal URL and extract favicon path, then return public URL."""
    try:
        resp = requests.get(base_url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        if resp.status_code != 200:
            return None
        match = FAVICON_PATTERN.search(resp.text)
        if match:
            path = match.group(1)
            # Return just the path - template will construct full URL
            return path
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
    # Router service names are like "authelia" but services API has "authelia@docker"
    internal_urls = {}
    for svc in services_data:
        lb = svc.get('loadBalancer', {})
        servers = lb.get('servers', [])
        if servers:
            name = svc['name']
            # Store with @docker suffix
            internal_urls[name] = servers[0]['url']
            # Also store without suffix for matching
            if '@' in name:
                base_name = name.split('@')[0]
                internal_urls[base_name] = servers[0]['url']

    services_map = {}
    for data in router_data:
        if is_internal_router(data):
            continue

        hosts = extract_hosts_from_rule(data.get('rule', ''))
        urls = build_urls(hosts)
        service_name = data.get('service', 'N/A')

        if service_name not in services_map:
            services_map[service_name] = {
                'name': service_name,
                'urls': urls,
                'status': data.get('status', 'unknown'),
                'provider': data.get('provider', 'N/A'),
                'favicon_path': None,
            }
        else:
            existing = services_map[service_name]
            for u in urls:
                if u not in existing['urls']:
                    existing['urls'].append(u)

    # Fetch favicons from internal URLs
    for svc_name, svc_info in services_map.items():
        internal_url = internal_urls.get(svc_name)
        if internal_url:
            favicon_path = fetch_favicon_from_url(internal_url)
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
