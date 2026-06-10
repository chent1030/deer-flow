import apiClient from './client';
import type { Department, User } from '../types';

interface DepartmentTreeResponse {
  departments: Department[];
}

interface CreateDepartmentParams {
  name: string;
  parent_id?: string;
}

interface UpdateDepartmentParams {
  name?: string;
  parent_id?: string;
}

interface DepartmentUsersResponse {
  users: User[];
  total: number;
  page: number;
  page_size: number;
}

export async function getDepartmentTree(): Promise<DepartmentTreeResponse> {
  const res = await apiClient.get('/api/admin/departments');
  return res.data;
}

export async function createDepartment(data: CreateDepartmentParams): Promise<Department> {
  const res = await apiClient.post('/api/admin/departments', data);
  return res.data;
}

export async function getDepartment(id: string): Promise<Department> {
  const res = await apiClient.get(`/api/admin/departments/${id}`);
  return res.data;
}

export async function updateDepartment(id: string, data: UpdateDepartmentParams): Promise<Department> {
  const res = await apiClient.put(`/api/admin/departments/${id}`, data);
  return res.data;
}

export async function deleteDepartment(id: string): Promise<void> {
  await apiClient.delete(`/api/admin/departments/${id}`);
}

export async function listDepartmentUsers(
  id: string,
  params?: { page?: number; page_size?: number },
): Promise<DepartmentUsersResponse> {
  const res = await apiClient.get(`/api/admin/departments/${id}/users`, { params });
  return res.data;
}
