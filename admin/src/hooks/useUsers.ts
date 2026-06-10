import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listUsers, createUser, updateUser, toggleUserStatus, resetUserPassword, deleteUser } from '../api/users';
import type { UserRole, UserStatus } from '../types';

export function useUsers(page: number, pageSize: number, search?: string, departmentId?: string) {
  return useQuery({
    queryKey: ['users', page, pageSize, search, departmentId],
    queryFn: () => listUsers({ page, page_size: pageSize, search, department_id: departmentId }),
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { username: string; password: string; display_name: string; email?: string; department_id?: string; role?: UserRole }) =>
      createUser(data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['users'] }); },
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: { display_name?: string; email?: string; department_id?: string; role?: UserRole } }) =>
      updateUser(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['users'] }); },
  });
}

export function useToggleUserStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: UserStatus }) => toggleUserStatus(id, status),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['users'] }); },
  });
}

export function useResetUserPassword() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, newPassword }: { id: string; newPassword: string }) => resetUserPassword(id, newPassword),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['users'] }); },
  });
}

export function useDeleteUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteUser(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['users'] }); },
  });
}
