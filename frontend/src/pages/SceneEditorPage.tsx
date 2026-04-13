import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ActionFailure, ActionSuccess, EmptyState } from '../components/Status';

function toMultiline(value: unknown): string {
  return Array.isArray(value) ? value.map((item) => String(item || '').trim()).filter(Boolean).join('\n') : '';
}

function parseMultiline(value: string): string[] {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter(Boolean);
}

export function SceneEditorPage() {
  const { projectId = '', sceneId = '' } = useParams();
  const navigate = useNavigate();
  const [sceneGoal, setSceneGoal] = useState('');
  const [participantsText, setParticipantsText] = useState('');
  const [conflictType, setConflictType] = useState('');
  const [emotionalCurve, setEmotionalCurve] = useState('');
  const [informationDelta, setInformationDelta] = useState('');
  const [blueprintId, setBlueprintId] = useState('');
  const [history, setHistory] = useState<Record<string, unknown>[]>([]);
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');
  const [editReason, setEditReason] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isGeneratingDraft, setIsGeneratingDraft] = useState(false);
  const [draftId, setDraftId] = useState('');
  const lastDraftStorageKey = useMemo(() => `workbench:${projectId}:lastDraftId`, [projectId]);

  const load = async () => {
    if (!projectId || !sceneId) return;
    setIsLoading(true);
    setError('');
    try {
      const [scene, stateHistory] = await Promise.all([api.getScene(projectId, sceneId), api.getSceneStateHistory(projectId, sceneId)]);
      setSceneGoal(String(scene.scene_goal || ''));
      setParticipantsText(toMultiline(scene.participating_entities));
      setConflictType(String(scene.conflict_type || ''));
      setEmotionalCurve(String(scene.emotional_curve || ''));
      setInformationDelta(String(scene.information_delta || ''));
      setBlueprintId(String(scene.blueprint_id || ''));
      setHistory(stateHistory);
    } catch (e) {
      setError(e instanceof Error ? e.message : '读取场景失败');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [projectId, sceneId]);

  const onSave = async () => {
    if (isSaving) return;
    if (!editReason.trim()) {
      setError('请填写 edit_reason');
      return;
    }
    setIsSaving(true);
    setFeedback('');
    setError('');
    try {
      const updated = await api.manualEditScene(sceneId, {
        project_id: projectId,
        scene_goal: sceneGoal,
        participating_entities: parseMultiline(participantsText),
        conflict_type: conflictType,
        emotional_curve: emotionalCurve,
        information_delta: informationDelta,
        edit_reason: editReason,
        edited_by: 'frontend_user',
      });
      setSceneGoal(String(updated.scene_goal || sceneGoal));
      setParticipantsText(toMultiline(updated.participating_entities));
      setConflictType(String(updated.conflict_type || conflictType));
      setEmotionalCurve(String(updated.emotional_curve || emotionalCurve));
      setInformationDelta(String(updated.information_delta || informationDelta));
      setFeedback('场景人工修订已保存。请重新生成草稿，再继续 Gate → ChangeSet → Publish。');
      setEditReason('');
      const stateHistory = await api.getSceneStateHistory(projectId, sceneId);
      setHistory(stateHistory);
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败');
    } finally {
      setIsSaving(false);
    }
  };

  const generateDraft = async () => {
    if (isGeneratingDraft || !blueprintId) return;
    setIsGeneratingDraft(true);
    setFeedback('');
    setError('');
    try {
      const draft = await api.generateDraft({
        project_id: projectId,
        blueprint_id: blueprintId,
        scene_ids: [sceneId],
      });
      const nextDraftId = String(draft.id || '');
      setDraftId(nextDraftId);
      if (nextDraftId) {
        window.localStorage.setItem(lastDraftStorageKey, nextDraftId);
      }
      setFeedback(`已基于当前场景重新生成草稿，draft_id=${nextDraftId}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : '生成草稿失败');
    } finally {
      setIsGeneratingDraft(false);
    }
  };

  return (
    <div>
      <h2>场景人工修订</h2>
      <div className="panel">project_id={projectId} / scene_id={sceneId} / blueprint_id={blueprintId || '-'}</div>
      <div className="panel">
        <label>
          scene_goal
          <textarea value={sceneGoal} onChange={(e) => setSceneGoal(e.target.value)} rows={5} disabled={isLoading} />
        </label>
        <label>
          participating_entities（每行一个）
          <textarea value={participantsText} onChange={(e) => setParticipantsText(e.target.value)} rows={5} disabled={isLoading} />
        </label>
        <label>
          conflict_type
          <input value={conflictType} onChange={(e) => setConflictType(e.target.value)} disabled={isLoading} />
        </label>
        <label>
          emotional_curve
          <input value={emotionalCurve} onChange={(e) => setEmotionalCurve(e.target.value)} disabled={isLoading} />
        </label>
        <label>
          information_delta
          <textarea value={informationDelta} onChange={(e) => setInformationDelta(e.target.value)} rows={4} disabled={isLoading} />
        </label>
        <label>
          edit_reason（必填）
          <textarea value={editReason} onChange={(e) => setEditReason(e.target.value)} rows={3} placeholder="说明为什么编辑该场景" />
        </label>
        <button onClick={() => void onSave()} disabled={isSaving || isLoading}>{isSaving ? '保存中...' : '保存场景人工修订'}</button>
      </div>

      <div className="panel">
        <h3>继续主链</h3>
        <button onClick={() => void generateDraft()} disabled={!blueprintId || isGeneratingDraft}>
          {isGeneratingDraft ? '草稿生成中...' : '基于该场景继续生成草稿'}
        </button>
        <div className="project-nav">
          <Link to={`/projects/${projectId}/workbench`}>回工作台</Link>
          <Link to={`/projects/${projectId}/gates`}>去 Gate</Link>
          <Link to={`/projects/${projectId}/changesets`}>去 ChangeSet</Link>
          <Link to={`/projects/${projectId}/published`}>去 Publish</Link>
          {draftId ? <Link to={`/projects/${projectId}/drafts/${draftId}/edit`}>编辑草稿</Link> : null}
          <button type="button" onClick={() => navigate(`/projects/${projectId}/workbench`)}>返回工作台继续</button>
        </div>
      </div>

      <div className="panel">
        <h3>场景人工编辑历史（最小审计）</h3>
        {history.length === 0 ? (
          <EmptyState text="暂无人工编辑记录" />
        ) : (
          <ul>
            {history.map((item) => (
              <li key={String(item.id || Math.random())}>
                trigger_type={String(item.trigger_type || '-')} / reason={String(item.reason || '-')} / edited_at=
                {String((item.transition_metadata as Record<string, unknown> | undefined)?.edited_at || item.created_at || '-')}
              </li>
            ))}
          </ul>
        )}
      </div>
      {feedback && <ActionSuccess text={feedback} />}
      {error && <ActionFailure text={error} />}
    </div>
  );
}
