import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

export const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getErrorMessage = (error, fallback = '요청을 처리하지 못했습니다.') => {
  const detail = error?.response?.data?.detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg).join('\n') || fallback;
  }
  if (typeof detail === 'string') return detail;
  if (error?.message === 'Network Error') {
    return '백엔드 서버에 연결할 수 없습니다.';
  }
  return error?.response?.data?.message || error?.message || fallback;
};

export const authApi = {
  register: (payload) => api.post('/auth/register', payload),
  login: (payload) => api.post('/auth/login', payload),
  logout: () => api.post('/auth/logout'),
  refresh: () => api.post('/auth/refresh'),
  requestPasswordReset: (payload) => api.post('/auth/password-reset/request', payload),
  confirmPasswordReset: (payload) => api.post('/auth/password-reset/confirm', payload),
  restoreAccount: () => api.post('/auth/account/restore'),
};

export const userApi = {
  me: () => api.get('/users/me'),
  updateMe: (payload) => api.patch('/users/me', payload),
  changePassword: (payload) => api.patch('/users/me/password', payload),
  deleteMe: () => api.delete('/users/me'),
  checkEmail: (email) => api.post('/users/check-email', { email }),
  checkNickname: (nickname) => api.post('/users/check-nickname', { nickname }),
  getNotificationSettings: () => api.get('/users/me/notification-settings'),
  updateNotificationSettings: (payload) => api.patch('/users/me/notification-settings', payload),
};

export const verificationApi = {
  sendEmail: (email) => api.post('/verifications/email', { email }),
  verifyEmail: (payload) => api.post('/verifications/email/verify', payload),
  sendPhone: (phone) => api.post('/verifications/phone', { phone }),
  verifyPhone: (payload) => api.post('/verifications/phone/verify', payload),
};

export const catalogApi = {
  categories: () => api.get('/categories'),
  attributes: (categoryId) => api.get(`/categories/${categoryId}/attributes`),
};

export const regionApi = {
  sd: () => api.get('/regions'),
  sgg: (sdId) => api.get(`/regions/${sdId}/sgg`),
  emd: (sggId) => api.get(`/regions/${sggId}/emd`),
};

export const skuApi = {
  resolve: (payload) => api.post('/sku/resolve', payload),
  detail: (skuId) => api.get(`/sku/${skuId}`),
  priceTrend: (skuId, params = {}) => api.get(`/sku/${skuId}/price-trend`, { params }),
  regionPrices: (skuId, params = {}) => api.get(`/sku/${skuId}/region-prices`, { params }),
};

export const analyticsApi = {
  summary: (params) => api.get('/analytics/summary', { params }),
  listings: (params) => api.get('/analytics/listings', { params }),
  trending: (params = {}) => api.get('/analytics/trending', { params }),
  popular: (params = {}) => api.get('/analytics/popular', { params }),
  platformCompare: (params) => api.get('/analytics/platform-compare', { params }),
};

export const watchlistApi = {
  list: () => api.get('/watchlist'),
  create: (payload) => api.post('/watchlist', payload),
  detail: (watchId) => api.get(`/watchlist/${watchId}`),
  update: (watchId, payload) => api.patch(`/watchlist/${watchId}`, payload),
  toggle: (watchId) => api.patch(`/watchlist/${watchId}/active`),
  remove: (watchId) => api.delete(`/watchlist/${watchId}`),
  alerts: (watchId, params = {}) => api.get(`/watchlist/${watchId}/alerts`, { params }),
};

export const alertsApi = {
  list: (params = {}) => api.get('/alerts', { params }),
  unreadCount: () => api.get('/alerts/unread-count'),
  markRead: (alertId) => api.patch(`/alerts/${alertId}/read`),
  markAllRead: () => api.patch('/alerts/read-all'),
  remove: (alertId) => api.delete(`/alerts/${alertId}`),
  bulkDelete: (alertIds = null) => api.delete('/alerts', { data: { alert_ids: alertIds } }),
};
