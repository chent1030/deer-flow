import { useEffect } from 'react';
import { Modal, Form, Input, Select, message } from 'antd';
import { useCreateUser, useUpdateUser } from '../../hooks/useUsers';
import { useDepartmentOptions } from '../../hooks/useDepartments';
import { useAuthStore } from '../../stores/auth';
import { UserRole } from '../../types';
import type { User } from '../../types';

interface UserFormModalProps {
  open: boolean;
  user?: User;
  onClose: () => void;
}

export default function UserFormModal({ open, user, onClose }: UserFormModalProps) {
  const [form] = Form.useForm();
  const createUser = useCreateUser();
  const updateUser = useUpdateUser();
  const { user: currentUser } = useAuthStore();
  const { options: deptOptions } = useDepartmentOptions();
  const isEdit = !!user;
  const isSuperAdmin = currentUser?.role === UserRole.SUPER_ADMIN;

  useEffect(() => {
    if (open) {
      if (user) {
        form.setFieldsValue({
          username: user.username,
          display_name: user.display_name,
          email: user.email,
          role: user.role,
          department_id: user.department_id || undefined,
        });
      } else {
        form.resetFields();
      }
    }
  }, [open, user, form]);

  const onFinish = async (values: Record<string, string>) => {
    try {
      if (isEdit) {
        const payload: Record<string, unknown> = {
          display_name: values.display_name,
          email: values.email,
          role: values.role,
        };
        if (isSuperAdmin) {
          if (values.department_id) {
            payload.department_id = values.department_id;
          } else if (user?.department_id) {
            payload.clear_department = true;
          }
        }
        await updateUser.mutateAsync({
          id: user!.id,
          data: payload as Parameters<typeof updateUser.mutateAsync>[0]['data'],
        });
        message.success('用户已更新');
      } else {
        await createUser.mutateAsync({
          username: values.username,
          password: values.password,
          display_name: values.display_name,
          email: values.email,
          role: values.role,
          department_id: values.department_id || undefined,
        });
        message.success('用户已创建');
      }
      onClose();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      message.error(err.response?.data?.detail || '操作失败');
    }
  };

  const roleOptions = isSuperAdmin
    ? [
        { value: UserRole.USER, label: '普通用户' },
        { value: UserRole.DEPT_ADMIN, label: '部门管理员' },
        { value: UserRole.SUPER_ADMIN, label: '超级管理员' },
      ]
    : [{ value: UserRole.USER, label: '普通用户' }];

  const passwordRules = [
    { required: true, message: '请输入密码' },
    { min: 8, message: '密码长度不能小于 8 位' },
    {
      pattern: /^(?=.*[a-z])(?=.*[A-Z])(?=.*[^A-Za-z0-9]).+$/,
      message: '密码必须包含大写字母、小写字母和特殊字符',
    },
  ];

  return (
    <Modal
      title={isEdit ? '编辑用户' : '新建用户'}
      open={open}
      onCancel={onClose}
      onOk={() => form.submit()}
      confirmLoading={createUser.isPending || updateUser.isPending}
    >
      <Form form={form} layout="vertical" onFinish={onFinish}>
        <Form.Item name="username" label="用户名" rules={isEdit ? [] : [{ required: true, min: 2, max: 50 }]}>
          <Input disabled={isEdit} />
        </Form.Item>
        {!isEdit && (
          <Form.Item name="password" label="密码" rules={passwordRules}>
            <Input.Password />
          </Form.Item>
        )}
        <Form.Item name="display_name" label="显示名" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item name="email" label="邮箱">
          <Input />
        </Form.Item>
        {isSuperAdmin && (
          <Form.Item name="department_id" label="所属部门">
            <Select
              placeholder="请选择部门"
              allowClear
              options={deptOptions}
            />
          </Form.Item>
        )}
        <Form.Item name="role" label="角色" rules={[{ required: true }]}>
          <Select options={roleOptions} />
        </Form.Item>
      </Form>
    </Modal>
  );
}
