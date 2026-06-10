import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listSkills, uploadSkill, updateSkill, setSkillVisibility,
  submitSkill, withdrawSkill, reviewSkill, autoReviewSkill, deleteSkill,
} from '../api/skills';
import type { SkillStatus, SkillVisibility } from '../types';

export function useSkills(page: number, pageSize: number, status?: SkillStatus, departmentId?: string) {
  return useQuery({
    queryKey: ['skills', page, pageSize, status, departmentId],
    queryFn: () => listSkills({ page, page_size: pageSize, status, department_id: departmentId }),
  });
}

export function useUploadSkill() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, name, description, version }: { file: File; name: string; description: string; version?: string }) =>
      uploadSkill(file, name, description, version),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['skills'] }); },
  });
}

export function useUpdateSkill() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name?: string; description?: string; version?: string } }) =>
      updateSkill(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['skills'] }); },
  });
}

export function useSetVisibility() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, visibility, visibleUserIds, visibleDepartmentIds }: {
      id: string;
      visibility: SkillVisibility;
      visibleUserIds?: string[];
      visibleDepartmentIds?: string[];
    }) => setSkillVisibility(id, visibility, visibleUserIds, visibleDepartmentIds),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['skills'] }); },
  });
}

export function useSubmitSkill() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => submitSkill(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['skills'] }); },
  });
}

export function useWithdrawSkill() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => withdrawSkill(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['skills'] }); },
  });
}

export function useReviewSkill() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, action, comment }: { id: string; action: 'approve' | 'reject'; comment?: string }) =>
      reviewSkill(id, action, comment),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['skills'] }); },
  });
}

export function useAutoReviewSkill() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reviewSkillName }: { id: string; reviewSkillName: string }) =>
      autoReviewSkill(id, reviewSkillName),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['skills'] }); },
  });
}

export function useDeleteSkill() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteSkill(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['skills'] }); },
  });
}
