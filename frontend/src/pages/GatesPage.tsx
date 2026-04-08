import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ApiError } from '../api/http';
import { ActionFailure, ActionSuccess, BlockedState } from '../components/Status';

const DEFAULT_GATE_NAMES = ['schema_gate', 'canon_gate', 'narrative_gate', 'style_gate'] as const;

export function GatesPage() {
  const { projectId = '' } = useParams();
  const [draftId, setDraftId] = useState('');
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');

  const run = async () => {
    setFeedback(''); setError('');
    const sanitizedDraftId = draftId.trim();
    if (!sanitizedDraftId) {
      setError('请先输入有效的 draft_id');
      return;
    }
    try {
      const data = await api.runGateReview({
        project_id: projectId,
        draft_id: sanitizedDraftId,
        gate_names: [...DEFAULT_GATE_NAMES],
      });
      setResult(data as Record<string, unknown>);
      setFeedback('Gate 审查完成');
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) {
        setError('Gate 审查请求参数不符合后端要求，请检查 draft_id 与 gate_names 后重试');
        return;
      }
      setError(e instanceof Error ? e.message : 'Gate失败');
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
