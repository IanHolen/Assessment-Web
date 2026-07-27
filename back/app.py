from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import os
import logging
import requests
from crop_inference import LocalInferenceClient
from auth_models import AuthDatabase, JWTManager
from auth_utils import (
    require_auth, require_auth_optional, validate_email, validate_username,
    validate_password, get_client_info, log_auth_activity,
    create_error_response, create_success_response
)
from prediction_log_models import PredictionLogDatabase

# Import blueprints
from dashboard_endpoints import dashboard_bp
from analytics_endpoints import analytics_bp
from chat_endpoints import chat_bp
from about_endpoints import about_bp
from prediction_log_endpoints import prediction_logs_bp

# Configure logging (stdout siempre; archivo opcional vía LOG_FILE)
_log_handlers = [logging.StreamHandler()]
_log_file = os.getenv('LOG_FILE')
if _log_file:
    try:
        os.makedirs(os.path.dirname(_log_file), exist_ok=True)
        _log_handlers.append(logging.FileHandler(_log_file))
    except Exception:
        pass
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=_log_handlers
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configure CORS. Orígenes por defecto + los que se agreguen vía env CORS_ORIGINS
# (lista separada por comas, p.ej. la URL del frontend desplegado).
_default_origins = [
    'https://agriai.local:420',
    'https://10.49.12.46:420',
    'https://172.28.69.47',
    'http://172.28.69.200:8000',
    'http://172.28.69.128:8000',
    'http://localhost:5173',
    'http://localhost:8080',
]
_env_origins = [o.strip() for o in os.getenv('CORS_ORIGINS', '').split(',') if o.strip()]
cors_config = {
    'origins': _default_origins + _env_origins,
    'supports_credentials': True,
    'methods': ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    'allow_headers': ['Content-Type', 'Authorization', 'X-Requested-With'],
    'expose_headers': ['Content-Length', 'X-JSON'],
    'max_age': 3600
}

CORS(app, **cors_config)

# Rate limiting
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["1000 per hour"]
)
limiter.init_app(app)

# Production Database Configuration - PostgreSQL
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '172.28.69.148'),
    'port': int(os.getenv('DB_PORT', '5432')),
    'user': os.getenv('DB_USER', 'cropapi'),
    'password': os.getenv('DB_PASSWORD', 'cropapi123'),
    'database': os.getenv('DB_NAME', 'crop_recommendations'),
    'connect_timeout': 10
}
# Aiven / Postgres gestionado exige SSL: DB_SSLMODE=require
if os.getenv('DB_SSLMODE'):
    DB_CONFIG['sslmode'] = os.getenv('DB_SSLMODE')

# JWT Secret - In production, use environment variable
app.config['JWT_SECRET'] = os.getenv('JWT_SECRET', 'your-super-secure-secret-key-change-in-production')

# Prediction logging configuration
app.config['ENABLE_PREDICTION_LOGGING'] = os.getenv('ENABLE_PREDICTION_LOGGING', 'true').lower() == 'true'
app.config['MAX_LOGS_PER_USER'] = int(os.getenv('MAX_LOGS_PER_USER', '10000'))
app.config['LOG_RETENTION_DAYS'] = int(os.getenv('LOG_RETENTION_DAYS', '365'))
app.config['ENABLE_LOG_COMPRESSION'] = os.getenv('ENABLE_LOG_COMPRESSION', 'true').lower() == 'true'
app.config['MAX_EXPORT_RECORDS'] = int(os.getenv('MAX_EXPORT_RECORDS', '5000'))
app.config['EXPORT_RATE_LIMIT'] = int(os.getenv('EXPORT_RATE_LIMIT', '5'))

# Initialize authentication components
auth_db = AuthDatabase(DB_CONFIG)
jwt_manager = JWTManager(app.config['JWT_SECRET'])
prediction_log_db = PredictionLogDatabase(DB_CONFIG)

# Store in app config for access in decorators
app.config['AUTH_DB'] = auth_db
app.config['JWT_MANAGER'] = jwt_manager
app.config['PREDICTION_LOG_DB'] = prediction_log_db
app.config['DB_CONFIG'] = DB_CONFIG

# Register blueprints
app.register_blueprint(dashboard_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(about_bp)
app.register_blueprint(prediction_logs_bp)


# Initialize local inference engine (in-process, numpy — sin servicio GPU externo)
try:
    engine = LocalInferenceClient()
    logger.info(f"Local inference engine ready. Models: {list(engine.models.keys())}")
except Exception as e:
    logger.error(f"Failed to initialize inference engine: {e}")
    raise

def test_db_connection():
    """Test database connection on startup with timeout."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("SELECT 'OK' as test;")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        logger.info(f"Database connection test result: {result[0]}")
        print("Connection with SQL has been established and properly tested")
        return True
    except psycopg2.OperationalError as e:
        logger.error(f"Database connection timeout: {e}")
        print(f"Database connection timeout: {e}")
        return False
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        print(f"Failed to connect to database: {e}")
        return False

def get_db_connection():
    """Get database connection with error handling and timeout."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.OperationalError as err:
        logger.error(f"Database connection timeout/error: {err}")
        return None
    except psycopg2.Error as err:
        logger.error(f"Database connection error: {err}")
        return None
    except Exception as e:
        logger.error(f"Unexpected database error: {e}")
        return None

def log_api_request(endpoint, method, status_code, response_time_ms, error_message=None):
    """Log API request to database."""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            user_agent = request.headers.get('User-Agent', '')[:500]  # Limit length
            client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
            
            cursor.execute("""
                INSERT INTO api_requests (endpoint, method, status_code, response_time_ms, 
                                        error_message, client_ip, user_agent)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (endpoint, method, status_code, response_time_ms, error_message, client_ip, user_agent))
            
            conn.commit()
            cursor.close()
            conn.close()
    except Exception as e:
        logger.error(f"Error logging API request: {e}")

def save_prediction(input_features, predicted_crop, confidence, alternatives, client_ip, user_id=None):
    """Save prediction to database with enhanced tracking."""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            
            # Save the prediction
            try:
                cursor.execute("""
                    INSERT INTO predictions (
                        nitrogen, phosphorus, potassium, temperature, humidity, ph, rainfall,
                        predicted_crop, confidence, alternatives, client_ip, user_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    input_features['N'], input_features['P'], input_features['K'],
                    input_features['temperature'], input_features['humidity'],
                    input_features['ph'], input_features['rainfall'],
                    predicted_crop, confidence, str(alternatives), client_ip, user_id
                ))
                prediction_id = cursor.fetchone()[0]
            except psycopg2.errors.UndefinedColumn:
                # Fallback to original structure if user_id column doesn't exist
                cursor.execute("""
                    INSERT INTO predictions (
                        nitrogen, phosphorus, potassium, temperature, humidity, ph, rainfall,
                        predicted_crop, confidence, alternatives, client_ip
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    input_features['N'], input_features['P'], input_features['K'],
                    input_features['temperature'], input_features['humidity'],
                    input_features['ph'], input_features['rainfall'],
                    predicted_crop, confidence, str(alternatives), client_ip
                ))
                prediction_id = cursor.fetchone()[0]
            
            # Update user activity if user is logged in
            if user_id:
                try:
                    cursor.execute("SELECT update_user_activity(%s, %s)", (user_id, datetime.now().date()))
                except Exception as e:
                    logger.warning(f"Failed to update user activity: {e}")
            
            # Create default prediction outcome as pending
            try:
                cursor.execute("""
                    INSERT INTO prediction_outcomes (prediction_id, outcome_status)
                    VALUES (%s, 'pending')
                """, (prediction_id,))
            except Exception as e:
                logger.warning(f"Failed to create prediction outcome: {e}")
            
            # Update geographic usage (default to Mexico if no country detected)
            try:
                # In a real implementation, you would use an IP geolocation service
                # For now, we'll default to Mexico since the app is primarily for LATAM
                cursor.execute("SELECT update_geographic_usage(%s, %s)", ('MEX', 'México'))
            except Exception as e:
                logger.warning(f"Failed to update geographic usage: {e}")
            
            conn.commit()
            cursor.close()
            conn.close()
            logger.info(f"Prediction saved: {predicted_crop} (confidence: {confidence:.4f}) for user: {user_id or 'anonymous'}")
    except Exception as e:
        logger.error(f"Error saving prediction: {e}")


@app.errorhandler(Exception)
def handle_exception(e):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {e}", exc_info=True)
    return jsonify({
        'error': 'Internal server error',
        'timestamp': datetime.now().isoformat()
    }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    start_time = datetime.now()
    
    try:
        # Check database connection
        conn = get_db_connection()
        db_status = "connected" if conn else "disconnected"
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM crops")
            crop_count = cursor.fetchone()[0]
            cursor.close()
            conn.close()
        else:
            crop_count = 0
        
        response = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': db_status,
            'models_loaded': len(engine.models),
            'available_models': list(engine.models.keys()),
            'supported_crops': crop_count,
            'server_ip': '172.28.69.96'
        }
        
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        log_api_request('/api/health', 'GET', 200, response_time)
        
        return jsonify(response), 200
        
    except Exception as e:
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        log_api_request('/api/health', 'GET', 500, response_time, str(e))
        
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/predict', methods=['POST'])
@require_auth_optional
def predict_crop():
    """Crop prediction endpoint."""
    start_time = datetime.now()
    
    try:
        # Validate request
        if not request.is_json:
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            log_api_request('/api/predict', 'POST', 400, response_time, "Request must be JSON")
            return jsonify({'error': 'Request must be JSON'}), 400
        
        data = request.get_json()
        if not data:
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            log_api_request('/api/predict', 'POST', 400, response_time, "No JSON data provided")
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Extract and validate features
        required_features = ['N', 'P', 'K', 'temperature', 'humidity', 'ph', 'rainfall']
        features = {}
        
        for feature in required_features:
            if feature not in data:
                response_time = (datetime.now() - start_time).total_seconds() * 1000
                log_api_request('/api/predict', 'POST', 400, response_time, f"Missing feature: {feature}")
                return jsonify({'error': f'Missing required feature: {feature}'}), 400
            
            try:
                features[feature] = float(data[feature])
            except (ValueError, TypeError):
                response_time = (datetime.now() - start_time).total_seconds() * 1000
                log_api_request('/api/predict', 'POST', 400, response_time, f"Invalid value for {feature}")
                return jsonify({'error': f'Invalid value for feature: {feature}'}), 400
        
        # Make prediction
        result = engine.predict(features)
        
        if not result['success']:
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            log_api_request('/api/predict', 'POST', 400, response_time, result['error'])
            return jsonify({'error': result['error']}), 400
        
        # Prepare response
        response = {
            'predicted_crop': result['predicted_crop'],
            'confidence': result['confidence'],
            'top_predictions': result['top_predictions'],
            'input_features': result['input_features'],
            'timestamp': datetime.now().isoformat(),
            'server_ip': '172.28.69.96'
        }
        
        if 'warnings' in result:
            response['warnings'] = result['warnings']
        
        # Save to database
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        alternatives = result['top_predictions']
        
        # Add user context if authenticated
        user_id = None
        session_id = None
        processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        if hasattr(request, 'current_user') and request.current_user:
            user_id = request.current_user['id']
            session_id = request.current_user.get('session_id')
            
            # Log API usage activity
            log_auth_activity(
                auth_db, 
                request.current_user['id'], 
                request.current_user['session_id'],
                'api_call',
                {'endpoint': '/api/predict', 'crop': result['predicted_crop'], 'confidence': result['confidence']}
            )
            
            # Save detailed prediction log for authenticated users
            if app.config.get('ENABLE_PREDICTION_LOGGING', True):
                try:
                    ip_address, user_agent = get_client_info(request)
                    log_data = {
                        'user_id': user_id,
                        'input_features': result['input_features'],
                        'predicted_crop': result['predicted_crop'],
                        'confidence': result['confidence'],
                        'top_predictions': result['top_predictions'],
                        'status': 'success',
                        'processing_time': processing_time,
                        'session_id': session_id,
                        'ip_address': ip_address,
                        'user_agent': user_agent
                    }
                    prediction_log_db.save_prediction_log(log_data)
                    
                    # Invalidate user dashboard cache for immediate updates
                    try:
                        from dashboard_endpoints import invalidate_user_dashboard_cache
                        invalidate_user_dashboard_cache(user_id)
                    except Exception as cache_error:
                        logger.warning(f"Failed to invalidate dashboard cache: {cache_error}")
                        
                except Exception as e:
                    logger.warning(f"Failed to save prediction log: {e}")
        
        save_prediction(
            result['input_features'],
            result['predicted_crop'],
            result['confidence'],
            alternatives,
            client_ip,
            user_id
        )
        
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        log_api_request('/api/predict', 'POST', 200, response_time)
        
        return jsonify(response), 200
        
    except Exception as e:
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        log_api_request('/api/predict', 'POST', 500, response_time, str(e))
        logger.error(f"Prediction error: {e}", exc_info=True)
        
        # Log failed prediction for authenticated users
        if hasattr(request, 'current_user') and request.current_user and app.config.get('ENABLE_PREDICTION_LOGGING', True):
            try:
                ip_address, user_agent = get_client_info(request)
                processing_time = int((datetime.now() - start_time).total_seconds() * 1000)
                data = request.get_json() if request.is_json else {}
                
                log_data = {
                    'user_id': request.current_user['id'],
                    'input_features': data,
                    'status': 'error',
                    'error_message': str(e),
                    'processing_time': processing_time,
                    'session_id': request.current_user.get('session_id'),
                    'ip_address': ip_address,
                    'user_agent': user_agent
                }
                prediction_log_db.save_prediction_log(log_data)
            except Exception as log_error:
                logger.warning(f"Failed to save error prediction log: {log_error}")
        
        return jsonify({
            'error': 'Internal server error',
            'details': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/crops', methods=['GET'])
def get_crops():
    """Get list of supported crops."""
    start_time = datetime.now()
    
    try:
        crops = list(engine.label_mapping.keys())
        
        response = {
            'crops': sorted(crops),
            'count': len(crops),
            'timestamp': datetime.now().isoformat(),
            'server_ip': '172.28.69.96'
        }
        
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        log_api_request('/api/crops', 'GET', 200, response_time)
        
        return jsonify(response), 200
        
    except Exception as e:
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        log_api_request('/api/crops', 'GET', 500, response_time, str(e))
        
        return jsonify({
            'error': 'Internal server error',
            'details': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/features', methods=['GET'])
def get_features():
    """Get information about required features."""
    start_time = datetime.now()
    
    try:
        features_info = []
        for feature in engine.feature_names:
            min_val, max_val = engine.feature_ranges[feature]
            features_info.append({
                'name': feature,
                'min_value': min_val,
                'max_value': max_val,
                'unit': get_feature_unit(feature),
                'description': get_feature_description(feature)
            })
        
        response = {
            'features': features_info,
            'count': len(features_info),
            'timestamp': datetime.now().isoformat(),
            'server_ip': '172.28.69.96'
        }
        
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        log_api_request('/api/features', 'GET', 200, response_time)
        
        return jsonify(response), 200
        
    except Exception as e:
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        log_api_request('/api/features', 'GET', 500, response_time, str(e))
        
        return jsonify({
            'error': 'Internal server error',
            'details': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get API usage statistics."""
    start_time = datetime.now()
    
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get prediction statistics
        cursor.execute("""
            SELECT 
                predicted_crop,
                COUNT(*) as count,
                AVG(confidence) as avg_confidence
            FROM predictions 
            WHERE created_at > NOW() - INTERVAL '24 hours'
            GROUP BY predicted_crop 
            ORDER BY count DESC
            LIMIT 10
        """)
        top_predictions = cursor.fetchall()
        
        # Get API usage statistics
        cursor.execute("""
            SELECT 
                endpoint,
                COUNT(*) as requests,
                AVG(response_time_ms) as avg_response_time,
                SUM(CASE WHEN status_code >= 400 THEN 1 ELSE 0 END) as errors
            FROM api_requests 
            WHERE created_at > NOW() - INTERVAL '24 hours'
            GROUP BY endpoint
        """)
        api_stats = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        response = {
            'top_predictions_24h': top_predictions,
            'api_usage_24h': api_stats,
            'timestamp': datetime.now().isoformat(),
            'server_ip': '172.28.69.96'
        }
        
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        log_api_request('/api/stats', 'GET', 200, response_time)
        
        return jsonify(response), 200
        
    except Exception as e:
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        log_api_request('/api/stats', 'GET', 500, response_time, str(e))
        
        return jsonify({
            'error': 'Internal server error',
            'details': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

def get_feature_unit(feature):
    """Get unit for feature."""
    units = {
        'N': 'kg/ha',
        'P': 'kg/ha',
        'K': 'kg/ha',
        'temperature': '°C',
        'humidity': '%',
        'ph': 'pH',
        'rainfall': 'mm/year'
    }
    return units.get(feature, '')

def get_feature_description(feature):
    """Get description for feature."""
    descriptions = {
        'N': 'Nitrogen content in soil',
        'P': 'Phosphorus content in soil',
        'K': 'Potassium content in soil',
        'temperature': 'Average temperature',
        'humidity': 'Relative humidity',
        'ph': 'Soil pH level',
        'rainfall': 'Annual rainfall'
    }
    return descriptions.get(feature, '')

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    log_api_request(request.path, request.method, 404, 0, "Endpoint not found")
    return jsonify({
        'error': 'Endpoint not found',
        'available_endpoints': [
            '/api/health', '/api/predict', '/api/crops', '/api/features', '/api/stats', '/api/chat',
            '/api/auth/signup', '/api/auth/login', '/api/auth/logout', '/api/auth/verify',
            '/api/auth/reset-password', '/api/auth/log-activity', '/api/auth/sessions/<user_id>',
            '/api/dashboard/metrics', '/api/dashboard/monthly-predictions', '/api/dashboard/crop-distribution',
            '/api/analytics/accuracy-trend', '/api/analytics/regional-distribution', 
            '/api/analytics/model-metrics', '/api/analytics/performance-metrics',
            '/api/about/metrics', '/api/about/cache/clear', '/api/about/metrics/update',
            '/api/chat', '/api/chat/conversations/<conversation_id>',
            '/api/prediction-logs', '/api/users/<user_id>/prediction-logs',
            '/api/users/<user_id>/prediction-statistics', '/api/users/<user_id>/prediction-logs/export'
        ],
        'timestamp': datetime.now().isoformat()
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    """Handle 405 errors."""
    log_api_request(request.path, request.method, 405, 0, "Method not allowed")
    return jsonify({
        'error': 'Method not allowed',
        'timestamp': datetime.now().isoformat()
    }), 405

# Authentication Endpoints

@app.route('/api/auth/signup', methods=['POST'])
@limiter.limit("5 per minute")
def auth_signup():
    """User registration endpoint."""
    start_time = datetime.now()
    
    try:
        logger.info(f"Signup request received from {request.remote_addr}")
        logger.info(f"Request content type: {request.content_type}")
        logger.info(f"Request is_json: {request.is_json}")
        
        if not request.is_json:
            logger.warning("Signup failed: Request is not JSON")
            return create_error_response("Request must be JSON", status_code=400)
        
        data = request.get_json()
        logger.info(f"Received signup data keys: {list(data.keys()) if data else 'None'}")
        
        # Validate required fields
        username = data.get('username', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        logger.info(f"Username: '{username}', Email: '{email}', Password length: {len(password) if password else 0}")
        
        if not username or not email or not password:
            logger.warning(f"Signup failed: Missing required fields - username: {bool(username)}, email: {bool(email)}, password: {bool(password)}")
            return create_error_response("Username, email, and password are required")
        
        # Validate input formats
        logger.info("Starting input validation...")
        if not validate_username(username):
            logger.warning(f"Signup failed: Invalid username format for '{username}'")
            return create_error_response("Invalid username format (3-50 characters, alphanumeric, underscore, hyphen only)")
        
        if not validate_email(email):
            logger.warning(f"Signup failed: Invalid email format for '{email}'")
            return create_error_response("Invalid email format")
        
        if not validate_password(password):
            logger.warning(f"Signup failed: Invalid password (length: {len(password)})")
            return create_error_response("Password must be at least 6 characters")
        
        logger.info("Input validation passed, creating user...")
        
        # Create user
        try:
            user_data = auth_db.create_user(username, email, password)
            logger.info(f"create_user returned: {user_data is not None}")
        except Exception as create_error:
            logger.error(f"Error in create_user: {create_error}")
            raise
        
        if not user_data:
            logger.warning(f"Signup failed: Username '{username}' or email '{email}' already exists")
            return create_error_response("Username or email already exists", status_code=400)
        
        # Create session and generate token
        logger.info("User created successfully, creating session...")
        ip_address, user_agent = get_client_info(request)
        logger.info(f"Client info - IP: {ip_address}, User-Agent: {user_agent[:50]}...")
        
        try:
            session_token = auth_db.create_session(user_data['id'], ip_address, user_agent)
            logger.info(f"create_session returned: {session_token is not None}")
        except Exception as session_error:
            logger.error(f"Error in create_session: {session_error}")
            raise
        
        if not session_token:
            logger.error("Failed to create session")
            return create_error_response("Failed to create session", status_code=500)
        
        # Generate JWT
        logger.info("Session created, generating JWT...")
        try:
            jwt_token = jwt_manager.generate_token(user_data, session_token)
            logger.info(f"JWT generated successfully: {jwt_token is not None}")
        except Exception as jwt_error:
            logger.error(f"Error generating JWT: {jwt_error}")
            raise
        
        # Log signup activity
        logger.info("Logging signup activity...")
        try:
            log_auth_activity(
                auth_db,
                user_data['id'],
                session_token,
                'signup',
                {'username': username, 'email': email}
            )
            logger.info("Signup activity logged successfully")
        except Exception as log_error:
            logger.warning(f"Failed to log signup activity: {log_error}")
        
        # Prepare response
        logger.info("Preparing response...")
        response_data = {
            'token': jwt_token,
            'user': {
                'id': user_data['id'],
                'username': user_data['username'],
                'email': user_data['email'],
                'lastLoginAt': user_data.get('last_login_at'),
                'sessionStartedAt': datetime.now().isoformat()
            }
        }
        
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        log_api_request('/api/auth/signup', 'POST', 201, response_time)
        
        logger.info("Signup completed successfully, returning 201 response")
        return create_success_response(response_data, status_code=201)
        
    except Exception as e:
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        log_api_request('/api/auth/signup', 'POST', 500, response_time, str(e))
        logger.error(f"Signup error: {e}", exc_info=True)
        return create_error_response("Internal server error", status_code=500)

@app.route('/api/auth/login', methods=['POST'])
@limiter.limit("5 per minute")
def auth_login():
    """User login endpoint."""
    start_time = datetime.now()
    
    try:
        if not request.is_json:
            return create_error_response("Request must be JSON", status_code=400)
        
        data = request.get_json()
        
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return create_error_response("Username and password are required")
        
        # Authenticate user
        user_data = auth_db.authenticate_user(username, password)
        
        if not user_data:
            # Log failed login attempt
            ip_address, user_agent = get_client_info(request)
            try:
                # Try to get user ID for failed login logging
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                    user_row = cursor.fetchone()
                    if user_row:
                        log_auth_activity(
                            auth_db,
                            user_row[0],
                            None,
                            'login_failed',
                            {'username': username, 'reason': 'invalid_credentials'}
                        )
                    cursor.close()
                    conn.close()
            except:
                pass
            
            return create_error_response("Invalid username or password", status_code=401)
        
        # Create session
        ip_address, user_agent = get_client_info(request)
        session_token = auth_db.create_session(user_data['id'], ip_address, user_agent)
        
        if not session_token:
            return create_error_response("Failed to create session", status_code=500)
        
        # Generate JWT
        jwt_token = jwt_manager.generate_token(user_data, session_token)
        
        # Log successful login
        log_auth_activity(
            auth_db,
            user_data['id'],
            session_token,
            'login',
            {'username': username}
        )
        
        # Prepare response
        response_data = {
            'token': jwt_token,
            'user': {
                'id': user_data['id'],
                'username': user_data['username'],
                'email': user_data['email'],
                'lastLoginAt': user_data['last_login_at'].isoformat() if user_data['last_login_at'] else None,
                'sessionStartedAt': datetime.now().isoformat()
            }
        }
        
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        log_api_request('/api/auth/login', 'POST', 200, response_time)
        
        return create_success_response(response_data)
        
    except Exception as e:
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        log_api_request('/api/auth/login', 'POST', 500, response_time, str(e))
        logger.error(f"Login error: {e}", exc_info=True)
        return create_error_response("Internal server error", status_code=500)

@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def auth_logout():
    """User logout endpoint."""
    start_time = datetime.now()
    
    try:
        user = request.current_user
        
        # End session
        auth_db.end_session(user['session_token'], 'user_logout')
        
        # Log logout activity
        log_auth_activity(
            auth_db,
            user['id'],
            user['session_id'],
            'logout',
            {'username': user['username']}
        )
        
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        log_api_request('/api/auth/logout', 'POST', 200, response_time)
        
        return create_success_response({'message': 'Logout successful'})
        
    except Exception as e:
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        log_api_request('/api/auth/logout', 'POST', 500, response_time, str(e))
        logger.error(f"Logout error: {e}", exc_info=True)
        return create_error_response("Internal server error", status_code=500)

@app.route('/api/auth/verify', methods=['GET'])
@require_auth
def auth_verify():
    """Token verification endpoint."""
    start_time = datetime.now()
    
    try:
        user = request.current_user
        
        response_data = {
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'lastLoginAt': None,  # Would need to fetch from DB if needed
                'sessionStartedAt': None  # Would need to fetch from session data
            }
        }
        
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        log_api_request('/api/auth/verify', 'GET', 200, response_time)
        
        return create_success_response(response_data)
        
    except Exception as e:
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        log_api_request('/api/auth/verify', 'GET', 500, response_time, str(e))
        logger.error(f"Verify error: {e}", exc_info=True)
        return create_error_response("Internal server error", status_code=500)

@app.route('/api/auth/reset-password', methods=['POST'])
@limiter.limit("3 per hour")
def auth_reset_password():
    """Password reset request endpoint."""
    start_time = datetime.now()
    
    try:
        if not request.is_json:
            return create_error_response("Request must be JSON", status_code=400)
        
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        
        if not email:
            return create_error_response("Email is required")
        
        if not validate_email(email):
            return create_error_response("Invalid email format")
        
        # Create reset token (always return success for security)
        ip_address, user_agent = get_client_info(request)
        reset_token = auth_db.create_password_reset_token(email, ip_address, user_agent)
        
        # Log reset request
        if reset_token:
            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                    user_row = cursor.fetchone()
                    if user_row:
                        log_auth_activity(
                            auth_db,
                            user_row[0],
                            None,
                            'password_reset_request',
                            {'email': email}
                        )
                    cursor.close()
                    conn.close()
            except:
                pass
        
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        log_api_request('/api/auth/reset-password', 'POST', 200, response_time)
        
        # Always return success for security (don't reveal if email exists)
        return create_success_response({'message': 'Password reset email sent if account exists'})
        
    except Exception as e:
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        log_api_request('/api/auth/reset-password', 'POST', 500, response_time, str(e))
        logger.error(f"Password reset error: {e}", exc_info=True)
        return create_error_response("Internal server error", status_code=500)

@app.route('/api/auth/log-activity', methods=['POST'])
@require_auth_optional
def auth_log_activity():
    """Log user activity endpoint."""
    start_time = datetime.now()
    
    try:
        if not request.is_json:
            return create_error_response("Request must be JSON", status_code=400)
        
        data = request.get_json()
        
        # If user is authenticated, use their data
        if hasattr(request, 'current_user') and request.current_user:
            user_id = request.current_user['id']
            session_id = request.current_user['session_id']
        else:
            # For anonymous activities
            user_id = data.get('userId')
            session_id = None
        
        activity_type = data.get('activity', '')
        activity_details = data.get('details', {})
        
        if not activity_type:
            return create_error_response("Activity type is required")
        
        # Log the activity
        ip_address, user_agent = get_client_info(request)
        success = auth_db.log_activity(
            user_id=user_id,
            session_id=session_id,
            activity_type=activity_type,
            details=activity_details,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        if not success:
            return create_error_response("Failed to log activity", status_code=500)
        
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        log_api_request('/api/auth/log-activity', 'POST', 200, response_time)
        
        return create_success_response({'message': 'Activity logged successfully'})
        
    except Exception as e:
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        log_api_request('/api/auth/log-activity', 'POST', 500, response_time, str(e))
        logger.error(f"Log activity error: {e}", exc_info=True)
        return create_error_response("Internal server error", status_code=500)

@app.route('/api/auth/sessions/<user_id>', methods=['GET'])
@require_auth
def auth_get_sessions(user_id):
    """Get user session history endpoint."""
    start_time = datetime.now()
    
    try:
        current_user = request.current_user
        
        # Users can only access their own session data
        if current_user['id'] != user_id:
            return create_error_response("Unauthorized access to user data", status_code=403)
        
        # Get session history
        sessions = auth_db.get_user_sessions(user_id)
        
        # Format sessions for response
        formatted_sessions = []
        for session in sessions:
            formatted_session = {
                'id': session['id'],
                'userId': session['user_id'],
                'sessionId': session['id'],
                'startTime': session['created_at'].isoformat() if session['created_at'] else None,
                'endTime': session['ended_at'].isoformat() if session['ended_at'] else None,
                'duration': int(session.get('duration_seconds', 0)),
                'activities': session.get('activities', []),
                'ipAddress': str(session['ip_address']) if session['ip_address'] else None,
                'userAgent': session['user_agent']
            }
            formatted_sessions.append(formatted_session)
        
        response_data = {'sessions': formatted_sessions}
        
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        log_api_request(f'/api/auth/sessions/{user_id}', 'GET', 200, response_time)
        
        return create_success_response(response_data)
        
    except Exception as e:
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        log_api_request(f'/api/auth/sessions/{user_id}', 'GET', 500, response_time, str(e))
        logger.error(f"Get sessions error: {e}", exc_info=True)
        return create_error_response("Internal server error", status_code=500)

@app.route('/api/chat', methods=['POST'])
@limiter.limit("10 per minute")
def chat_proxy():
    """Chat endpoint that redirects to GPU instance."""
    start_time = datetime.now()
    
    try:
        if not request.is_json:
            return jsonify({'error': 'Request must be JSON'}), 400
        
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Message is required'}), 400
        
        # Forward request to GPU instance
        gpu_url = "http://172.28.69.2:8081/chat"
        
        try:
            response = requests.post(
                gpu_url,
                json=data,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            log_api_request('/api/chat', 'POST', response.status_code, response_time)
            
            # Return the GPU instance response
            return jsonify(response.json()), response.status_code
            
        except requests.exceptions.RequestException as e:
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            log_api_request('/api/chat', 'POST', 502, response_time, str(e))
            
            return jsonify({
                'error': 'Chat service unavailable',
                'details': 'Unable to connect to chat service',
                'timestamp': datetime.now().isoformat()
            }), 502
        
    except Exception as e:
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        log_api_request('/api/chat', 'POST', 500, response_time, str(e))
        logger.error(f"Chat proxy error: {e}", exc_info=True)
        
        return jsonify({
            'error': 'Internal server error',
            'timestamp': datetime.now().isoformat()
        }), 500

if __name__ == '__main__':
    # Test database connection on startup
    if test_db_connection():
        port = int(os.getenv('PORT', '8443'))
        # SSL solo si USE_SSL=true (en la nube, el host provee TLS).
        use_ssl = os.getenv('USE_SSL', 'false').lower() == 'true'
        ssl_ctx = ('certs/cert.pem', 'certs/key.pem') if use_ssl else None
        logger.info(f"Starting Flask on 0.0.0.0:{port} (ssl={use_ssl})")
        app.run(
            host='0.0.0.0',
            port=port,
            debug=False,
            threaded=True,
            ssl_context=ssl_ctx
        )
    else:
        logger.error("Failed to establish database connection. Exiting.")
        exit(1)
