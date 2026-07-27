const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://10.49.12.46:420/api';

export interface PredictionRequest {
  N: number;
  P: number;
  K: number;
  temperature: number;
  humidity: number;
  ph: number;
  rainfall: number;
}

export interface PredictionResponse {
  predicted_crop: string;
  confidence: number;
  top_predictions: {
    crop: string;
    probability: number;
  }[];
  input_features: {
    N: number;
    P: number;
    K: number;
    temperature: number;
    humidity: number;
    ph: number;
    rainfall: number;
  };
  warnings?: string;
  timestamp: string;
}

export interface ApiError {
  error: string;
  details?: string;
  timestamp: string;
}

export interface HealthResponse {
  status: string;
  timestamp: string;
  database: string;
  models_loaded: number;
  available_models: string[];
}

export interface Crop {
  name: string;
}

export interface Feature {
  name: string;
  min_value: number;
  max_value: number;
  unit: string;
  description: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  token: string;
  user: {
    id: string;
    username: string;
    email?: string;
    lastLoginAt: string;
    sessionStartedAt: string;
  };
}

export interface ResetPasswordRequest {
  email: string;
}

export interface SignupRequest {
  username: string;
  email: string;
  password: string;
}

export interface SessionActivity {
  userId: string;
  activity: 'login' | 'logout' | 'page_view' | 'action';
  timestamp: string;
  userAgent?: string;
  ipAddress?: string;
  details?: Record<string, any>;
}

export interface SessionLog {
  id: string;
  userId: string;
  sessionId: string;
  startTime: string;
  endTime?: string;
  duration?: number;
  activities: SessionActivity[];
  ipAddress: string;
  userAgent: string;
}

export interface PredictionLog {
  id: string;
  userId: string;
  timestamp: string;
  inputFeatures: {
    N: number;
    P: number;
    K: number;
    temperature: number;
    humidity: number;
    ph: number;
    rainfall: number;
  };
  predictedCrop: string;
  confidence: number;
  topPredictions: {
    crop: string;
    probability: number;
  }[];
  status: 'success' | 'error';
  processingTime?: number;
  errorMessage?: string;
}

class CropRecommendationAPI {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  async checkHealth(): Promise<HealthResponse> {
    const response = await fetch(`${this.baseUrl}/health`, {
      credentials: 'include',
      referrerPolicy: "unsafe-url"
    });
    
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.status}`);
    }
    
    return response.json();
  }

  async predictCrop(data: PredictionRequest, token?: string): Promise<PredictionResponse> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${this.baseUrl}/predict`, {
      method: 'POST',
      headers,
      body: JSON.stringify(data),
      credentials: 'include',
      referrerPolicy: "unsafe-url"
    });

    const result = await response.json();

    if (!response.ok) {
      const error: ApiError = result;
      throw new Error(error.error || 'Prediction failed');
    }

    return result;
  }

  async getCrops(): Promise<{ crops: string[]; count: number; timestamp: string }> {
    const response = await fetch(`${this.baseUrl}/crops`, {
      credentials: 'include',
      referrerPolicy: "unsafe-url"
    });
    
    if (!response.ok) {
      throw new Error(`Failed to get crops: ${response.status}`);
    }
    
    return response.json();
  }

  async getFeatures(): Promise<{ features: Feature[]; count: number; timestamp: string }> {
    const response = await fetch(`${this.baseUrl}/features`, {
      credentials: 'include',
      referrerPolicy: "unsafe-url"
    });
    
    if (!response.ok) {
      throw new Error(`Failed to get features: ${response.status}`);
    }
    
    return response.json();
  }

  async predictBatch(predictions: PredictionRequest[]): Promise<PredictionResponse[]> {
    const results = await Promise.all(
      predictions.map(prediction => this.predictCrop(prediction))
    );
    
    return results;
  }

  async login(credentials: LoginRequest): Promise<LoginResponse> {
    const response = await fetch(`${this.baseUrl}/auth/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(credentials),
      credentials: 'include',
      referrerPolicy: "unsafe-url"
    });

    const result = await response.json();

    if (!response.ok) {
      const error: ApiError = result;
      throw new Error(error.error || 'Login failed');
    }

    return result;
  }

  async logout(token: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/auth/logout`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
      credentials: 'include',
      referrerPolicy: "unsafe-url"
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Logout failed');
    }
  }

  async verifyToken(token: string): Promise<LoginResponse> {
    const response = await fetch(`${this.baseUrl}/auth/verify`, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
      credentials: 'include',
      referrerPolicy: "unsafe-url"
    });

    const result = await response.json();

    if (!response.ok) {
      const error: ApiError = result;
      throw new Error(error.error || 'Token verification failed');
    }

    return result;
  }

  async resetPassword(request: ResetPasswordRequest): Promise<void> {
    const response = await fetch(`${this.baseUrl}/auth/reset-password`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
      credentials: 'include',
      referrerPolicy: "unsafe-url"
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Password reset failed');
    }
  }

  async signup(credentials: SignupRequest): Promise<LoginResponse> {
    const response = await fetch(`${this.baseUrl}/auth/signup`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(credentials),
      credentials: 'include',
      referrerPolicy: "unsafe-url"
    });

    const result = await response.json();

    if (!response.ok) {
      const error: ApiError = result;
      throw new Error(error.error || 'Sign up failed');
    }

    return result;
  }

  async logActivity(activity: SessionActivity, token?: string): Promise<void> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${this.baseUrl}/auth/log-activity`, {
      method: 'POST',
      headers,
      body: JSON.stringify(activity),
      credentials: 'include',
      referrerPolicy: "unsafe-url"
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Activity logging failed');
    }
  }

  async getSessionLogs(userId: string, token: string): Promise<SessionLog[]> {
    const response = await fetch(`${this.baseUrl}/auth/sessions/${userId}`, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
      credentials: 'include',
      referrerPolicy: "unsafe-url"
    });

    const result = await response.json();

    if (!response.ok) {
      const error: ApiError = result;
      throw new Error(error.error || 'Failed to get session logs');
    }

    return result.sessions;
  }

  // Dashboard endpoints
  async getDashboardMetrics(): Promise<any> {
    const response = await fetch(`${this.baseUrl}/dashboard/metrics`, {
      credentials: 'include',
      referrerPolicy: "unsafe-url"
    });
    
    if (!response.ok) {
      throw new Error(`Failed to get dashboard metrics: ${response.status}`);
    }
    
    return response.json();
  }

  async getMonthlyPredictions(): Promise<{ data: any[], timestamp: string }> {
    const response = await fetch(`${this.baseUrl}/dashboard/monthly-predictions`, {
      credentials: 'include',
      referrerPolicy: "unsafe-url"
    });
    
    if (!response.ok) {
      throw new Error(`Failed to get monthly predictions: ${response.status}`);
    }
    
    return response.json();
  }

  async getCropDistribution(): Promise<{ data: any[], timestamp: string }> {
    const response = await fetch(`${this.baseUrl}/dashboard/crop-distribution`, {
      credentials: 'include',
      referrerPolicy: "unsafe-url"
    });
    
    if (!response.ok) {
      throw new Error(`Failed to get crop distribution: ${response.status}`);
    }
    
    return response.json();
  }

  // User-specific dashboard endpoints
  async getUserDashboardMetrics(userId?: string, token?: string): Promise<any> {
    const headers: Record<string, string> = {};
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const url = userId 
      ? `${this.baseUrl}/dashboard/user/${userId}/metrics`
      : `${this.baseUrl}/dashboard/metrics`;

    const response = await fetch(url, { headers, credentials: 'include', referrerPolicy: "unsafe-url" });
    
    if (!response.ok) {
      throw new Error(`Failed to get user dashboard metrics: ${response.status}`);
    }
    
    return response.json();
  }

  async getUserMonthlyPredictions(userId?: string, token?: string): Promise<{ data: any[], timestamp: string }> {
    const headers: Record<string, string> = {};
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const url = userId 
      ? `${this.baseUrl}/dashboard/user/${userId}/monthly-predictions`
      : `${this.baseUrl}/dashboard/monthly-predictions`;

    const response = await fetch(url, { headers, credentials: 'include', referrerPolicy: "unsafe-url" });
    
    if (!response.ok) {
      throw new Error(`Failed to get user monthly predictions: ${response.status}`);
    }
    
    return response.json();
  }

  async getUserCropDistribution(userId?: string, token?: string): Promise<{ data: any[], timestamp: string }> {
    const headers: Record<string, string> = {};
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const url = userId 
      ? `${this.baseUrl}/dashboard/user/${userId}/crop-distribution`
      : `${this.baseUrl}/dashboard/crop-distribution`;

    const response = await fetch(url, { headers, credentials: 'include', referrerPolicy: "unsafe-url" });
    
    if (!response.ok) {
      throw new Error(`Failed to get user crop distribution: ${response.status}`);
    }
    
    return response.json();
  }

  // Analytics endpoints
  async getResponseTimeData(token?: string): Promise<{ data: { timestamp: string; responseTime: number }[], timestamp: string }> {
    const headers: Record<string, string> = {};
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${this.baseUrl}/analytics/user/response-time-data`, {
      headers,
      credentials: 'include',
      referrerPolicy: "unsafe-url"
    });
    
    if (!response.ok) {
      throw new Error(`Failed to get response time data: ${response.status}`);
    }
    
    return response.json();
  }

  async getUserPredictions(token?: string): Promise<{ predictions: { date: string; user: string; recommendedCrop: string; confidence: number }[], timestamp: string }> {
    const headers: Record<string, string> = {};
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${this.baseUrl}/analytics/user-predictions`, {
      headers,
      credentials: 'include',
      referrerPolicy: "unsafe-url"
    });
    
    if (!response.ok) {
      throw new Error(`Failed to get user predictions: ${response.status}`);
    }
    
    return response.json();
  }

  async getModelMetrics(token?: string): Promise<{ metrics: any[], timestamp: string }> {
    const headers: Record<string, string> = {};
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${this.baseUrl}/analytics/user/model-metrics`, {
      headers,
      credentials: 'include',
      referrerPolicy: "unsafe-url"
    });
    
    if (!response.ok) {
      throw new Error(`Failed to get model metrics: ${response.status}`);
    }
    
    return response.json();
  }

  async getPerformanceMetrics(token?: string): Promise<any> {
    const headers: Record<string, string> = {};
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${this.baseUrl}/analytics/user/performance-metrics`, {
      headers,
      credentials: 'include',
      referrerPolicy: "unsafe-url"
    });
    
    if (!response.ok) {
      throw new Error(`Failed to get performance metrics: ${response.status}`);
    }
    
    return response.json();
  }

  // About page metrics endpoint
  async getAboutMetrics(): Promise<{
    crops_analyzed: number;
    active_users: number;
    success_rate: number;
    countries_served: number;
  }> {
    const response = await fetch(`${this.baseUrl}/about/metrics`, {
      credentials: 'include',
      referrerPolicy: "unsafe-url"
    });
    
    if (!response.ok) {
      throw new Error(`Failed to get about metrics: ${response.status}`);
    }
    
    return response.json();
  }

  // Chatbot endpoint
  async sendChatMessage(message: string, conversationId?: string): Promise<{
    response: string;
    conversationId: string;
    suggestions?: string[];
    context?: any;
  }> {
    try {
      // Use the direct chat endpoint (usa la URL base configurable)
      const chatEndpoint = `${import.meta.env.VITE_API_BASE_URL || 'https://10.49.12.46:420/api'}/chat`;
      
      const response = await fetch(chatEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message,
        }),
        credentials: 'include',
        referrerPolicy: "unsafe-url"
      });

      if (!response.ok) {
        // Try to get error details from response
        let errorMessage = `Chat request failed with status ${response.status}`;
        try {
          const errorData = await response.json();
          errorMessage = errorData.error || errorData.message || errorMessage;
        } catch {
          // If we can't parse the error response, use the status-based message
        }
        throw new Error(errorMessage);
      }

      const result = await response.json();

      // Adapt the response format to what the ChatBot component expects
      // Backend returns: { model, processing_time_ms, response, server_type, timestamp }
      return {
        response: result.response || result.message || 'No response received',
        conversationId: conversationId || 'chat-session-' + Date.now(),
        suggestions: result.suggestions || undefined,
        context: {
          model: result.model,
          processingTime: result.processing_time_ms,
          serverType: result.server_type,
          timestamp: result.timestamp
        }
      };
    } catch (error) {
      // Handle network errors, timeout, or parsing errors
      if (error instanceof TypeError && error.message.includes('fetch')) {
        throw new Error('Unable to connect to chat service. Please check your connection.');
      }
      // Re-throw other errors as-is
      throw error;
    }
  }

  // User prediction logs endpoints
  async getUserPredictionLogs(userId: string, token?: string, params?: {
    limit?: number;
    offset?: number;
    dateFrom?: string;
    dateTo?: string;
    crop?: string;
    status?: 'success' | 'error';
    orderBy?: 'timestamp' | 'confidence' | 'predicted_crop' | 'processing_time';
    orderDirection?: 'asc' | 'desc';
  }): Promise<{ logs: PredictionLog[], pagination: { total: number, limit: number, offset: number, hasMore: boolean } }> {
    const headers: Record<string, string> = {};
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    // Build query string
    const queryParams = new URLSearchParams();
    if (params) {
      if (params.limit) queryParams.append('limit', params.limit.toString());
      if (params.offset) queryParams.append('offset', params.offset.toString());
      if (params.dateFrom) queryParams.append('dateFrom', params.dateFrom);
      if (params.dateTo) queryParams.append('dateTo', params.dateTo);
      if (params.crop) queryParams.append('crop', params.crop);
      if (params.status) queryParams.append('status', params.status);
      if (params.orderBy) queryParams.append('orderBy', params.orderBy);
      if (params.orderDirection) queryParams.append('orderDirection', params.orderDirection);
    }

    try {
      const url = `${this.baseUrl}/users/${userId}/prediction-logs${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
      const response = await fetch(url, { headers, credentials: 'include', referrerPolicy: "unsafe-url" });

      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('Endpoint not found - History feature not implemented on backend');
        }
        if (response.status === 401) {
          throw new Error('Unauthorized - Please login again');
        }
        if (response.status === 403) {
          throw new Error('Forbidden - Cannot access other users\' data');
        }
        const error = await response.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(error.error || `Failed to get user prediction logs (${response.status})`);
      }

      const result = await response.json();
      return {
        logs: result.logs || [],
        pagination: result.pagination || { total: 0, limit: 50, offset: 0, hasMore: false }
      };
    } catch (error: any) {
      // If it's already an Error object, re-throw it
      if (error instanceof Error) {
        throw error;
      }
      // Otherwise, wrap it
      throw new Error(error.message || 'Failed to get user prediction logs');
    }
  }

  async getUserPredictionStatistics(userId: string, token?: string, params?: {
    period?: '7d' | '30d' | '90d' | '1y' | 'all';
    groupBy?: 'day' | 'week' | 'month';
  }): Promise<{
    statistics: {
      totalPredictions: number;
      successfulPredictions: number;
      failedPredictions: number;
      successRate: number;
      avgConfidence: number;
      avgProcessingTime: number;
      mostPredictedCrop: string | null;
      firstPrediction: string | null;
      lastPrediction: string | null;
    };
    timeline: Array<{
      date: string;
      predictions: number;
      avgConfidence: number;
    }>;
    cropDistribution: Array<{
      crop: string;
      count: number;
      percentage: number;
    }>;
  }> {
    const headers: Record<string, string> = {};
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    // Build query string
    const queryParams = new URLSearchParams();
    if (params) {
      if (params.period) queryParams.append('period', params.period);
      if (params.groupBy) queryParams.append('groupBy', params.groupBy);
    }

    try {
      const url = `${this.baseUrl}/users/${userId}/prediction-statistics${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
      const response = await fetch(url, { headers, credentials: 'include', referrerPolicy: "unsafe-url" });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Unauthorized - Please login again');
        }
        if (response.status === 403) {
          throw new Error('Forbidden - Cannot access other users\' data');
        }
        const error = await response.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(error.error || `Failed to get user prediction statistics (${response.status})`);
      }

      const result = await response.json();
      return result || {
        statistics: {
          totalPredictions: 0,
          successfulPredictions: 0,
          failedPredictions: 0,
          successRate: 0,
          avgConfidence: 0,
          avgProcessingTime: 0,
          mostPredictedCrop: null,
          firstPrediction: null,
          lastPrediction: null
        },
        timeline: [],
        cropDistribution: []
      };
    } catch (error: any) {
      if (error instanceof Error) {
        throw error;
      }
      throw new Error(error.message || 'Failed to get user prediction statistics');
    }
  }

  async exportUserPredictionLogs(userId: string, token?: string, params?: {
    dateFrom?: string;
    dateTo?: string;
    crop?: string;
    status?: 'success' | 'error';
  }): Promise<Blob> {
    const headers: Record<string, string> = {};
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    // Build query string
    const queryParams = new URLSearchParams();
    if (params) {
      if (params.dateFrom) queryParams.append('dateFrom', params.dateFrom);
      if (params.dateTo) queryParams.append('dateTo', params.dateTo);
      if (params.crop) queryParams.append('crop', params.crop);
      if (params.status) queryParams.append('status', params.status);
    }

    try {
      const url = `${this.baseUrl}/users/${userId}/prediction-logs/export${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
      const response = await fetch(url, { headers, credentials: 'include', referrerPolicy: "unsafe-url" });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Unauthorized - Please login again');
        }
        if (response.status === 403) {
          throw new Error('Forbidden - Cannot access other users\' data');
        }
        const error = await response.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(error.error || `Failed to export user prediction logs (${response.status})`);
      }

      return await response.blob();
    } catch (error: any) {
      if (error instanceof Error) {
        throw error;
      }
      throw new Error(error.message || 'Failed to export user prediction logs');
    }
  }

  async savePredictionLog(predictionData: {
    userId: string;
    inputFeatures: PredictionRequest;
    prediction: PredictionResponse;
    processingTime?: number;
  }, token?: string): Promise<void> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    // Transform the data to match backend expected format
    const transformedData = {
      userId: predictionData.userId,
      inputFeatures: predictionData.inputFeatures,
      prediction: {
        predicted_crop: predictionData.prediction.predicted_crop,
        confidence: predictionData.prediction.confidence,
        top_predictions: predictionData.prediction.top_predictions,
        timestamp: predictionData.prediction.timestamp
      },
      processingTime: predictionData.processingTime,
      sessionId: localStorage.getItem('sessionId') || undefined,
      ipAddress: undefined, // Will be captured by backend
      userAgent: navigator.userAgent
    };

    const response = await fetch(`${this.baseUrl}/prediction-logs`, {
      method: 'POST',
      headers,
      body: JSON.stringify(transformedData),
      credentials: 'include',
      referrerPolicy: "unsafe-url"
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Unknown error' }));
      throw new Error(error.error || 'Failed to save prediction log');
    }
  }
}

export const api = new CropRecommendationAPI();
export default api;
