import { useQuery } from '@tanstack/react-query';
import {
  getThreadStats,
  getThreadStatsChart,
  listAuditThreads,
  getThreadMessages,
} from '../api/threads';

export function useThreadStats(params: {
  start_date?: string;
  end_date?: string;
  quick?: string;
}) {
  return useQuery({
    queryKey: ['threadStats', params],
    queryFn: () => getThreadStats(params),
  });
}

export function useThreadStatsChart(params: {
  start_date?: string;
  end_date?: string;
  quick?: string;
}) {
  return useQuery({
    queryKey: ['threadStatsChart', params],
    queryFn: () => getThreadStatsChart(params),
  });
}

export function useAuditThreads(params: {
  page: number;
  page_size: number;
  user_id?: string;
  start_date?: string;
  end_date?: string;
  search?: string;
}) {
  return useQuery({
    queryKey: ['auditThreads', params],
    queryFn: () => listAuditThreads(params),
  });
}

export function useThreadMessages(params: {
  thread_id: string;
  page: number;
  page_size: number;
}) {
  return useQuery({
    queryKey: ['threadMessages', params],
    queryFn: () => getThreadMessages(params),
    enabled: !!params.thread_id,
  });
}
