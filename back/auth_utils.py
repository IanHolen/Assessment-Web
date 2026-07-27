"""
Authentication utilities and decorators for the crop recommendation API.
"""

from functools import wraps
from flask import request, jsonify, current_app
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)

def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_username(username: str) -> bool:
    """Validate username format."""
    if len(username) < 3 or len(username) > 50:
        return False
    # Allow alphanumeric, underscore, hyphen
    pattern = r'^[a-zA-Z0-9_-]+$'
    return re.match(pattern, username) is not None

def validate_password(password: str) -> bool:
    """Validate password strength."""
    if len(password) < 6:
        return False
    return True

def get_client_info(request):
    """Extract client IP and user agent from request."""
    # X-Forwarded-For puede venir como lista "ip1, ip2, ..." (proxies/Render);
    # tomar solo la primera IP (la real del cliente).
    xff = request.environ.get('HTTP_X_FORWARDED_FOR', '')
    ip_address = xff.split(',')[0].strip() if xff else request.remote_addr
    user_agent = request.headers.get('User-Agent', '')[:500]  # Limit length
    return ip_address, user_agent

def require_auth(f):
    """Decorator to require authentication for endpoints."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({
                'error': 'Authorization header required',
                'timestamp': datetime.now().isoformat()
            }), 401
        
        if not auth_header.startswith('Bearer '):
            return jsonify({
                'error': 'Invalid authorization header format',
                'timestamp': datetime.now().isoformat()
            }), 401
        
        token = auth_header.split(' ')[1]
        
        # Verify JWT token
        jwt_manager = current_app.config['JWT_MANAGER']
        payload = jwt_manager.verify_token(token)
        
        if not payload:
            return jsonify({
                'error': 'Invalid or expired token',
                'timestamp': datetime.now().isoformat()
            }), 401
        
        # Validate session
        auth_db = current_app.config['AUTH_DB']
        session_data = auth_db.validate_session(payload.get('session_token'))
        
        if not session_data:
            return jsonify({
                'error': 'Invalid session',
                'timestamp': datetime.now().isoformat()
            }), 401
        
        # Add user data to request context
        request.current_user = {
            'id': payload['user_id'],
            'username': payload['username'],
            'email': payload.get('email'),
            'session_id': session_data['id'],
            'session_token': payload['session_token']
        }
        
        return f(*args, **kwargs)
    
    return decorated_function

def require_auth_optional(f):
    """Decorator for optional authentication (user data available if authenticated)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        request.current_user = None
        
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            
            # Verify JWT token
            jwt_manager = current_app.config['JWT_MANAGER']
            payload = jwt_manager.verify_token(token)
            
            if payload:
                # Validate session
                auth_db = current_app.config['AUTH_DB']
                session_data = auth_db.validate_session(payload.get('session_token'))
                
                if session_data:
                    request.current_user = {
                        'id': payload['user_id'],
                        'username': payload['username'],
                        'email': payload.get('email'),
                        'session_id': session_data['id'],
                        'session_token': payload['session_token']
                    }
        
        return f(*args, **kwargs)
    
    return decorated_function

def log_auth_activity(auth_db, user_id: str, session_id: str, activity_type: str, 
                     details: dict = None, request_obj=None):
    """Log authentication-related activity."""
    if request_obj is None:
        request_obj = request
    
    ip_address, user_agent = get_client_info(request_obj)
    
    activity_details = details or {}
    activity_details.update({
        'endpoint': request_obj.endpoint,
        'method': request_obj.method,
        'timestamp': datetime.now().isoformat()
    })
    
    try:
        auth_db.log_activity(
            user_id=user_id,
            session_id=session_id,
            activity_type=activity_type,
            details=activity_details,
            ip_address=ip_address,
            user_agent=user_agent
        )
    except Exception as e:
        logger.error(f"Error logging activity: {e}")

def create_error_response(message: str, details: str = None, status_code: int = 400):
    """Create standardized error response."""
    response = {
        'error': message,
        'timestamp': datetime.now().isoformat()
    }
    
    if details:
        response['details'] = details
    
    return jsonify(response), status_code

def create_success_response(data: dict, status_code: int = 200):
    """Create standardized success response."""
    response = data.copy()
    response['timestamp'] = datetime.now().isoformat()
    
    return jsonify(response), status_code

def verify_jwt_token(token: str):
    """Verify JWT token and return user data."""
    try:
        jwt_manager = current_app.config.get('JWT_MANAGER')
        if not jwt_manager:
            logger.error("JWT_MANAGER not found in app config")
            return None
        
        payload = jwt_manager.verify_token(token)
        if not payload:
            return None
        
        # Validate session if needed
        auth_db = current_app.config.get('AUTH_DB')
        if auth_db:
            session_data = auth_db.validate_session(payload.get('session_token'))
            if not session_data:
                return None
        
        return {
            'user_id': payload.get('user_id'),
            'username': payload.get('username'),
            'email': payload.get('email'),
            'session_token': payload.get('session_token')
        }
    except Exception as e:
        logger.error(f"Error verifying JWT token: {e}")
        return None