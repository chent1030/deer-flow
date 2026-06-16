import axios from 'axios';

const apiClient = axios.create();

function getCookie(name: string): string | undefined {
  const match = document.cookie
    .split('; ')
    .find((cookie) => cookie.startsWith(`${encodeURIComponent(name)}=`));

  if (!match) {
    return undefined;
  }

  return decodeURIComponent(match.split('=').slice(1).join('='));
}

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  const csrfToken = getCookie('csrf_token');
  if (csrfToken) {
    config.headers['X-CSRF-Token'] = csrfToken;
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
          const csrfToken = getCookie('csrf_token');
          const response = await axios.post(
            '/api/admin/auth/refresh',
            {
              refresh_token: refreshToken,
            },
            csrfToken ? { headers: { 'X-CSRF-Token': csrfToken } } : undefined
          );
          const { access_token, refresh_token } = response.data;
          localStorage.setItem('access_token', access_token);
          localStorage.setItem('refresh_token', refresh_token);
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
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
