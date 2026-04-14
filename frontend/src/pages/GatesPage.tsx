import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { mergeProjectChainState } from '../features/projectState';
import { api } from '../api/client';
import { ApiError } from '../api/http';
import { ActionFailure, ActionSuccess, BlockedState, EmptyState } from '../components/Status';
import { toActionErrorMessage } from '../utils/actionError';

const DEFAULT_GATE_NAMES = ['schema_gate', 'canon_gate', 'narrative_gate', 'style_gate'] as const;

function toGateSummary(result: Record<string, unknown>): string[] {
  const checks = Array.isArray(result.checks) ? result.checks : [];
  if (checks.length > 0) {
    return checks.slice(0, 4).map((check) => {
      const item = check as Record<string, unknown>;
      return `${String(item.title || item.key || '检查项')}: ${String(item.message || item.status || '已完成')}`;
    });
  }
  const summary = String(result.summary || '').trim();
  if (summary) return [summary];
  return ['质量检查已完成，请继续查看结果并决定是否需要人工修订。'];
}

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
    setFeedback('');
    setError('');
    const sanitizedDraftId = draftId.trim();
    if (!sanitizedDraftId) {
      setError('请先选择要检查的章节草稿。');
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
      mergeProjectChainState(projectId, { draftId: sanitizedDraftId });
      setFeedback('质量检查完成。若有问题请先人工修订草稿，通过后再生成变更提案。');
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) {
        setError('执行质量检查失败，请确认草稿可用后重试。');
      } else {
        setError(toActionErrorMessage('执行质量检查', e, '请稍后重试。'));
      }
    } finally {
      setIsRunningGate(false);
    }
  };

  if (!projectId) return <BlockedState text="缺少项目上下文" />;

  return <div><h2>质量检查</h2>
    <div className="panel">用于检查章节草稿是否满足发布前要求。</div>
    <div className="panel">
      <input placeholder="请输入草稿编号" value={draftId} onChange={(e)=>setDraftId(e.target.value)} />
      <button onClick={run} disabled={isRunningGate}>{isRunningGate ? '执行中...' : '执行质量检查'}</button>
    </div>
    {isRunningGate && <ActionSuccess text="正在执行质量检查，请稍候（约 10-30 秒）..." />}
    {feedback && <ActionSuccess text={feedback} />} {error && <ActionFailure text={error} />}
    <div className="project-nav"><Link to={`/projects/${projectId}/workbench`}>返回创作工作台</Link>{draftId ? <Link to={`/projects/${projectId}/drafts/${draftId}/edit`}>人工修订草稿</Link> : null}<Link to={`/projects/${projectId}/changesets`}>生成变更提案</Link><Link to={`/projects/${projectId}/overview`}>回项目概览</Link></div>
    {result ? (
      <div className="panel">
        <h3>质量检查结果摘要</h3>
        <ul>
          {toGateSummary(result).map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
    ) : <EmptyState text="还没有质量检查结果，请先执行质量检查。" />}
  </div>;
}
