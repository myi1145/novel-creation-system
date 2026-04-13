import { FormEvent, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ActionFailure, ActionSuccess, LoadingState } from '../components/Status';

export function DraftEditorPage() {
  const { projectId = '', draftId = '' } = useParams();
  const navigate = useNavigate();
  const [content, setContent] = useState('');
  const [status, setStatus] = useState('');
  const [editReason, setEditReason] = useState('');
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const lastDraftStorageKey = useMemo(() => `workbench:${projectId}:lastDraftId`, [projectId]);

  useEffect(() => {
    if (!projectId || !draftId) return;
    let mounted = true;
    setIsLoading(true);
    setError('');
    void api
      .getDraft(projectId, draftId)
      .then((draft) => {
        if (!mounted) return;
        setContent(String(draft.content || ''));
        setStatus(String(draft.status || '-'));
      })
      .catch((e) => {
        if (!mounted) return;
        setError(e instanceof Error ? e.message : '读取草稿失败');
      })
      .finally(() => {
        if (mounted) setIsLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [draftId, projectId]);

  const onSave = async (event: FormEvent) => {
    event.preventDefault();
    if (isSaving) return;
    setFeedback('');
    setError('');
    if (!editReason.trim()) {
      setError('请填写 edit_reason 后再保存');
      return;
    }
    setIsSaving(true);
    try {
      const updated = await api.manualEditDraft(draftId, {
        project_id: projectId,
        content,
        edit_reason: editReason.trim(),
        edited_by: 'frontend_user',
      });
      setStatus(String(updated.status || '-'));
      window.localStorage.setItem(lastDraftStorageKey, String(updated.id || draftId));
      setFeedback('保存成功。可回 Gate 重新审查，再继续 ChangeSet → Publish。');
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div>
      <h2>草稿人工编辑</h2>
      <div className="panel">project_id={projectId} / draft_id={draftId} / status={status || '-'}</div>
      {isLoading ? (
        <LoadingState text="草稿加载中..." />
      ) : (
        <form className="panel" onSubmit={onSave}>
          <label>
            draft.content
            <textarea value={content} onChange={(e) => setContent(e.target.value)} rows={18} style={{ width: '100%' }} />
          </label>
          <label>
            edit_reason
            <input value={editReason} onChange={(e) => setEditReason(e.target.value)} placeholder="说明本次人工修订原因" />
          </label>
          <button type="submit" disabled={isSaving}>{isSaving ? '保存中...' : '保存人工修订'}</button>
        </form>
      )}
      {feedback && <ActionSuccess text={feedback} />}
      {error && <ActionFailure text={error} />}
      <div className="panel">
        <div className="project-nav">
          <Link to={`/projects/${projectId}/gates`}>回 Gate 重新审查</Link>
          <Link to={`/projects/${projectId}/changesets`}>去 ChangeSet</Link>
          <Link to={`/projects/${projectId}/published`}>去 Publish</Link>
          <button type="button" onClick={() => navigate(`/projects/${projectId}/workbench`)}>回工作台</button>
        </div>
      </div>
    </div>
  );
}
