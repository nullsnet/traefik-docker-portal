from flask import Blueprint, jsonify
from services import get_services, get_static_services
from app import favicon_svc

api_bp = Blueprint('api', __name__)


@api_bp.route('/api/services')
def api_services():
    services_list, error = get_services(favicon_svc)
    if error:
        return jsonify({'error': error}), 500
    return jsonify(services_list)


@api_bp.route('/api/static-services')
def api_static_services():
    return jsonify(get_static_services(favicon_svc))
