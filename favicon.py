import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

_LINK_TAG = re.compile(
    r'<link([^>]*)>',
    re.IGNORECASE,
)
_REL_ICON = re.compile(
    r'''rel\s*=\s*["'](icon|shortcut\s+icon)["']''',
    re.IGNORECASE,
)
_HREF_ATTR = re.compile(
    r'''href\s*=\s*["']([^"'>]+)["']''',
    re.IGNORECASE,
)

def _parse_link_tags(html: str) -> list[dict]:
    results = []
    for tag_match in _LINK_TAG.finditer(html):
        attrs = tag_match.group(1)
        if not _REL_ICON.search(attrs):
            continue
        href_m = _HREF_ATTR.search(attrs)
        results.append({
            'href': href_m.group(1) if href_m else None,
        })
    return results


def _normalize_path(path: str) -> str:
    if path.startswith('http://') or path.startswith('https://'):
        return path
    return '/' + path.lstrip('./')


class FaviconService:
    def __init__(self, timeout=5, max_workers=8):
        self.timeout = timeout
        self.max_workers = max_workers
        self._internal_urls: dict[str, str] = {}
        self._favicon_paths: dict[str, str | None] = {}
        self._overrides: dict[str, str] = {}
        self._background_executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix='favicon-bg')
        self._lock = threading.Lock()

    def set_overrides(self, overrides: dict[str, str]) -> None:
        self._overrides = overrides

    def set_internal_urls(self, urls: dict[str, str]) -> None:
        self._internal_urls = urls

    def get_internal_urls(self) -> dict[str, str]:
        return self._internal_urls

    def fetch_for_service(self, service_name: str) -> str | None:
        # Check manual override first
        if service_name in self._overrides:
            path = self._overrides[service_name]
            internal_url = self._internal_urls.get(service_name)
            if internal_url and self._try_path(internal_url, path, True):
                return path
            return None
        internal_url = self._internal_urls.get(service_name)
        if not internal_url:
            return None
        return self._detect_from_html(internal_url)

    def fetch_for_services(self, service_names: list[str]) -> dict[str, str | None]:
        results: dict[str, str | None] = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.fetch_for_service, name): name
                for name in service_names
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception:
                    results[name] = None
        self._favicon_paths = results
        return results

    def fetch_for_external_url(self, base_url: str) -> str | None:
        return self._detect_from_html(base_url, verify=False)

    def get_cached_path(self, service_name: str) -> str | None:
        return self._favicon_paths.get(service_name)

    def fetch_for_services_async(self, service_names: list[str]) -> dict[str, str | None]:
        current_cache = dict(self._favicon_paths)

        def _background_fetch():
            results = {}
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self.fetch_for_service, name): name
                    for name in service_names
                }
                for future in as_completed(futures):
                    name = futures[future]
                    try:
                        results[name] = future.result()
                    except Exception:
                        results[name] = None
            with self._lock:
                self._favicon_paths.update(results)

        self._background_executor.submit(_background_fetch)
        return current_cache

    def _try_path(self, base_url: str, path: str, verify: bool) -> bool:
        try:
            if path.startswith('http://') or path.startswith('https://'):
                url = path
            else:
                url = f'{base_url.rstrip("/")}{path}'
            resp = requests.get(
                url, timeout=self.timeout,
                headers={'User-Agent': 'Mozilla/5.0'},
                verify=verify,
            )
            if resp.status_code != 200 or len(resp.content) == 0:
                return False
            ct = resp.headers.get('Content-Type', '')
            # Reject HTML/text responses (SPA catch-all), accept everything else
            return not ('text/html' in ct or 'text/plain' in ct)
        except requests.RequestException:
            return False

    def _detect_from_html(self, base_url: str, verify=True) -> str | None:
        original_url = base_url.rstrip('/')
        resolved_url = original_url

        html_resp = None
        try:
            html_resp = requests.get(
                base_url, timeout=self.timeout, allow_redirects=True,
                headers={'User-Agent': 'Mozilla/5.0'},
                verify=verify,
            )
        except requests.RequestException:
            pass

        if html_resp and html_resp.status_code == 200:
            resolved_url = html_resp.url.rstrip('/')

            links = _parse_link_tags(html_resp.text)
            for link in links:
                if not link['href']:
                    continue
                href = link['href']
                path = _normalize_path(href)
                use_url = original_url if href.startswith('/') else resolved_url
                if self._try_path(use_url, path, verify):
                    return path

        # Fallback: always try against original URL (static files at root)
        for fallback in ['/favicon.ico', '/favicon.svg']:
            if self._try_path(original_url, fallback, verify):
                return fallback

        return None
