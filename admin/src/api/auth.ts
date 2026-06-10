import apiClient from './client';
import type { LoginRequest, TokenResponse, User } from '../types';

export async function login(data: LoginRequest): Promise<TokenResponse> {
  const res = await apiClient.post('/api/admin/auth/login', data);
  return res.data;
}

export async function refresh(refresh_token: string): Promise<TokenResponse> {
  const res = await apiClient.post('/api/admin/auth/refresh', { refresh_token });
  return res.data;
}

export async function getMe(): Promise<User> {
  const res = await apiClient.get('/api/admin/auth/me');
  return res.data;
}

export async function changePassword(old_password: string, new_password: string): Promise<void> {
  await apiClient.put('/api/admin/auth/me/password', { old_password, new_password });
}
