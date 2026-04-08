import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ApiError } from '../api/http';
import { ActionFailure, ActionSuccess, BlockedState } from '../components/Status';
import { toActionErrorMessage } from '../utils/actionError';

const DEFAULT_GATE_NAMES = ['schema_gate', 'canon_gate', 'narrative_gate', 'style_gate'] as const;

export function GatesPage() {
  const { projectId = '' } = useParams();
  const [draftId, setDraftId] = useState('');
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');
  const [isRunningGate, setIsRunningGate] = useState(false);
  const lastDraftStorageKey = useMemo(() => `workbench:${projectId}:lastDraftId`, [projectId]);

  useEffect(() => {
    if (!projectId) return;
    const cached = window.localStorage.getItem(lastDraftStorageKey);
    if (cached) {
      setDraftId(cached);
    }
  }, [lastDraftStorageKey, projectId]);

  const run = async () => {
    if (isRunningGate) return;
    setFeedback(''); setError('');
    const sanitizedDraftId = draftId.trim();
    if (!sanitizedDraftId) {
      setError('请先输入有效的 draft_id');
      return;
    }
    setIsRunningGate(true);
    try {
      const data = await api.runGateReview({
        project_id: projectId,
        draft_id: sanitizedDraftId,
        gate_names: [...DEFAULT_GATE_NAMES],
      });
      window.localStorage.setItem(lastDraftStorageKey, sanitizedDraftId);
      setResult(data as Record<string, unknown>);
      setFeedback('Gate 审查完成');
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) {
        setError('Gate 审查请求失败，请检查草稿编号后重试（参数不符合后端要求）。');
      } else {
        setError(toActionErrorMessage('执行 Gate 审查', e, '请检查草稿状态或稍后重试。'));
      }
    } finally {
      setIsRunningGate(false);
    }
  };

  if (!projectId) return <BlockedState text="缺少项目上下文" />;

  return <div><h2>Gate 结果页</h2>
    <div className="panel">
      <input placeholder="draft_id" value={draftId} onChange={(e)=>setDraftId(e.target.value)} />
      <button onClick={run} disabled={isRunningGate}>{isRunningGate ? '执行中...' : '执行 Gate 审查'}</button>
    </div>
    {isRunningGate && <ActionSuccess text="正在执行 Gate 审查，请稍候..." />}
    {feedback && <ActionSuccess text={feedback} />} {error && <ActionFailure text={error} />}
    <p><Link to={`/projects/${projectId}/workbench`}>返回工作台修订</Link></p>
    <pre className="panel">{JSON.stringify(result, null, 2)}</pre>
  </div>;
}
