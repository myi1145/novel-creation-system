import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ActionFailure, ActionSuccess, EmptyState, LoadingState } from '../components/Status';

export function ChangesetsPage() {
  const { projectId = '' } = useParams();
  const [items, setItems] = useState<Awaited<ReturnType<typeof api.listChangeSets>>>([]);
  const [loading, setLoading] = useState(false);
  const [draftId, setDraftId] = useState('');
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');

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

  const projectItems = useMemo(
    () => items.filter((item) => String(item.project_id || '') === projectId),
    [items, projectId],
  );

  const run = async (fn: () => Promise<unknown>, message: string) => {
    setFeedback('');
    setError('');
    try {
      await fn();
      setFeedback(message);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : '操作失败');
    }
  };

  return (
    <div>
      <h2>ChangeSet 审批页（项目域）</h2>
      <div className="panel">
        当前 project_id: <strong>{projectId}</strong>
      </div>
      <div className="panel">
        <input value={draftId} onChange={(e) => setDraftId(e.target.value)} placeholder="draft_id" />
        <button
          onClick={() =>
            void run(
              () => api.generateDraftChangeSetProposal(draftId, { project_id: projectId, rationale: '从草稿提议', auto_create_changeset: true }),
              '已生成 ChangeSet 提议',
            )
          }
        >
          从草稿生成提议
        </button>
      </div>
      {feedback && <ActionSuccess text={feedback} />}
      {error && <ActionFailure text={error} />}
      {loading && <LoadingState text="ChangeSet 加载中" />}
      {!loading && projectItems.length === 0 && <EmptyState text="当前项目暂无 ChangeSet" />}
      <ul>
        {projectItems.map((cs) => (
          <li key={cs.id} className="panel">
            <div>ID: {cs.id} / 状态: {String(cs.status)}</div>
            <pre>{JSON.stringify(cs.patch_operations ?? [], null, 2)}</pre>
            <button onClick={() => void run(() => api.approveChangeSet(cs.id, 'frontend_reviewer'), '已审批')}>审批</button>
            <button onClick={() => void run(() => api.rejectChangeSet(cs.id, 'frontend_reviewer', '不通过'), '已驳回')}>驳回</button>
            <button onClick={() => void run(() => api.applyChangeSet(cs.id), '已应用')}>应用</button>
            <button onClick={() => void run(() => api.rollbackChangeSet(cs.id, { rolled_back_by: 'frontend_reviewer', reason: 'UI回滚' }), '已回滚')}>回滚</button>
          </li>
        ))}
      </ul>
    </div>
  );
}
