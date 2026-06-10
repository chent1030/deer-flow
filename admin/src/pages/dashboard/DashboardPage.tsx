import { useEffect, useState } from 'react';
import { Card, Col, Row, Statistic, DatePicker, Button, Space, Spin } from 'antd';
import { UserOutlined, ApartmentOutlined, RobotOutlined, AuditOutlined, MessageOutlined, CommentOutlined, TeamOutlined } from '@ant-design/icons';
import ReactECharts from 'echarts-for-react';
import dayjs, { type Dayjs } from 'dayjs';
import { useAuthStore } from '../../stores/auth';
import { listUsers } from '../../api/users';
import { getDepartmentTree } from '../../api/departments';
import { listSkills } from '../../api/skills';
import { SkillStatus } from '../../types';
import { useThreadStats, useThreadStatsChart } from '../../hooks/useThreads';

type QuickRange = '7d' | 'last_week' | '1m' | '6m' | '1y';

const quickRangeMap: Record<QuickRange, [Dayjs, Dayjs]> = {
  '7d': [dayjs().subtract(7, 'day'), dayjs()],
  last_week: [dayjs().subtract(1, 'week').startOf('week'), dayjs().subtract(1, 'week').endOf('week')],
  '1m': [dayjs().subtract(1, 'month'), dayjs()],
  '6m': [dayjs().subtract(6, 'month'), dayjs()],
  '1y': [dayjs().subtract(1, 'year'), dayjs()],
};

const quickRangeLabels: Record<QuickRange, string> = {
  '7d': '7天内',
  last_week: '上周',
  '1m': '一个月内',
  '6m': '半年',
  '1y': '一年',
};

export default function DashboardPage() {
  const { user } = useAuthStore();
  const [stats, setStats] = useState({ users: 0, departments: 0, pendingSkills: 0, approvedSkills: 0 });

  const [quick, setQuick] = useState<QuickRange>('7d');
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs]>(quickRangeMap['7d']);

  useEffect(() => {
    async function load() {
      try {
        const [usersRes, deptsRes, pendingRes, approvedRes] = await Promise.all([
          listUsers({ page: 1, page_size: 1 }),
          getDepartmentTree(),
          listSkills({ page: 1, page_size: 1, status: SkillStatus.PENDING_REVIEW }),
          listSkills({ page: 1, page_size: 1, status: SkillStatus.APPROVED }),
        ]);
        setStats({
          users: usersRes.total,
          departments: deptsRes.departments.length,
          pendingSkills: pendingRes.total,
          approvedSkills: approvedRes.total,
        });
      } catch {}
    }
    load();
  }, []);

  const threadStats = useThreadStats({
    start_date: dateRange[0].format('YYYY-MM-DD'),
    end_date: dateRange[1].format('YYYY-MM-DD'),
    quick,
  });

  const threadChart = useThreadStatsChart({
    start_date: dateRange[0].format('YYYY-MM-DD'),
    end_date: dateRange[1].format('YYYY-MM-DD'),
    quick,
  });

  function handleQuick(range: QuickRange) {
    setQuick(range);
    setDateRange(quickRangeMap[range]);
  }

  function handleDateChange(dates: [Dayjs | null, Dayjs | null] | null) {
    if (dates && dates[0] && dates[1]) {
      setQuick('' as QuickRange);
      setDateRange([dates[0], dates[1]]);
    }
  }

  const chartData = threadChart.data;
  const allDates = chartData
    ? [...new Set([...chartData.thread_stats.map(s => s.date), ...chartData.message_stats.map(s => s.date)])].sort()
    : [];

  const threadCountMap = Object.fromEntries((chartData?.thread_stats ?? []).map(s => [s.date, s.thread_count]));
  const messageCountMap = Object.fromEntries((chartData?.message_stats ?? []).map(s => [s.date, s.message_count]));

  const chartOption = {
    tooltip: { trigger: 'axis' as const },
    legend: { data: ['对话数', '消息数'] },
    grid: { left: 60, right: 60, bottom: 30, top: 40 },
    xAxis: { type: 'category' as const, data: allDates },
    yAxis: [
      { type: 'value' as const, name: '对话数', position: 'left' as const },
      { type: 'value' as const, name: '消息数', position: 'right' as const },
    ],
    series: [
      {
        name: '对话数',
        type: 'bar',
        data: allDates.map(d => threadCountMap[d] ?? 0),
        yAxisIndex: 0,
        itemStyle: { color: '#5B8FF9' },
      },
      {
        name: '消息数',
        type: 'line',
        data: allDates.map(d => messageCountMap[d] ?? 0),
        yAxisIndex: 1,
        smooth: true,
        itemStyle: { color: '#5AD8A6' },
      },
    ],
  };

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>欢迎，{user?.display_name || user?.username}</h2>
      <Row gutter={16}>
        <Col span={6}>
          <Card><Statistic title="用户总数" value={stats.users} prefix={<UserOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="部门数" value={stats.departments} prefix={<ApartmentOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="待审核 Skill" value={stats.pendingSkills} prefix={<AuditOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="已发布 Skill" value={stats.approvedSkills} prefix={<RobotOutlined />} /></Card>
        </Col>
      </Row>

      <Card title="对话统计" style={{ marginTop: 24 }}>
        <Space style={{ marginBottom: 16 }} wrap>
          {(Object.keys(quickRangeLabels) as QuickRange[]).map(key => (
            <Button
              key={key}
              type={quick === key ? 'primary' : 'default'}
              onClick={() => handleQuick(key)}
            >
              {quickRangeLabels[key]}
            </Button>
          ))}
          <DatePicker.RangePicker
            value={dateRange}
            onChange={handleDateChange}
          />
        </Space>

        <Row gutter={16} style={{ marginBottom: 24 }}>
          <Col span={8}>
            <Card>
              <Statistic
                title="总对话数"
                value={threadStats.data?.total_threads ?? 0}
                prefix={<MessageOutlined />}
                loading={threadStats.isLoading}
              />
            </Card>
          </Col>
          <Col span={8}>
            <Card>
              <Statistic
                title="总消息数"
                value={threadStats.data?.total_messages ?? 0}
                prefix={<CommentOutlined />}
                loading={threadStats.isLoading}
              />
            </Card>
          </Col>
          <Col span={8}>
            <Card>
              <Statistic
                title="活跃用户"
                value={threadStats.data?.active_users ?? 0}
                prefix={<TeamOutlined />}
                loading={threadStats.isLoading}
              />
            </Card>
          </Col>
        </Row>

        {threadChart.isLoading ? (
          <Spin />
        ) : (
          <ReactECharts option={chartOption} style={{ height: 400 }} />
        )}
      </Card>
    </div>
  );
}
