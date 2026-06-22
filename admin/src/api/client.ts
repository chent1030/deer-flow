import axios from 'axios';

const apiClient = axios.create();

const STATE_CHANGING_METHODS = new Set(['post', 'put', 'patch', 'delete']);

function getCookie(name: string): string | undefined {
  const match = document.cookie
    .split('; ')
    .find((cookie) => cookie.startsWith(`${encodeURIComponent(name)}=`));

  if (!match) {
    return undefined;
  }

  return decodeURIComponent(match.split('=').slice(1).join('='));
}

function createCsrfToken(): string {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
}

function ensureCsrfToken(): string {
  const existing = getCookie('csrf_token');
  if (existing) {
    return existing;
  }

  const token = createCsrfToken();
  document.cookie = `csrf_token=${encodeURIComponent(token)}; path=/; SameSite=Strict`;
  return token;
}

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`);
  }

  const method = (config.method ?? 'get').toLowerCase();
  if (STATE_CHANGING_METHODS.has(method) && !config.headers.has('X-CSRF-Token')) {
    config.headers.set('X-CSRF-Token', ensureCsrfToken());
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        try {
          const response = await axios.post(
            '/api/admin/auth/refresh',
            {
              refresh_token: refreshToken,
            },
            { headers: { 'X-CSRF-Token': ensureCsrfToken() } }
          );
          const { access_token, refresh_token } = response.data;
          localStorage.setItem('access_token', access_token);
          localStorage.setItem('refresh_token', refresh_token);
          originalRequest.headers.set('Authorization', `Bearer ${access_token}`);
          return apiClient(originalRequest);
        } catch {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          window.location.href = '/login';
        }
      } else {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default apiClient;
