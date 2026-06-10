import { useState } from 'react';
import { Table, Button, Input, Space, Tag, Popconfirm, message, Select, Modal, Form } from 'antd';
import { LockOutlined, PlusOutlined, SearchOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { useUsers, useToggleUserStatus, useResetUserPassword, useDeleteUser } from '../../hooks/useUsers';
import { useDepartmentOptions } from '../../hooks/useDepartments';
import { useAuthStore } from '../../stores/auth';
import { UserRole, UserStatus } from '../../types';
import type { User } from '../../types';
import UserFormModal from './UserFormModal';

interface PasswordResetValues {
  new_password: string;
  confirm_password: string;
}

function getApiErrorMessage(error: unknown, fallback: string): string {
  if (typeof error === 'object' && error !== null) {
    const response = Reflect.get(error, 'response');
    if (typeof response === 'object' && response !== null) {
      const data = Reflect.get(response, 'data');
      if (typeof data === 'object' && data !== null) {
        const detail = Reflect.get(data, 'detail');
        if (typeof detail === 'string' && detail) {
          return detail;
        }
      }
    }
  }
  return fallback;
}

export default function UserListPage() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [deptId, setDeptId] = useState<string | undefined>();
  const [modalOpen, setModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | undefined>();
  const [passwordUser, setPasswordUser] = useState<User | undefined>();
  const [passwordForm] = Form.useForm<PasswordResetValues>();

  const { user: currentUser } = useAuthStore();
  const { data, isLoading } = useUsers(page, pageSize, search || undefined, deptId);
  const { options: deptOptions } = useDepartmentOptions();
  const toggleStatus = useToggleUserStatus();
  const resetPassword = useResetUserPassword();
  const deleteUser = useDeleteUser();

  const roleLabels: Record<string, string> = { super_admin: '超级管理员', dept_admin: '部门管理员', user: '普通用户' };
  const statusLabels: Record<string, string> = { active: '启用', disabled: '禁用' };

  const deptNameMap: Record<string, string> = {};
  for (const opt of deptOptions) {
    deptNameMap[opt.value] = opt.label;
  }

  const passwordRules = [
    { required: true, message: '请输入新密码' },
    { min: 8, message: '密码长度不能小于 8 位' },
    {
      pattern: /^(?=.*[a-z])(?=.*[A-Z])(?=.*[^A-Za-z0-9]).+$/,
      message: '密码必须包含大写字母、小写字母和特殊字符',
    },
  ];

  const canResetPassword = (record: User) => {
    if (!currentUser) return false;
    if (currentUser.role === UserRole.SUPER_ADMIN) return true;
    if (currentUser.role === UserRole.DEPT_ADMIN && record.id === currentUser.id) return true;
    return (
      currentUser.role === UserRole.DEPT_ADMIN &&
      record.role === UserRole.USER &&
      record.department_id === currentUser.department_id
    );
  };

  const openPasswordModal = (record: User) => {
    setPasswordUser(record);
    passwordForm.resetFields();
  };

  const handlePasswordReset = async () => {
    if (!passwordUser) return;
    let values: PasswordResetValues;
    try {
      values = await passwordForm.validateFields();
    } catch {
      return;
    }
    try {
      await resetPassword.mutateAsync({ id: passwordUser.id, newPassword: values.new_password });
      message.success('密码已重置');
      setPasswordUser(undefined);
      passwordForm.resetFields();
    } catch (e: unknown) {
      message.error(getApiErrorMessage(e, '密码重置失败'));
    }
  };

  const columns: ColumnsType<User> = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '显示名', dataIndex: 'display_name', key: 'display_name' },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      render: (role: string) => {
        const colorMap: Record<string, string> = { super_admin: 'red', dept_admin: 'blue', user: 'green' };
        return <Tag color={colorMap[role] || 'default'}>{roleLabels[role] || role}</Tag>;
      },
    },
    {
      title: '所属部门',
      dataIndex: 'department_id',
      key: 'department_id',
      render: (deptId: string | null) => deptId ? (deptNameMap[deptId] || deptId) : '-',
    },
    { title: '邮箱', dataIndex: 'email', key: 'email' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={status === 'active' ? 'green' : 'red'}>{statusLabels[status] || status}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      render: (_, record) => (
        <Space>
          {currentUser?.role === UserRole.SUPER_ADMIN && (
            <>
              <Button size="small" onClick={() => {
                setEditingUser(record);
                setModalOpen(true);
              }}>编辑</Button>
              <Popconfirm
                title={`确认${record.status === 'active' ? '禁用' : '启用'}用户？`}
                onConfirm={() => {
                  const newStatus = record.status === 'active' ? UserStatus.DISABLED : UserStatus.ACTIVE;
                  toggleStatus.mutate({ id: record.id, status: newStatus }, {
                    onSuccess: () => message.success('状态已更新'),
                  });
                }}
              >
                <Button size="small" danger={record.status === 'active'}>
                  {record.status === 'active' ? '禁用' : '启用'}
                </Button>
              </Popconfirm>
              <Popconfirm
                title="确认删除用户？"
                onConfirm={() => {
                  deleteUser.mutate(record.id, {
                    onSuccess: () => message.success('用户已删除'),
                  });
                }}
              >
              <Button size="small" danger>删除</Button>
              </Popconfirm>
            </>
          )}
          {canResetPassword(record) && (
            <Button size="small" icon={<LockOutlined />} onClick={() => openPasswordModal(record)}>
              重置密码
            </Button>
          )}
          {currentUser?.role === UserRole.DEPT_ADMIN && record.department_id === currentUser.department_id && (
            <Button size="small" onClick={() => {
              setEditingUser(record);
              setModalOpen(true);
            }}>编辑</Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <Space>
          <Input
            placeholder="搜索用户..."
            prefix={<SearchOutlined />}
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            style={{ width: 250 }}
          />
          {currentUser?.role === UserRole.SUPER_ADMIN && (
            <Select
              placeholder="筛选部门"
              allowClear
              style={{ width: 200 }}
              value={deptId}
              onChange={(v) => { setDeptId(v); setPage(1); }}
              options={deptOptions}
            />
          )}
        </Space>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditingUser(undefined); setModalOpen(true); }}>
          新建用户
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={data?.users || []}
        rowKey="id"
        loading={isLoading}
        pagination={{
          current: page,
          pageSize,
          total: data?.total || 0,
          onChange: (p, ps) => { setPage(p); setPageSize(ps); },
          showSizeChanger: true,
        }}
      />
      <UserFormModal
        open={modalOpen}
        user={editingUser}
        onClose={() => { setModalOpen(false); setEditingUser(undefined); }}
      />
      <Modal
        title={`重置密码${passwordUser ? `：${passwordUser.display_name || passwordUser.username}` : ''}`}
        open={!!passwordUser}
        onCancel={() => { setPasswordUser(undefined); passwordForm.resetFields(); }}
        onOk={handlePasswordReset}
        confirmLoading={resetPassword.isPending}
      >
        <Form form={passwordForm} layout="vertical">
          <Form.Item name="new_password" label="新密码" rules={passwordRules}>
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <Form.Item
            name="confirm_password"
            label="确认新密码"
            dependencies={['new_password']}
            rules={[
              { required: true, message: '请再次输入新密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('new_password') === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error('两次输入的密码不一致'));
                },
              }),
            ]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
