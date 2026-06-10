import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getDepartmentTree, createDepartment, updateDepartment, deleteDepartment, listDepartmentUsers } from '../api/departments';
import type { Department } from '../types';

function flattenDepartments(depts: Department[], prefix = ''): { value: string; label: string }[] {
  const result: { value: string; label: string }[] = [];
  for (const d of depts) {
    result.push({ value: d.id, label: prefix + d.name });
    if (d.children?.length) {
      result.push(...flattenDepartments(d.children, prefix + d.name + ' / '));
    }
  }
  return result;
}

export function useDepartmentTree() {
  return useQuery({
    queryKey: ['departments'],
    queryFn: getDepartmentTree,
  });
}

export function useDepartmentOptions() {
  const { data, ...rest } = useDepartmentTree();
  return {
    ...rest,
    options: data?.departments ? flattenDepartments(data.departments) : [],
  };
}

export function useDepartmentUsers(deptId: string | undefined, page = 1, pageSize = 20) {
  return useQuery({
    queryKey: ['department-users', deptId, page, pageSize],
    queryFn: () => listDepartmentUsers(deptId!, { page, page_size: pageSize }),
    enabled: !!deptId,
  });
}

export function useCreateDepartment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; parent_id?: string }) => createDepartment(data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['departments'] }); },
  });
}

export function useUpdateDepartment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name?: string; parent_id?: string } }) =>
      updateDepartment(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['departments'] }); },
  });
}

export function useDeleteDepartment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteDepartment(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['departments'] }); },
  });
}
