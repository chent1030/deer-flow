import { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Avatar, Dropdown, theme, Modal, Form, Input, message } from 'antd';
import {
  DashboardOutlined,
  UserOutlined,
  ApartmentOutlined,
  RobotOutlined,
  AuditOutlined,
  ShareAltOutlined,
  LogoutOutlined,
  MessageOutlined,
  LockOutlined,
} from '@ant-design/icons';
import type { MenuProps } from 'antd';
import { changePassword } from '../api/auth';
import { useAuthStore } from '../stores/auth';
import { UserRole } from '../types';

const { Header, Sider, Content } = Layout;

interface PasswordFormValues {
  old_password: string;
  new_password: string;
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
    const errorMessage = Reflect.get(error, 'message');
    if (typeof errorMessage === 'string' && errorMessage) {
      return errorMessage;
    }
  }
  return fallback;
}

export default function AdminLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const [passwordModalOpen, setPasswordModalOpen] = useState(false);
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [passwordForm] = Form.useForm();
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();
  const { token: { colorBgContainer, borderRadiusLG } } = theme.useToken();

  const passwordRules = [
    { required: true, message: '请输入新密码' },
    { min: 8, message: '密码长度不能小于 8 位' },
    {
      pattern: /^(?=.*[a-z])(?=.*[A-Z])(?=.*[^A-Za-z0-9]).+$/,
      message: '密码必须包含大写字母、小写字母和特殊字符',
    },
  ];

  const handleChangePassword = async () => {
    const values = await passwordForm.validateFields() as PasswordFormValues;
    setPasswordLoading(true);
    try {
      await changePassword(values.old_password, values.new_password);
      message.success('密码已修改');
      setPasswordModalOpen(false);
      passwordForm.resetFields();
    } catch (e: unknown) {
      message.error(getApiErrorMessage(e, '密码修改失败'));
    } finally {
      setPasswordLoading(false);
    }
  };

  const menuItems: MenuProps['items'] = [
    {
      key: '/dashboard',
      icon: <DashboardOutlined />,
      label: '仪表盘',
    },
  ];

  if (user?.role === UserRole.SUPER_ADMIN || user?.role === UserRole.DEPT_ADMIN) {
    menuItems!.push({
      key: '/users',
      icon: <UserOutlined />,
      label: '用户管理',
    });
  }

  if (user?.role === UserRole.SUPER_ADMIN) {
    menuItems!.push({
      key: '/departments',
      icon: <ApartmentOutlined />,
      label: '部门管理',
    });
    menuItems!.push({
      key: '/threads',
      icon: <MessageOutlined />,
      label: '对话审计',
    });
    menuItems!.push({
      key: '/agent-shares',
      icon: <ShareAltOutlined />,
      label: '智能体分享记录',
    });
  }

  menuItems!.push({
    key: '/skills',
    icon: <RobotOutlined />,
    label: 'Skill 管理',
  });

  if (user?.role === UserRole.SUPER_ADMIN) {
    menuItems!.push({
      key: '/skills/review',
      icon: <AuditOutlined />,
      label: 'Skill 审核',
    });
  }

  const userMenuItems: MenuProps['items'] = [
    {
      key: 'changePassword',
      icon: <LockOutlined />,
      label: '修改密码',
      onClick: () => setPasswordModalOpen(true),
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: () => {
        logout();
        navigate('/login');
      },
    },
  ];

  const selectedKey = location.pathname.replace(/^\/admin(?=\/|$)/, '') || '/';

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed}>
        <div style={{ height: 32, margin: 16, color: 'white', fontSize: collapsed ? 14 : 18, fontWeight: 'bold', textAlign: 'center' }}>
          {collapsed ? '芯' : '芯工坊调度系统管理端'}
        </div>
        <Menu
          theme="dark"
          selectedKeys={[selectedKey]}
          mode="inline"
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{ padding: '0 16px', background: colorBgContainer, display: 'flex', justifyContent: 'flex-end', alignItems: 'center' }}>
          <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
            <div style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Avatar icon={<UserOutlined />} />
              <span>{user?.display_name || user?.username}</span>
            </div>
          </Dropdown>
        </Header>
        <Content style={{ margin: 16 }}>
          <div style={{ padding: 24, minHeight: 360, background: colorBgContainer, borderRadius: borderRadiusLG }}>
            <Outlet />
          </div>
        </Content>
      </Layout>
      <Modal
        title="修改密码"
        open={passwordModalOpen}
        onCancel={() => {
          setPasswordModalOpen(false);
          passwordForm.resetFields();
        }}
        onOk={handleChangePassword}
        confirmLoading={passwordLoading}
      >
        <Form form={passwordForm} layout="vertical">
          <Form.Item
            name="old_password"
            label="当前密码"
            rules={[{ required: true, message: '请输入当前密码' }]}
          >
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          <Form.Item
            name="new_password"
            label="新密码"
            rules={passwordRules}
          >
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
    </Layout>
  );
}
