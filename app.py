import os
import logging
from flask import Flask
from config import PORT, TRAEFIK_API_URL
from favicon import FaviconService

favicon_svc = FaviconService()


def create_app() -> Flask:
    app = Flask(__name__)
    from routes import register_blueprints
    register_blueprints(app)
    return app


if __name__ == '__main__':
    logging.basicConfig(level=os.environ.get('LOG_LEVEL', 'INFO').upper())
    logging.info(f'Traefik API URL: {TRAEFIK_API_URL}')
    logging.info(f'Portal port: {PORT}')

    from services import get_services
    services, error = get_services(favicon_svc)
    if error:
        logging.warning(f'Could not fetch initial data: {error}')
    else:
        enabled = sum(1 for s in services if s['status'] == 'enabled')
        logging.info(f'Discovered {len(services)} services ({enabled} enabled):')
        for svc in services:
            urls_str = ', '.join(svc['urls']) if svc['urls'] else '(no URL)'
            logging.info(f'  [{svc["status"]}] {svc["name"]} -> {urls_str}')

    app = create_app()
    app.run(host='0.0.0.0', port=PORT)
