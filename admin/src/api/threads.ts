import apiClient from './client';

export interface ThreadAuditItem {
  id: string;
  user_id: string;
  title: string | null;
  status: string;
  message_count: number;
  created_at: string;
  updated_at: string;
  username: string | null;
  display_name: string | null;
}

export interface ThreadAuditListResponse {
  items: ThreadAuditItem[];
  total: number;
}

export interface ThreadMessageItem {
  id: string;
  thread_id: string;
  role: string;
  content: string | null;
  raw_content: Record<string, unknown> | null;
  token_count: number | null;
  created_at: string;
}

export interface ThreadMessageListResponse {
  items: ThreadMessageItem[];
  total: number;
}

export interface ThreadStatsResponse {
  total_threads: number;
  total_messages: number;
  active_users: number;
}

export interface DailyStatsPoint {
  date: string;
  thread_count: number;
}

export interface DailyMessageStatsPoint {
  date: string;
  message_count: number;
}

export interface ThreadStatsChartResponse {
  thread_stats: DailyStatsPoint[];
  message_stats: DailyMessageStatsPoint[];
}

export async function listAuditThreads(params: {
  page: number;
  page_size: number;
  user_id?: string;
  start_date?: string;
  end_date?: string;
  search?: string;
}): Promise<ThreadAuditListResponse> {
  const res = await apiClient.get('/api/admin/audit/threads', { params });
  return res.data;
}

export async function getThreadStats(params: {
  start_date?: string;
  end_date?: string;
  quick?: string;
}): Promise<ThreadStatsResponse> {
  const res = await apiClient.get('/api/admin/audit/threads/stats', { params });
  return res.data;
}

export async function getThreadStatsChart(params: {
  start_date?: string;
  end_date?: string;
  quick?: string;
}): Promise<ThreadStatsChartResponse> {
  const res = await apiClient.get('/api/admin/audit/threads/stats/chart', { params });
  return res.data;
}

export async function getThreadMessages(params: {
  thread_id: string;
  page: number;
  page_size: number;
}): Promise<ThreadMessageListResponse> {
  const res = await apiClient.get(`/api/admin/audit/threads/${params.thread_id}/messages`, {
    params: { page: params.page, page_size: params.page_size },
  });
  return res.data;
}
