import apiClient from './client';
import type { User, UserRole, UserStatus } from '../types';

interface UserListParams {
  page?: number;
  page_size?: number;
  search?: string;
  department_id?: string;
}

interface UserListResponse {
  users: User[];
  total: number;
  page: number;
  page_size: number;
}

interface CreateUserParams {
  username: string;
  password: string;
  display_name: string;
  email?: string;
  department_id?: string;
  role?: UserRole;
}

interface UpdateUserParams {
  display_name?: string;
  email?: string;
  department_id?: string;
  role?: UserRole;
}

export async function listUsers(params: UserListParams): Promise<UserListResponse> {
  const res = await apiClient.get('/api/admin/users', { params });
  return res.data;
}

export async function createUser(data: CreateUserParams): Promise<User> {
  const res = await apiClient.post('/api/admin/users', data);
  return res.data;
}

export async function getUser(id: string): Promise<User> {
  const res = await apiClient.get(`/api/admin/users/${id}`);
  return res.data;
}

export async function updateUser(id: string, data: UpdateUserParams): Promise<User> {
  const res = await apiClient.put(`/api/admin/users/${id}`, data);
  return res.data;
}

export async function toggleUserStatus(id: string, status: UserStatus): Promise<User> {
  const res = await apiClient.put(`/api/admin/users/${id}/status`, { status });
  return res.data;
}

export async function resetUserPassword(id: string, newPassword: string): Promise<void> {
  await apiClient.put(`/api/admin/users/${id}/password`, { new_password: newPassword });
}

export async function deleteUser(id: string): Promise<void> {
  await apiClient.delete(`/api/admin/users/${id}`);
}
