import os
import re
from typing import Optional
import docker
import logging
from flask import Flask, render_template

PORT = int(os.environ.get('PORTAL_PORT', 5001))
DOMAIN_SUFFIX = os.environ.get('DOMAIN_SUFFIX', 'example.com')
PAGE_TITLE = os.environ.get('PAGE_TITLE', 'Docker Container Portal')
PAGE_HEADING = os.environ.get('PAGE_HEADING', 'Container Service Portal 🚀')

logging.basicConfig(level=os.environ.get('LOG_LEVEL', 'INFO').upper())
app = Flask(__name__)

try:
    client = docker.from_env()
    client.ping()
    logging.info("Successfully connected to Docker daemon.")
except docker.errors.DockerException:
    client = None
    logging.error(
        "Could not connect to Docker daemon. Is it running and is the socket accessible?")


def extract_hostname_from_rule(rule: str) -> str | None:
    match = re.search(r'Host\(`([^`]+)`\)', rule)
    return match.group(1) if match else None


def get_services() -> tuple[list[dict[str, str]], str | None]:
    services: list[dict[str, str]] = []
    error_message: Optional[str] = None

    if not client:
        return [], "Docker daemon is not available."

    try:
        for container in client.containers.list():
            hostname: Optional[str] = None

            # Traefik v1 の 'traefik.host' ラベル
            if 'traefik.host' in container.labels:
                hostname = container.labels.get('traefik.host')
            # Traefik v2+ のルーティングルール
            else:
                for key, value in container.labels.items():
                    if key.startswith('traefik.http.routers.') and key.endswith('.rule'):
                        hostname = extract_hostname_from_rule(value)
                        if hostname:
                            break

            if hostname:
                url = f"https://{hostname}" if '.' in hostname else f"https://{hostname}.{DOMAIN_SUFFIX}"
                service_name = container.labels.get(
                    'com.docker.compose.service', container.name)
                services.append({'name': service_name, 'url': url})

    except docker.errors.DockerException as e:
        error_message = f"An error occurred while communicating with Docker: {e}"
        logging.error(error_message)

    return sorted(services, key=lambda x: x['name']), error_message


@app.route('/')
def index():
    services, error = get_services()
    return render_template('index.html', title=PAGE_TITLE, heading=PAGE_HEADING, services=services, domain=DOMAIN_SUFFIX, error=error)


if __name__ == '__main__':
    initial_services, err = get_services()
    if err:
        logging.warning(f"Could not fetch initial services: {err}")
    elif initial_services:
        logging.info("Discovered Services on Startup:")
        for service in initial_services:
            logging.info(f" - {service['name']} -> {service['url']}")
    else:
        logging.info("No services with 'traefik' labels found on startup.")

    app.run(host='0.0.0.0', port=PORT)
