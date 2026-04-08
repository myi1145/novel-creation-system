import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ApiError } from '../api/http';
import { DEFAULT_GATE_NAMES } from '../types/api';
import { ActionFailure, ActionSuccess, BlockedState } from '../components/Status';

function formatGateError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 422) {
      const detailText = error.details ? ` 详情: ${JSON.stringify(error.details)}` : '';
      return `Gate 审查请求参数不符合后端要求，请检查 draft_id 与 gate_names。${detailText}`;
    }
    return error.message;
  }

  if (error instanceof Error) return error.message;
  return 'Gate 审查失败';
}

export function GatesPage() {
  const { projectId = '' } = useParams();
  const [draftId, setDraftId] = useState('');
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');

  const run = async () => {
    const normalizedDraftId = draftId.trim();
    setFeedback('');
    setError('');

    if (!normalizedDraftId) {
      setError('请先输入有效的 draft_id（不能为空）');
      return;
    }

    try {
      const data = await api.runGateReview({
        project_id: projectId,
        draft_id: normalizedDraftId,
        gate_names: DEFAULT_GATE_NAMES,
      });
      setResult(data as Record<string, unknown>);
      setFeedback('Gate 审查完成');
    } catch (e) {
      setError(formatGateError(e));
    }
  };

  if (!projectId) return <BlockedState text="缺少项目上下文" />;

  return <div><h2>Gate 结果页</h2>
    <div className="panel"><input placeholder="draft_id" value={draftId} onChange={(e)=>setDraftId(e.target.value)} /><button onClick={run}>执行 Gate 审查</button></div>
    {feedback && <ActionSuccess text={feedback} />} {error && <ActionFailure text={error} />}
    <p><Link to={`/projects/${projectId}/workbench`}>返回工作台修订</Link></p>
    <pre className="panel">{JSON.stringify(result, null, 2)}</pre>
  </div>;
}
