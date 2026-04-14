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
  const [dependencyItems, setDependencyItems] = useState<Record<string, unknown>[]>([]);
  const [isRecomputing, setIsRecomputing] = useState(false);
  const lastDraftStorageKey = useMemo(() => `workbench:${projectId}:lastDraftId`, [projectId]);

  const load = async () => {
    if (!projectId || !sceneId) return;
    setIsLoading(true);
    setError('');
    try {
      const [scene, stateHistory] = await Promise.all([api.getScene(projectId, sceneId), api.getSceneStateHistory(projectId, sceneId)]);
      setSceneGoal(String(scene.场景目标 || ''));
      setParticipantsText(toMultiline(scene.participating_entities));
      setConflictType(String(scene.冲突类型 || ''));
      setEmotionalCurve(String(scene.情绪曲线 || ''));
      setInformationDelta(String(scene.信息变化 || ''));
      setBlueprintId(String(scene.blueprint_id || ''));
      setHistory(stateHistory);
      const dependency = await api.getDependencyStatus({ project_id: projectId, scene_id: sceneId });
      setDependencyItems(Array.isArray(dependency.items) ? (dependency.items as Record<string, unknown>[]) : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : '读取场景失败');
    } finally {
      setIsLoading(false);
    }
  };

  const recomputeDraft = async () => {
    if (isRecomputing) return;
    setIsRecomputing(true);
    setFeedback('');
    setError('');
    try {
      await api.recomputeDependencies({
        project_id: projectId,
        scene_id: sceneId,
        source_type: 'scene',
        source_id: sceneId,
        action: 'recompute_draft',
        confirmed_by: 'frontend_user',
      });
      const dependency = await api.getDependencyStatus({ project_id: projectId, scene_id: sceneId });
      setDependencyItems(Array.isArray(dependency.items) ? (dependency.items as Record<string, unknown>[]) : []);
      setFeedback('已确认重跑草稿生成。');
    } catch (e) {
      setError(e instanceof Error ? e.message : '重跑失败');
    } finally {
      setIsRecomputing(false);
    }
  };

  useEffect(() => {
    void load();
  }, [projectId, sceneId]);

  const onSave = async () => {
    if (isSaving) return;
    if (!editReason.trim()) {
      setError('请填写修订原因（edit_reason）');
      return;
    }
    setIsSaving(true);
    setFeedback('');
    setError('');
    try {
      const updated = await api.manualEditScene(sceneId, {
        project_id: projectId,
        场景目标: sceneGoal,
        participating_entities: parseMultiline(participantsText),
        冲突类型: conflictType,
        情绪曲线: emotionalCurve,
        信息变化: informationDelta,
        edit_reason: editReason,
        edited_by: 'frontend_user',
      });
      setSceneGoal(String(updated.场景目标 || sceneGoal));
      setParticipantsText(toMultiline(updated.participating_entities));
      setConflictType(String(updated.冲突类型 || conflictType));
      setEmotionalCurve(String(updated.情绪曲线 || emotionalCurve));
      setInformationDelta(String(updated.信息变化 || informationDelta));
      setFeedback('场景人工修订已保存。请重新生成草稿，再继续质量检查 → 变更提案 → 发布章节。');
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
      <h2>场景安排人工修订</h2>
      <div className="panel">用于把章节蓝图拆成具体场景，并支持人工修订后继续生成章节草稿。</div>
      <div className="panel">project_id={projectId} / scene_id={sceneId} / blueprint_id={blueprintId || '-'}</div>
      <div className="panel">
        <label>
          场景目标
          <textarea value={sceneGoal} onChange={(e) => setSceneGoal(e.target.value)} rows={5} disabled={isLoading} />
        </label>
        <label>
          参与角色（每行一个）
          <textarea value={participantsText} onChange={(e) => setParticipantsText(e.target.value)} rows={5} disabled={isLoading} />
        </label>
        <label>
          冲突类型
          <input value={conflictType} onChange={(e) => setConflictType(e.target.value)} disabled={isLoading} />
        </label>
        <label>
          情绪曲线
          <input value={emotionalCurve} onChange={(e) => setEmotionalCurve(e.target.value)} disabled={isLoading} />
        </label>
        <label>
          信息变化
          <textarea value={informationDelta} onChange={(e) => setInformationDelta(e.target.value)} rows={4} disabled={isLoading} />
        </label>
        <label>
          修订原因（edit_reason，必填）
          <textarea value={editReason} onChange={(e) => setEditReason(e.target.value)} rows={3} placeholder="说明为什么编辑该场景" />
        </label>
        <button onClick={() => void onSave()} disabled={isSaving || isLoading}>{isSaving ? '保存中...' : '保存人工修订场景'}</button>
      </div>

      <div className="panel">
        <h3>下游内容可能已过期</h3>
        {dependencyItems.length === 0 ? <div>当前场景没有检测到下游内容过期项。</div> : (
          <ul>
            {dependencyItems.map((item) => (
              <li key={String(item.stale_id || Math.random())}>
                影响={String(item.affected_type || '-')} / 原因={String(item.reason || '-')}
              </li>
            ))}
          </ul>
        )}
        <button onClick={() => void recomputeDraft()} disabled={isRecomputing || dependencyItems.length === 0}>
          {isRecomputing ? '执行中...' : '重新生成下游内容：章节草稿'}
        </button>
        <div>重新生成不会自动发布章节，也不会自动写入正式设定。</div>
      </div>

      <div className="panel">
        <h3>继续主链</h3>
        <button onClick={() => void generateDraft()} disabled={!blueprintId || isGeneratingDraft}>
          {isGeneratingDraft ? '草稿生成中...' : '基于该场景继续生成草稿'}
        </button>
        <div className="project-nav">
          <Link to={`/projects/${projectId}/workbench`}>回工作台</Link>
          <Link to={`/projects/${projectId}/gates`}>去质量检查</Link>
          <Link to={`/projects/${projectId}/changesets`}>去变更提案</Link>
          <Link to={`/projects/${projectId}/published`}>去发布章节</Link>
          {draftId ? <Link to={`/projects/${projectId}/drafts/${draftId}/edit`}>人工修订草稿</Link> : null}
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
