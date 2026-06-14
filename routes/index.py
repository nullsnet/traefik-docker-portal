from flask import Blueprint, render_template
from config import PAGE_TITLE, PAGE_HEADING, LINK_TARGET

index_bp = Blueprint('index', __name__)


@index_bp.route('/')
def index():
    from services import get_services, get_static_services
    from app import favicon_svc

    services_list, error = get_services(favicon_svc)
    static_services = get_static_services(favicon_svc)

    return render_template(
        'index.html',
        title=PAGE_TITLE,
        heading=PAGE_HEADING,
        routers=services_list,
        error=error,
        link_target=LINK_TARGET,
        static_services=static_services,
    )


@index_bp.route('/static/manifest.json')
def manifest():
    from flask import make_response
    resp = make_response(render_template('manifest_body.json', title=PAGE_TITLE, heading=PAGE_HEADING))
    resp.mimetype = 'application/json'
    return resp
