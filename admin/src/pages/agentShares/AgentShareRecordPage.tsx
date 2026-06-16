import { useState } from 'react';
import { Button, Card, DatePicker, Input, Select, Space, Table, Tag, Typography } from 'antd';
import { ReloadOutlined, SearchOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import dayjs, { type Dayjs } from 'dayjs';
import { useAgentShareRecords } from '../../hooks/useAgentShares';
import { useUsers } from '../../hooks/useUsers';
import { AgentShareStatus } from '../../types';
import type { AgentShareRecord, User } from '../../types';

const { Text } = Typography;

function formatUser(displayName: string | null, username: string | null, id: string) {
  return displayName || username || id;
}

function localizeErrorMessage(message: string | null) {
  if (!message) return null;
  const map: Array<[RegExp, string]> = [
    [/^Agent '(.+)' not found$/, "智能体“$1”不存在"],
    [/^Target user not found$/, "目标用户不存在"],
    [/^Cannot share an agent to self$/, "不能将智能体分享给自己"],
    [/^Target user is disabled$/, "目标用户已被禁用"],
    [/^Failed to /, "操作失败："],
  ];
  for (const [pattern, replacement] of map) {
    if (pattern.test(message)) {
      return message.replace(pattern, replacement);
    }
  }
  return message;
}

export default function AgentShareRecordPage() {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [sourceAgentInput, setSourceAgentInput] = useState('');
  const [targetAgentInput, setTargetAgentInput] = useState('');
  const [sourceOwnerId, setSourceOwnerId] = useState<string | undefined>();
  const [targetUserId, setTargetUserId] = useState<string | undefined>();
  const [sourceAgentName, setSourceAgentName] = useState<string | undefined>();
  const [targetAgentName, setTargetAgentName] = useState<string | undefined>();
  const [status, setStatus] = useState<AgentShareStatus | undefined>();
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs] | null>(null);
  const [sourceUserSearch, setSourceUserSearch] = useState('');
  const [targetUserSearch, setTargetUserSearch] = useState('');

  const sourceUsers = useUsers(1, 50, sourceUserSearch || undefined);
  const targetUsers = useUsers(1, 50, targetUserSearch || undefined);

  const toUserOption = (user: User) => ({
    value: user.id,
    label: `${user.display_name || user.username} (${user.username})`,
  });

  const records = useAgentShareRecords({
    page,
    page_size: pageSize,
    source_owner_id: sourceOwnerId,
    target_user_id: targetUserId,
    source_agent_name: sourceAgentName,
    target_agent_name: targetAgentName,
    status,
    created_from: dateRange?.[0]?.startOf('day').toISOString(),
    created_to: dateRange?.[1]?.endOf('day').toISOString(),
  });

  const applyFilters = () => {
    setSourceAgentName(sourceAgentInput.trim() || undefined);
    setTargetAgentName(targetAgentInput.trim() || undefined);
    setPage(1);
  };

  const resetFilters = () => {
    setSourceAgentInput('');
    setTargetAgentInput('');
    setSourceUserSearch('');
    setTargetUserSearch('');
    setSourceOwnerId(undefined);
    setTargetUserId(undefined);
    setSourceAgentName(undefined);
    setTargetAgentName(undefined);
    setStatus(undefined);
    setDateRange(null);
    setPage(1);
  };

  const columns: ColumnsType<AgentShareRecord> = [
    {
      title: '来源用户',
      key: 'source_owner',
      render: (_, record) => formatUser(record.source_owner_display_name, record.source_owner_username, record.source_owner_id),
    },
    {
      title: '来源智能体',
      dataIndex: 'source_agent_name',
      key: 'source_agent_name',
      ellipsis: true,
    },
    {
      title: '目标用户',
      key: 'target_user',
      render: (_, record) => formatUser(record.target_display_name, record.target_username, record.target_user_id),
    },
    {
      title: '复制后名称',
      dataIndex: 'target_agent_name',
      key: 'target_agent_name',
      ellipsis: true,
      render: (value: string | null) => localizeErrorMessage(value) || <Text type="secondary">-</Text>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (value: AgentShareStatus) => (
        <Tag color={value === AgentShareStatus.CREATED ? 'green' : 'red'}>
          {value === AgentShareStatus.CREATED ? '已创建' : '失败'}
        </Tag>
      ),
    },
    {
      title: '错误信息',
      dataIndex: 'error_message',
      key: 'error_message',
      ellipsis: true,
      render: (value: string | null) => value || <Text type="secondary">-</Text>,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (value: string | null) => value ? dayjs(value).format('YYYY-MM-DD HH:mm:ss') : '-',
    },
  ];

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <Select
            placeholder="来源用户"
            value={sourceOwnerId}
            onChange={(value) => {
              setSourceOwnerId(value);
              setPage(1);
            }}
            onSearch={setSourceUserSearch}
            options={(sourceUsers.data?.users ?? []).map(toUserOption)}
            style={{ width: 220 }}
            loading={sourceUsers.isLoading}
            allowClear
            showSearch
            filterOption={false}
          />
          <Select
            placeholder="目标用户"
            value={targetUserId}
            onChange={(value) => {
              setTargetUserId(value);
              setPage(1);
            }}
            onSearch={setTargetUserSearch}
            options={(targetUsers.data?.users ?? []).map(toUserOption)}
            style={{ width: 220 }}
            loading={targetUsers.isLoading}
            allowClear
            showSearch
            filterOption={false}
          />
          <Input
            placeholder="来源智能体"
            value={sourceAgentInput}
            onChange={(event) => setSourceAgentInput(event.target.value)}
            style={{ width: 180 }}
            allowClear
          />
          <Input
            placeholder="复制后名称"
            value={targetAgentInput}
            onChange={(event) => setTargetAgentInput(event.target.value)}
            style={{ width: 180 }}
            allowClear
          />
          <Select
            placeholder="状态"
            value={status}
            onChange={(value) => {
              setStatus(value);
              setPage(1);
            }}
            options={[
              { value: AgentShareStatus.CREATED, label: '已创建' },
              { value: AgentShareStatus.FAILED, label: '失败' },
            ]}
            style={{ width: 140 }}
            allowClear
          />
          <DatePicker.RangePicker
            value={dateRange}
            onChange={(dates) => {
              setDateRange(dates as [Dayjs, Dayjs] | null);
              setPage(1);
            }}
          />
          <Button type="primary" icon={<SearchOutlined />} onClick={applyFilters}>
            查询
          </Button>
          <Button icon={<ReloadOutlined />} onClick={resetFilters}>
            重置
          </Button>
        </Space>
      </Card>

      <Table
        columns={columns}
        dataSource={records.data?.items ?? []}
        rowKey="id"
        loading={records.isLoading}
        pagination={{
          current: page,
          pageSize,
          total: records.data?.total ?? 0,
          onChange: (nextPage, nextPageSize) => {
            setPage(nextPage);
            setPageSize(nextPageSize);
          },
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 条`,
        }}
      />
    </div>
  );
}
