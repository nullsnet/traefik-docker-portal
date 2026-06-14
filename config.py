import os

PORT = int(os.environ.get('PORTAL_PORT', 5001))
TRAEFIK_API_URL = os.environ.get('TRAEFIK_API_URL', 'http://traefik:8080')
DOMAIN_SUFFIX = os.environ.get('DOMAIN_SUFFIX', '')
PAGE_TITLE = os.environ.get('PAGE_TITLE', 'Traefik Service Portal')
PAGE_HEADING = os.environ.get('PAGE_HEADING', 'Service Portal 🚀')
LINK_TARGET = os.environ.get('LINK_TARGET', '_self')
STATIC_SERVICES_FILE = os.environ.get('STATIC_SERVICES_FILE', '/etc/services.json')

INTERNAL_PROVIDERS = {'internal'}
INTERNAL_SERVICE_PREFIXES = ('api@', 'dashboard@')
PROVIDER_ICONS = {'docker': '🐳', 'file': '📄'}
DEFAULT_PROVIDER_ICON = '🐋'
