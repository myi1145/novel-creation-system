import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ApiError } from '../api/http';
import { ActionFailure, ActionSuccess, EmptyState, LoadingState } from '../components/Status';
import { toActionErrorMessage } from '../utils/actionError';
import { mergeProjectChainState } from '../features/projectState';

function toChangesetStatus(status: string): string {
  if (status.includes('pending')) return '待处理';
  if (status.includes('approved')) return '已通过';
  if (status.includes('rejected')) return '已驳回';
  if (status.includes('applied')) return '已写入正式设定';
  if (status.includes('rolled_back')) return '已撤销写入';
  return status || '-';
}

export function ChangesetsPage() {
  const { projectId = '' } = useParams();
  const [items, setItems] = useState<Awaited<ReturnType<typeof api.listChangeSets>>>([]);
  const [loading, setLoading] = useState(false);
  const [draftId, setDraftId] = useState('');
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');
  const [isCreatingFromDraft, setIsCreatingFromDraft] = useState(false);
  const [runningActionById, setRunningActionById] = useState<Record<string, 'approve' | 'reject' | 'apply' | 'rollback' | undefined>>({});
  const lastDraftStorageKey = useMemo(() => `workbench:${projectId}:lastDraftId`, [projectId]);

  const reload = async () => {
    setLoading(true);
    try {
      setItems(await api.listChangeSets());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void reload();
  }, []);

  useEffect(() => {
    if (!projectId) return;
    const cached = window.localStorage.getItem(lastDraftStorageKey);
    if (cached) {
      setDraftId(cached);
    }
  }, [lastDraftStorageKey, projectId]);

  const run = async (fn: () => Promise<unknown>, message: string, actionLabel: string) => {
    setFeedback('');
    setError('');
    try {
      await fn();
      setFeedback(message);
      await reload();
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) {
        setError(`${actionLabel}失败，请确认当前提案状态后重试。`);
        return;
      }
      setError(toActionErrorMessage(actionLabel, e, '请稍后重试。'));
    }
  };

  const scoped = useMemo(() => items.filter((cs) => String(cs.project_id || '') === projectId), [items, projectId]);

  useEffect(() => {
    const hasPending = scoped.some((cs) => String(cs.status || '').toLowerCase().includes('pending'));
    mergeProjectChainState(projectId, { hasPendingChangeset: hasPending });
  }, [projectId, scoped]);

  return (
    <div>
      <h2>变更提案</h2>
      <div className="panel">用于确认哪些内容要写入正式设定。建议顺序：先生成提案，再通过/写入，然后去发布章节。</div>
      <div className="panel">
        <input value={draftId} onChange={(e) => setDraftId(e.target.value)} placeholder="请输入草稿编号" />
        <button
          disabled={isCreatingFromDraft}
          onClick={() =>
            void (async () => {
              if (isCreatingFromDraft) return;
              setIsCreatingFromDraft(true);
              try {
                await run(
                  () =>
                    api.generateDraftChangeSetProposal(draftId, {
                      project_id: projectId,
                      rationale: '从草稿提议',
                      auto_create_changeset: true,
                    }),
                  '已生成变更提案。',
                  '生成变更提案',
                );
                if (draftId.trim()) {
                  window.localStorage.setItem(lastDraftStorageKey, draftId.trim());
                }
              } finally {
                setIsCreatingFromDraft(false);
              }
            })()
          }
        >
          {isCreatingFromDraft ? '生成中...' : '生成变更提案'}
        </button>
      </div>

      {isCreatingFromDraft && <LoadingState text="正在生成变更提案..." />}
      {feedback && <ActionSuccess text={feedback} />}
      {error && <ActionFailure text={error} />}
      {loading && <LoadingState text="变更提案加载中" />}

      {!loading && scoped.length === 0 && <EmptyState text="还没有变更提案，请先从草稿生成变更提案。" />}
      <ul>
        {scoped.map((cs) => (
          <li key={cs.id} className="panel">
            <div>提案编号：{cs.id}</div>
            <div>状态：{toChangesetStatus(String(cs.status || '').toLowerCase())}</div>
            <div>变更条目数：{Array.isArray(cs.patch_operations) ? cs.patch_operations.length : 0}</div>
            <button
              disabled={Boolean(runningActionById[cs.id])}
              onClick={() =>
                void (async () => {
                  if (runningActionById[cs.id]) return;
                  setRunningActionById((prev) => ({ ...prev, [cs.id]: 'approve' }));
                  try {
                    await run(() => api.approveChangeSet(cs.id, 'frontend_reviewer'), '提案已通过。', '通过提案');
                  } finally {
                    setRunningActionById((prev) => ({ ...prev, [cs.id]: undefined }));
                  }
                })()
              }
            >
              {runningActionById[cs.id] === 'approve' ? '处理中...' : '通过提案'}
            </button>
            <button
              disabled={Boolean(runningActionById[cs.id])}
              onClick={() =>
                void (async () => {
                  if (runningActionById[cs.id]) return;
                  setRunningActionById((prev) => ({ ...prev, [cs.id]: 'reject' }));
                  try {
                    await run(() => api.rejectChangeSet(cs.id, 'frontend_reviewer', '不通过'), '提案已驳回。', '驳回提案');
                  } finally {
                    setRunningActionById((prev) => ({ ...prev, [cs.id]: undefined }));
                  }
                })()
              }
            >
              {runningActionById[cs.id] === 'reject' ? '处理中...' : '驳回提案'}
            </button>
            <button
              disabled={Boolean(runningActionById[cs.id])}
              onClick={() =>
                void (async () => {
                  if (runningActionById[cs.id]) return;
                  setRunningActionById((prev) => ({ ...prev, [cs.id]: 'apply' }));
                  try {
                    await run(() => api.applyChangeSet(cs.id), '已写入正式设定。', '写入正式设定');
                  } finally {
                    setRunningActionById((prev) => ({ ...prev, [cs.id]: undefined }));
                  }
                })()
              }
            >
              {runningActionById[cs.id] === 'apply' ? '处理中...' : '写入正式设定'}
            </button>
            <button
              disabled={Boolean(runningActionById[cs.id])}
              onClick={() =>
                void (async () => {
                  if (runningActionById[cs.id]) return;
                  setRunningActionById((prev) => ({ ...prev, [cs.id]: 'rollback' }));
                  try {
                    await run(
                      () => api.rollbackChangeSet(cs.id, { rolled_back_by: 'frontend_reviewer', reason: 'UI回滚' }),
                      '已撤销本次写入。',
                      '撤销写入',
                    );
                  } finally {
                    setRunningActionById((prev) => ({ ...prev, [cs.id]: undefined }));
                  }
                })()
              }
            >
              {runningActionById[cs.id] === 'rollback' ? '处理中...' : '撤销本次写入'}
            </button>
          </li>
        ))}
      </ul>

      <div className="panel">
        <div className="project-nav">
          <Link to={`/projects/${projectId}/objects`}>回对象页</Link>
          <Link to={`/projects/${projectId}/workbench`}>回工作台</Link>
          <Link to={`/projects/${projectId}/published`}>下一步：发布章节</Link>
          <Link to={`/projects/${projectId}/overview`}>回项目概览</Link>
        </div>
      </div>
    </div>
  );
}
