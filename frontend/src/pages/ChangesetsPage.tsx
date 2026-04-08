import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ApiError } from '../api/http';
import { ActionFailure, ActionSuccess, EmptyState, LoadingState } from '../components/Status';
import { toActionErrorMessage } from '../utils/actionError';

export function ChangesetsPage() {
  const { projectId = '' } = useParams();
  const [items, setItems] = useState<Awaited<ReturnType<typeof api.listChangeSets>>>([]);
  const [loading, setLoading] = useState(false);
  const [draftId, setDraftId] = useState('');
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');
  const [isCreatingFromDraft, setIsCreatingFromDraft] = useState(false);
  const [runningActionById, setRunningActionById] = useState<Record<string, 'approve' | 'reject' | 'apply' | 'rollback' | undefined>>({});

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

  const run = async (fn: () => Promise<unknown>, message: string, actionLabel: string) => {
    setFeedback('');
    setError('');
    try {
      await fn();
      setFeedback(message);
      await reload();
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) {
        setError(`${actionLabel}失败，请确认 ChangeSet 状态与参数后重试。`);
        return;
      }
      setError(toActionErrorMessage(actionLabel, e, '请确认当前提议状态是否允许该操作。'));
    }
  };

  const scoped = useMemo(() => items.filter((cs) => String(cs.project_id || '') === projectId), [items, projectId]);
  const unknownProjectItems = useMemo(() => items.filter((cs) => !cs.project_id), [items]);

  return (
    <div>
      <h2>ChangeSet 审批页</h2>
      <div className="panel">项目域：{projectId || '-'}</div>
      <div className="panel">
        <input value={draftId} onChange={(e) => setDraftId(e.target.value)} placeholder="draft_id" />
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
                  '已生成 ChangeSet 提议',
                  '从草稿生成 ChangeSet 提议',
                );
              } finally {
                setIsCreatingFromDraft(false);
              }
            })()
          }
        >
          {isCreatingFromDraft ? '生成中...' : '从草稿生成提议'}
        </button>
      </div>

      {isCreatingFromDraft && <LoadingState text="正在从草稿生成 ChangeSet 提议..." />}
      {feedback && <ActionSuccess text={feedback} />}
      {error && <ActionFailure text={error} />}
      {loading && <LoadingState text="ChangeSet 加载中" />}

      {!loading && (
        <div className="panel">
          已按返回字段 `project_id` 过滤，仅展示当前项目数据。当前项目命中 {scoped.length} 条，接口总返回 {items.length} 条。
          {unknownProjectItems.length > 0 && (
            <div>其中有 {unknownProjectItems.length} 条记录缺少 project_id，已按最小退化策略排除，不在本页展示。</div>
          )}
        </div>
      )}

      {!loading && scoped.length === 0 && <EmptyState text="当前项目暂无 ChangeSet" />}
      <ul>
        {scoped.map((cs) => (
          <li key={cs.id} className="panel">
            <div>
              ID: {cs.id} / 项目: {String(cs.project_id || '-')} / 状态: {String(cs.status)}
            </div>
            <pre>{JSON.stringify(cs.patch_operations ?? [], null, 2)}</pre>
            <button
              disabled={Boolean(runningActionById[cs.id])}
              onClick={() =>
                void (async () => {
                  if (runningActionById[cs.id]) return;
                  setRunningActionById((prev) => ({ ...prev, [cs.id]: 'approve' }));
                  try {
                    await run(() => api.approveChangeSet(cs.id, 'frontend_reviewer'), '已审批', '审批 ChangeSet');
                  } finally {
                    setRunningActionById((prev) => ({ ...prev, [cs.id]: undefined }));
                  }
                })()
              }
            >
              {runningActionById[cs.id] === 'approve' ? '审批中...' : '审批'}
            </button>
            <button
              disabled={Boolean(runningActionById[cs.id])}
              onClick={() =>
                void (async () => {
                  if (runningActionById[cs.id]) return;
                  setRunningActionById((prev) => ({ ...prev, [cs.id]: 'reject' }));
                  try {
                    await run(() => api.rejectChangeSet(cs.id, 'frontend_reviewer', '不通过'), '已驳回', '驳回 ChangeSet');
                  } finally {
                    setRunningActionById((prev) => ({ ...prev, [cs.id]: undefined }));
                  }
                })()
              }
            >
              {runningActionById[cs.id] === 'reject' ? '驳回中...' : '驳回'}
            </button>
            <button
              disabled={Boolean(runningActionById[cs.id])}
              onClick={() =>
                void (async () => {
                  if (runningActionById[cs.id]) return;
                  setRunningActionById((prev) => ({ ...prev, [cs.id]: 'apply' }));
                  try {
                    await run(() => api.applyChangeSet(cs.id), '已应用', '应用 ChangeSet');
                  } finally {
                    setRunningActionById((prev) => ({ ...prev, [cs.id]: undefined }));
                  }
                })()
              }
            >
              {runningActionById[cs.id] === 'apply' ? '应用中...' : '应用'}
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
                      '已回滚',
                      '回滚 ChangeSet',
                    );
                  } finally {
                    setRunningActionById((prev) => ({ ...prev, [cs.id]: undefined }));
                  }
                })()
              }
            >
              {runningActionById[cs.id] === 'rollback' ? '回滚中...' : '回滚'}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
