import os
import json
import logging
import requests
from config import (
    TRAEFIK_API_URL, INTERNAL_PROVIDERS, INTERNAL_SERVICE_PREFIXES,
    PROVIDER_ICONS, DEFAULT_PROVIDER_ICON, DOMAIN_SUFFIX, STATIC_SERVICES_FILE,
)
from favicon import FaviconService

logger = logging.getLogger(__name__)


class TraefikClient:
    def __init__(self, base_url: str = TRAEFIK_API_URL, timeout: int = 5):
        self.base_url = base_url
        self.timeout = timeout

    def fetch_routers(self) -> list[dict]:
        resp = requests.get(f'{self.base_url}/api/http/routers', timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def fetch_services(self) -> list[dict]:
        resp = requests.get(f'{self.base_url}/api/http/services', timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()


def extract_hosts_from_rule(rule: str) -> list[str]:
    import re
    return re.findall(r'Host\(`([^`]+)`\)', rule)


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


def is_internal_router(data: dict) -> bool:
    if data.get('provider', '') in INTERNAL_PROVIDERS:
        return True
    service = data.get('service', '')
    for prefix in INTERNAL_SERVICE_PREFIXES:
        if service.startswith(prefix):
            return True
    return False


def get_services(favicon_svc: FaviconService) -> tuple[list[dict], str | None]:
    client = TraefikClient()
    try:
        router_data = client.fetch_routers()
        services_data = client.fetch_services()
    except requests.RequestException as e:
        logger.error(f'Failed to fetch from Traefik API: {e}')
        return [], f'Could not connect to Traefik API: {e}'

    internal_urls: dict[str, str] = {}
    for svc in services_data:
        lb = svc.get('loadBalancer', {})
        servers = lb.get('servers', [])
        if servers:
            name = svc['name']
            internal_urls[name] = servers[0]['url']
            if '@' in name:
                base_name = name.split('@')[0]
                internal_urls[base_name] = servers[0]['url']

    favicon_svc.set_internal_urls(internal_urls)

    services_map: dict[str, dict] = {}
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

    favicon_results = favicon_svc.fetch_for_services(list(services_map.keys()))
    for svc_name, path in favicon_results.items():
        if path and svc_name in services_map:
            services_map[svc_name]['favicon_path'] = path

    result = [s for s in services_map.values() if s['urls']]
    result.sort(key=lambda x: x['name'])
    return result, None


def get_static_services(favicon_svc: FaviconService) -> list[dict]:
    if not os.path.isfile(STATIC_SERVICES_FILE):
        return []
    try:
        with open(STATIC_SERVICES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, list):
            logger.warning('Static services file is not a JSON array')
            return []
        result = []
        for section in data:
            title = section.get('title', '')
            services = section.get('services', [])
            if not title or not services:
                continue
            filtered = []
            for item in services:
                name = item.get('name', '')
                url = item.get('url', '')
                favicon = item.get('favicon', None)
                if name and url:
                    if not favicon:
                        detected = favicon_svc.fetch_for_external_url(url)
                        if detected:
                            favicon = detected
                    filtered.append({'name': name, 'url': url, 'favicon': favicon})
            if filtered:
                result.append({'title': title, 'services': filtered})
        return result
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f'Failed to read static services file: {e}')
        return []
