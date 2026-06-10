import { useEffect, useState } from 'react';
import { Table, Card, Input, DatePicker, Button, Drawer, Tag, Space, Pagination, Typography } from 'antd';
import { SearchOutlined, EyeOutlined } from '@ant-design/icons';
import dayjs, { type Dayjs } from 'dayjs';
import { useAuditThreads, useThreadMessages } from '../../hooks/useThreads';
import type { ThreadAuditItem, ThreadMessageItem } from '../../api/threads';

const { Text, Paragraph } = Typography;

function MessageBubble({ message }: { message: ThreadMessageItem }) {
  const isUser = message.role === 'user';
  const isAssistant = message.role === 'assistant';

  const bubbleBg = isUser ? '#E6F7FF' : isAssistant ? '#F6FFED' : '#F5F5F5';
  const borderColor = isUser ? '#91D5FF' : isAssistant ? '#B7EB8F' : '#D9D9D9';

  function renderToolCalls(raw: Record<string, unknown>) {
    const toolCalls = raw.tool_calls as Array<{ name?: string; args?: unknown }> | undefined;
    if (!toolCalls || !Array.isArray(toolCalls)) return null;
    return (
      <div style={{ marginTop: 8 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>工具调用：</Text>
        {toolCalls.map((tc, i) => (
          <Tag key={i} color="orange" style={{ marginTop: 4 }}>
            {tc.name} {tc.args ? JSON.stringify(tc.args) : ''}
          </Tag>
        ))}
      </div>
    );
  }

  return (
    <div
      style={{
        background: bubbleBg,
        border: `1px solid ${borderColor}`,
        borderRadius: 8,
        padding: 12,
        marginBottom: 8,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <Tag color={isUser ? 'blue' : isAssistant ? 'green' : 'default'}>{message.role}</Tag>
        <Text type="secondary" style={{ fontSize: 12 }}>
          {dayjs(message.created_at).format('YYYY-MM-DD HH:mm:ss')}
          {message.token_count != null && ` · ${message.token_count} tokens`}
        </Text>
      </div>
      {message.content && (
        <Paragraph style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{message.content}</Paragraph>
      )}
      {message.raw_content && renderToolCalls(message.raw_content)}
    </div>
  );
}

export default function ThreadListPage() {
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs] | null>(null);
  const [selectedThread, setSelectedThread] = useState<ThreadAuditItem | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [msgPage, setMsgPage] = useState(1);
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  const threads = useAuditThreads({
    page,
    page_size: pageSize,
    search: search || undefined,
    start_date: dateRange?.[0]?.format('YYYY-MM-DD') || undefined,
    end_date: dateRange?.[1]?.format('YYYY-MM-DD') || undefined,
  });

  const messages = useThreadMessages({
    thread_id: selectedThread?.id ?? '',
    page: msgPage,
    page_size: 20,
  });

  useEffect(() => {
    if (drawerOpen && selectedThread) {
      setMsgPage(1);
    }
  }, [drawerOpen, selectedThread]);

  function handleSearch() {
    setSearch(searchInput);
    setPage(1);
  }

  function handleView(record: ThreadAuditItem) {
    setSelectedThread(record);
    setDrawerOpen(true);
    setMsgPage(1);
  }

  if (!mounted) return null;

  const columns = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      render: (text: string | null) => text || <Text type="secondary">无标题</Text>,
    },
    {
      title: '所属用户',
      key: 'user',
      render: (_: unknown, record: ThreadAuditItem) =>
        record.display_name || record.username || record.user_id,
    },
    {
      title: '消息数',
      dataIndex: 'message_count',
      key: 'message_count',
      width: 100,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const color = status === 'active' ? 'green' : status === 'archived' ? 'default' : 'blue';
        return <Tag color={color}>{status}</Tag>;
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss'),
    },
    {
      title: '最后活跃',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 180,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss'),
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: unknown, record: ThreadAuditItem) => (
        <Button type="link" icon={<EyeOutlined />} onClick={() => handleView(record)}>查看</Button>
      ),
    },
  ];

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <Input.Search
            placeholder="搜索对话标题"
            value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
            onSearch={handleSearch}
            enterButton={<Button type="primary" icon={<SearchOutlined />}>搜索</Button>}
            style={{ width: 300 }}
          />
          <DatePicker.RangePicker
            value={dateRange}
            onChange={dates => {
              setDateRange(dates as [Dayjs, Dayjs] | null);
              setPage(1);
            }}
          />
        </Space>
      </Card>

      <Table
        columns={columns}
        dataSource={threads.data?.items ?? []}
        rowKey="id"
        loading={threads.isLoading}
        pagination={{
          current: page,
          pageSize,
          total: threads.data?.total ?? 0,
          showTotal: total => `共 ${total} 条`,
          onChange: (p) => setPage(p),
        }}
      />

      <Drawer
        title={selectedThread?.title || '对话详情'}
        open={drawerOpen}
        onClose={() => { setDrawerOpen(false); setSelectedThread(null); }}
        width={640}
      >
        {selectedThread && (
          <div>
            <div style={{ marginBottom: 16 }}>
              <Text type="secondary">用户：{selectedThread.display_name || selectedThread.username}</Text>
              <br />
              <Text type="secondary">创建时间：{dayjs(selectedThread.created_at).format('YYYY-MM-DD HH:mm:ss')}</Text>
            </div>
            {messages.data?.items.map(msg => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {messages.data && messages.data.total > 20 && (
              <div style={{ textAlign: 'center', marginTop: 16 }}>
                <Pagination
                  current={msgPage}
                  pageSize={20}
                  total={messages.data.total}
                  onChange={p => setMsgPage(p)}
                  showTotal={total => `共 ${total} 条消息`}
                  size="small"
                />
              </div>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
}
