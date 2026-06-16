import apiClient from './client';
import type { AgentShareRecord, AgentShareStatus } from '../types';

export interface AgentShareRecordListParams {
  page: number;
  page_size: number;
  source_owner_id?: string;
  target_user_id?: string;
  source_agent_name?: string;
  target_agent_name?: string;
  status?: AgentShareStatus;
  created_from?: string;
  created_to?: string;
}

export interface AgentShareRecordListResponse {
  items: AgentShareRecord[];
  total: number;
  page: number;
  page_size: number;
}

export async function listAgentShareRecords(
  params: AgentShareRecordListParams,
): Promise<AgentShareRecordListResponse> {
  const res = await apiClient.get('/api/admin/agent-share-records', { params });
  return res.data;
}
