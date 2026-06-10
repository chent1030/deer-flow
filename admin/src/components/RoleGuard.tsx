import { UserRole } from '../types';
import { useAuthStore } from '../stores/auth';
import { Result } from 'antd';
import type { ReactNode } from 'react';

interface RoleGuardProps {
  roles: UserRole[];
  children: ReactNode;
}

export default function RoleGuard({ roles, children }: RoleGuardProps) {
  const { user } = useAuthStore();

  if (!user || !roles.includes(user.role)) {
    return (
      <Result
        status="403"
        title="403"
        subTitle="抱歉，您没有权限访问此页面。"
      />
    );
  }

  return <>{children}</>;
}
