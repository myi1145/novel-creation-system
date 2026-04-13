import { FormEvent, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ActionFailure, ActionSuccess, LoadingState } from '../components/Status';

function toLoadErrorMessage(error: unknown) {
  if (error instanceof Error && error.message.trim()) {
    return `草稿加载失败，请刷新后重试；若仍失败，请确认 draft_id 是否有效。`;
  }
  return '草稿加载失败，请稍后重试。';
}

function toSaveErrorMessage(error: unknown) {
  if (error instanceof Error && error.message.trim()) {
    return '保存失败：未能提交人工修订。请检查网络或 draft 状态后重试。';
  }
  return '保存失败，请稍后重试。';
}

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
        setError(toLoadErrorMessage(e));
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
    const trimmedEditReason = editReason.trim();
    if (!trimmedEditReason) {
      setError('请填写“人工修订原因”，用于后续 Gate / ChangeSet 判断本次改动背景。');
      return;
    }
    if (trimmedEditReason.length < 4) {
      setError('“人工修订原因”至少 4 个字，建议写清你改了什么、为什么改。');
      return;
    }
    setIsSaving(true);
    try {
      const updated = await api.manualEditDraft(draftId, {
        project_id: projectId,
        content,
        edit_reason: trimmedEditReason,
        edited_by: 'frontend_user',
      });
      setStatus(String(updated.status || '-'));
      window.localStorage.setItem(lastDraftStorageKey, String(updated.id || draftId));
      setFeedback('保存成功：已写回人工修订草稿。下一步建议回 Gate 重新审查，再继续 ChangeSet → Publish。');
    } catch (e) {
      setError(toSaveErrorMessage(e));
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div>
      <h2>ChapterDraft 人工修订</h2>
      <div className="panel">
        <div>你正在编辑的草稿：draft_id={draftId || '-'}（project_id={projectId || '-'}）</div>
        <div>当前状态：{status || '-'}</div>
        <div>本页用于人工修订草稿文本；保存后请回 Gate 重审，再继续 ChangeSet / Publish 主链。</div>
      </div>
      {isLoading ? (
        <LoadingState text="草稿加载中..." />
      ) : (
        <form className="panel" onSubmit={onSave}>
          <label>
            draft.content（草稿正文）
            <textarea value={content} onChange={(e) => setContent(e.target.value)} rows={18} style={{ width: '100%' }} />
          </label>
          <label>
            edit_reason（人工修订原因）
            <input value={editReason} onChange={(e) => setEditReason(e.target.value)} placeholder="例如：修正人物动机冲突，并补足与上一章衔接" />
          </label>
          <div>说明：`edit_reason` 会进入最小审计信息，供后续 Gate / ChangeSet 判断修订上下文。</div>
          <button type="submit" disabled={isSaving}>{isSaving ? '保存中...' : '保存人工修订'}</button>
        </form>
      )}
      {feedback && <ActionSuccess text={feedback} />}
      {error && <ActionFailure text={error} />}
      <div className="panel">
        <div className="project-nav">
          <Link to={`/projects/${projectId}/gates`}>下一步：回 Gate 重新审查</Link>
          <Link to={`/projects/${projectId}/changesets`}>然后：去 ChangeSet</Link>
          <Link to={`/projects/${projectId}/published`}>最后：去 Publish</Link>
          <button type="button" onClick={() => navigate(`/projects/${projectId}/workbench`)}>回工作台</button>
        </div>
      </div>
    </div>
  );
}
