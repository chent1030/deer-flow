import { useQuery } from '@tanstack/react-query';
import { listAgentShareRecords } from '../api/agentShares';
import type { AgentShareRecordListParams } from '../api/agentShares';

export function useAgentShareRecords(params: AgentShareRecordListParams) {
  return useQuery({
    queryKey: ['agentShareRecords', params],
    queryFn: () => listAgentShareRecords(params),
  });
}
