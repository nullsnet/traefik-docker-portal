import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

FAVICON_PATTERN = re.compile(
    r'<link[^>]*rel=(?:\"|\'|)(?:icon|shortcut\s*icon)[^>]*href=(?:\"|\'|)([^\"\'\s>]+)',
    re.IGNORECASE,
)


class FaviconService:
    def __init__(self, timeout=5, max_workers=8):
        self.timeout = timeout
        self.max_workers = max_workers
        self._internal_urls: dict[str, str] = {}
        self._favicon_paths: dict[str, str | None] = {}

    def set_internal_urls(self, urls: dict[str, str]) -> None:
        self._internal_urls = urls

    def get_internal_urls(self) -> dict[str, str]:
        return self._internal_urls

    def fetch_for_service(self, service_name: str) -> str | None:
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

    def _detect_from_html(self, base_url: str, verify=True) -> str | None:
        try:
            resp = requests.get(
                base_url, timeout=self.timeout,
                headers={'User-Agent': 'Mozilla/5.0'},
                verify=verify,
            )
            if resp.status_code == 200:
                match = FAVICON_PATTERN.search(resp.text)
                if match:
                    path = match.group(1) or match.group(2)
                    if path.startswith('http://') or path.startswith('https://'):
                        return path
                    path = '/' + path.lstrip('./')
                    fav_resp = requests.get(
                        f'{base_url}{path}', timeout=self.timeout,
                        headers={'User-Agent': 'Mozilla/5.0'},
                        verify=verify,
                    )
                    if fav_resp.status_code == 200 and len(fav_resp.content) > 0:
                        return path
                    alt_path = '/web' + path
                    alt_resp = requests.get(
                        f'{base_url}{alt_path}', timeout=self.timeout,
                        headers={'User-Agent': 'Mozilla/5.0'},
                        verify=verify,
                    )
                    if alt_resp.status_code == 200 and len(alt_resp.content) > 0:
                        return alt_path
        except requests.RequestException:
            pass

        try:
            favicon_resp = requests.get(
                f'{base_url}/favicon.ico', timeout=self.timeout,
                headers={'User-Agent': 'Mozilla/5.0'},
                verify=verify,
            )
            if favicon_resp.status_code == 200 and len(favicon_resp.content) > 0:
                return '/favicon.ico'
        except requests.RequestException:
            pass

        return None
