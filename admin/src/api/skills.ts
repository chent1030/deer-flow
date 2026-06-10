import apiClient from './client';
import type { Skill, SkillStatus, SkillVisibility } from '../types';

interface SkillListParams {
  page?: number;
  page_size?: number;
  status?: SkillStatus;
  department_id?: string;
}

interface SkillListResponse {
  skills: Skill[];
  total: number;
  page: number;
  page_size: number;
}

export async function listSkills(params: SkillListParams): Promise<SkillListResponse> {
  const res = await apiClient.get('/api/admin/skills', { params });
  return res.data;
}

export async function uploadSkill(file: File, name: string, description: string, version?: string): Promise<Skill> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('name', name);
  formData.append('description', description);
  if (version) {
    formData.append('version', version);
  }
  const res = await apiClient.post('/api/admin/skills', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

export async function getSkill(id: string): Promise<Skill> {
  const res = await apiClient.get(`/api/admin/skills/${id}`);
  return res.data;
}

export async function downloadSkill(id: string, name?: string): Promise<void> {
  const res = await apiClient.get(`/api/admin/skills/${id}/download`, { responseType: 'blob' });
  const blob = new Blob([res.data], { type: 'application/zip' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${name || id}.zip`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export async function updateSkill(id: string, data: { name?: string; description?: string; version?: string }): Promise<Skill> {
  const res = await apiClient.put(`/api/admin/skills/${id}`, data);
  return res.data;
}

export async function setSkillVisibility(id: string, visibility: SkillVisibility, visible_user_ids?: string[], visible_department_ids?: string[]): Promise<Skill> {
  const res = await apiClient.put(`/api/admin/skills/${id}/visibility`, {
    visibility,
    visible_user_ids: visible_user_ids || [],
    visible_department_ids: visible_department_ids || [],
  });
  return res.data;
}

export async function submitSkill(id: string): Promise<Skill> {
  const res = await apiClient.post(`/api/admin/skills/${id}/submit`);
  return res.data;
}

export async function withdrawSkill(id: string): Promise<Skill> {
  const res = await apiClient.post(`/api/admin/skills/${id}/withdraw`);
  return res.data;
}

export async function reviewSkill(id: string, action: 'approve' | 'reject', comment?: string): Promise<Skill> {
  const res = await apiClient.post(`/api/admin/skills/${id}/review`, { action, comment: comment || '' });
  return res.data;
}

export async function autoReviewSkill(id: string, reviewSkillName: string): Promise<Skill> {
  const res = await apiClient.post(`/api/admin/skills/${id}/auto-review`, { review_skill_name: reviewSkillName });
  return res.data;
}

export async function deleteSkill(id: string): Promise<void> {
  await apiClient.delete(`/api/admin/skills/${id}`);
}
