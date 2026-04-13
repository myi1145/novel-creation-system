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

export function BlueprintEditorPage() {
  const { projectId = '', blueprintId = '' } = useParams();
  const navigate = useNavigate();
  const [titleHint, setTitleHint] = useState('');
  const [summary, setSummary] = useState('');
  const [advancesText, setAdvancesText] = useState('');
  const [risksText, setRisksText] = useState('');
  const [editReason, setEditReason] = useState('');
  const [history, setHistory] = useState<Record<string, unknown>[]>([]);
  const [sceneIds, setSceneIds] = useState<string[]>([]);
  const [draftId, setDraftId] = useState('');
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isDecomposing, setIsDecomposing] = useState(false);
  const [isGeneratingDraft, setIsGeneratingDraft] = useState(false);

  const lastDraftStorageKey = useMemo(() => `workbench:${projectId}:lastDraftId`, [projectId]);

  const load = async () => {
    if (!projectId || !blueprintId) return;
    setIsLoading(true);
    setError('');
    try {
      const [blueprint, stateHistory] = await Promise.all([
        api.getBlueprint(projectId, blueprintId),
        api.getBlueprintStateHistory(projectId, blueprintId),
      ]);
      setTitleHint(String(blueprint.title_hint || ''));
      setSummary(String(blueprint.summary || ''));
      setAdvancesText(toMultiline(blueprint.advances));
      setRisksText(toMultiline(blueprint.risks));
      setHistory(stateHistory);
    } catch (e) {
      setError(e instanceof Error ? e.message : '读取蓝图失败');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [blueprintId, projectId]);

  const save = async () => {
    if (isSaving) return;
    if (!editReason.trim()) {
      setError('请填写 edit_reason');
      return;
    }
    setIsSaving(true);
    setFeedback('');
    setError('');
    try {
      const updated = await api.manualEditBlueprint(blueprintId, {
        project_id: projectId,
        title_hint: titleHint,
        summary: summary,
        advances: parseMultiline(advancesText),
        risks: parseMultiline(risksText),
        edit_reason: editReason,
        edited_by: 'frontend_user',
      });
      setTitleHint(String(updated.title_hint || titleHint));
      setSummary(String(updated.summary || summary));
      setAdvancesText(toMultiline(updated.advances));
      setRisksText(toMultiline(updated.risks));
      setFeedback('蓝图人工修订已保存，可继续场景拆解与草稿生成。');
      setEditReason('');
      const stateHistory = await api.getBlueprintStateHistory(projectId, blueprintId);
      setHistory(stateHistory);
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败');
    } finally {
      setIsSaving(false);
    }
  };

  const decompose = async () => {
    if (isDecomposing) return;
    setIsDecomposing(true);
    setFeedback('');
    setError('');
    try {
      const scenes = await api.decomposeScenes({ project_id: projectId, blueprint_id: blueprintId });
      const ids = scenes.map((item) => String(item.id));
      setSceneIds(ids);
      setFeedback(`场景拆解完成，scene 数量：${ids.length}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : '场景拆解失败');
    } finally {
      setIsDecomposing(false);
    }
  };

  const generateDraft = async () => {
    if (isGeneratingDraft) return;
    setIsGeneratingDraft(true);
    setFeedback('');
    setError('');
    try {
      const draft = await api.generateDraft({
        project_id: projectId,
        blueprint_id: blueprintId,
        scene_ids: sceneIds,
      });
      const nextDraftId = String(draft.id || '');
      setDraftId(nextDraftId);
      if (nextDraftId) {
        window.localStorage.setItem(lastDraftStorageKey, nextDraftId);
      }
      setFeedback(`草稿生成成功，draft_id=${nextDraftId}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : '草稿生成失败');
    } finally {
      setIsGeneratingDraft(false);
    }
  };

  return (
    <div>
      <h2>蓝图人工修订</h2>
      <div className="panel">project_id={projectId} / blueprint_id={blueprintId}</div>

      <div className="panel">
        <label>
          标题提示（title_hint）
          <input value={titleHint} onChange={(e) => setTitleHint(e.target.value)} disabled={isLoading} />
        </label>
        <label>
          本章摘要（summary）
          <textarea value={summary} onChange={(e) => setSummary(e.target.value)} rows={6} disabled={isLoading} />
        </label>
        <label>
          推进点（advances，每行一条）
          <textarea value={advancesText} onChange={(e) => setAdvancesText(e.target.value)} rows={5} disabled={isLoading} />
        </label>
        <label>
          风险点（risks，每行一条）
          <textarea value={risksText} onChange={(e) => setRisksText(e.target.value)} rows={5} disabled={isLoading} />
        </label>
        <label>
          edit_reason（必填）
          <textarea value={editReason} onChange={(e) => setEditReason(e.target.value)} rows={3} placeholder="说明你为何编辑该蓝图" />
        </label>
        <button onClick={() => void save()} disabled={isSaving || isLoading}>{isSaving ? '保存中...' : '保存蓝图人工修订'}</button>
      </div>

      <div className="panel">
        <h3>继续主链</h3>
        <button onClick={() => void decompose()} disabled={isDecomposing}>{isDecomposing ? '场景拆解中...' : '继续场景拆解'}</button>
        <button onClick={() => void generateDraft()} disabled={isGeneratingDraft}>{isGeneratingDraft ? '草稿生成中...' : '继续生成草稿'}</button>
        <div>scene_ids: {sceneIds.join('，') || '-'}</div>
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
        <h3>蓝图人工编辑历史（最小审计）</h3>
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
