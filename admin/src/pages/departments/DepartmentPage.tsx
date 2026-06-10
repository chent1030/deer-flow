import { useState } from 'react';
import { Tree, Button, Space, Popconfirm, message, Card, Modal, Table } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, TeamOutlined } from '@ant-design/icons';
import type { TreeProps } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useDepartmentTree, useDeleteDepartment, useDepartmentUsers } from '../../hooks/useDepartments';
import type { Department, User } from '../../types';
import DepartmentForm from './DepartmentForm';

export default function DepartmentPage() {
  const [formOpen, setFormOpen] = useState(false);
  const [editingDept, setEditingDept] = useState<Department | undefined>();
  const [parentId, setParentId] = useState<string | undefined>();
  const [membersOpen, setMembersOpen] = useState(false);
  const [membersDeptId, setMembersDeptId] = useState<string | undefined>();
  const [membersDeptName, setMembersDeptName] = useState('');
  const [membersPage, setMembersPage] = useState(1);
  const { data, isLoading } = useDepartmentTree();
  const deleteDept = useDeleteDepartment();
  const { data: membersData, isLoading: membersLoading } = useDepartmentUsers(membersDeptId, membersPage);

  const showMembers = (deptId: string, deptName: string) => {
    setMembersDeptId(deptId);
    setMembersDeptName(deptName);
    setMembersPage(1);
    setMembersOpen(true);
  };

  const memberColumns: ColumnsType<User> = [
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '显示名', dataIndex: 'display_name', key: 'display_name' },
    { title: '角色', dataIndex: 'role', key: 'role' },
    { title: '邮箱', dataIndex: 'email', key: 'email' },
  ];

  const buildTreeData = (depts: Department[]): TreeProps['treeData'] =>
    depts.map((dept) => ({
      key: dept.id,
      title: (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          {dept.name}
          <span style={{ color: '#999', fontSize: 12 }}>({dept.member_count} 人)</span>
          <Space size={4}>
            <Button
              type="link"
              size="small"
              icon={<TeamOutlined />}
              title="查看成员"
              onClick={(e) => {
                e.stopPropagation();
                showMembers(dept.id, dept.name);
              }}
            />
            <Button
              type="link"
              size="small"
              icon={<PlusOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                setEditingDept(undefined);
                setParentId(dept.id);
                setFormOpen(true);
              }}
            />
            <Button
              type="link"
              size="small"
              icon={<EditOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                setEditingDept(dept);
                setParentId(undefined);
                setFormOpen(true);
              }}
            />
            <Popconfirm
              title="确认删除该部门？"
              description="请先转移该部门下的用户。"
              onConfirm={() => {
                deleteDept.mutate(dept.id, {
                  onSuccess: () => message.success('部门已删除'),
                  onError: (e: any) => message.error(e.response?.data?.detail || '删除失败'),
                });
              }}
            >
              <Button
                type="link"
                size="small"
                danger
                icon={<DeleteOutlined />}
                onClick={(e) => e.stopPropagation()}
              />
            </Popconfirm>
          </Space>
        </span>
      ),
      children: dept.children ? buildTreeData(dept.children) : [],
    }));

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'flex-end' }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditingDept(undefined); setParentId(undefined); setFormOpen(true); }}>
          新建部门
        </Button>
      </div>
      <Card loading={isLoading}>
        {data?.departments && data.departments.length > 0 ? (
          <Tree
            treeData={buildTreeData(data.departments)}
            defaultExpandAll
            showLine
          />
        ) : (
          <div style={{ textAlign: 'center', padding: 40, color: '#999' }}>暂无部门</div>
        )}
      </Card>
      <DepartmentForm
        open={formOpen}
        department={editingDept}
        parentId={parentId}
        onClose={() => { setFormOpen(false); setEditingDept(undefined); setParentId(undefined); }}
      />
      <Modal
        title={`${membersDeptName} - 成员列表`}
        open={membersOpen}
        onCancel={() => setMembersOpen(false)}
        footer={null}
        width={700}
      >
        <Table
          columns={memberColumns}
          dataSource={membersData?.users || []}
          rowKey="id"
          loading={membersLoading}
          pagination={{
            current: membersPage,
            pageSize: 20,
            total: membersData?.total || 0,
            onChange: setMembersPage,
          }}
        />
      </Modal>
    </div>
  );
}
