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
  const [dependencyItems, setDependencyItems] = useState<Record<string, unknown>[]>([]);
  const [isRecomputing, setIsRecomputing] = useState(false);

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
      const dependency = await api.getDependencyStatus({ project_id: projectId, blueprint_id: blueprintId });
      setDependencyItems(Array.isArray(dependency.items) ? (dependency.items as Record<string, unknown>[]) : []);
    } catch {
      setError('加载失败，请稍后重试。');
    } finally {
      setIsLoading(false);
    }
  };

  const recompute = async (action: 'recompute_scenes' | 'recompute_draft') => {
    if (isRecomputing) return;
    setIsRecomputing(true);
    setFeedback('');
    setError('');
    try {
      await api.recomputeDependencies({
        project_id: projectId,
        blueprint_id: blueprintId,
        source_type: 'blueprint',
        source_id: blueprintId,
        action,
        confirmed_by: 'frontend_user',
      });
      const dependency = await api.getDependencyStatus({ project_id: projectId, blueprint_id: blueprintId });
      setDependencyItems(Array.isArray(dependency.items) ? (dependency.items as Record<string, unknown>[]) : []);
      setFeedback(action === 'recompute_scenes' ? '已确认重新生成场景安排。' : '已确认重新生成草稿。');
    } catch {
      setError('重新生成失败，请稍后重试。');
    } finally {
      setIsRecomputing(false);
    }
  };

  useEffect(() => {
    void load();
  }, [blueprintId, projectId]);

  const save = async () => {
    if (isSaving) return;
    if (!editReason.trim()) {
      setError('请填写修订原因（必填）。');
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
      setFeedback('蓝图人工修订已保存，可继续生成场景安排与章节草稿。');
      setEditReason('');
      const stateHistory = await api.getBlueprintStateHistory(projectId, blueprintId);
      setHistory(stateHistory);
    } catch {
      setError('保存失败，请稍后重试。');
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
      setFeedback(`场景安排生成完成，共 ${ids.length} 个场景。`);
    } catch {
      setError('场景安排生成失败，请稍后重试。');
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
      setFeedback('草稿生成成功。');
    } catch {
      setError('草稿生成失败，请稍后重试。');
    } finally {
      setIsGeneratingDraft(false);
    }
  };

  return (
    <div>
      <h2>章节蓝图人工修订</h2>
      <div className="panel">在这里调整本章剧情方向。保存后建议顺序：场景安排 → 章节草稿 → 质量检查。</div>

      <div className="panel">
        <label>
          标题提示
          <input value={titleHint} onChange={(e) => setTitleHint(e.target.value)} disabled={isLoading} />
        </label>
        <label>
          本章摘要
          <textarea value={summary} onChange={(e) => setSummary(e.target.value)} rows={6} disabled={isLoading} />
        </label>
        <label>
          推进点（每行一条）
          <textarea value={advancesText} onChange={(e) => setAdvancesText(e.target.value)} rows={5} disabled={isLoading} />
        </label>
        <label>
          风险点（每行一条）
          <textarea value={risksText} onChange={(e) => setRisksText(e.target.value)} rows={5} disabled={isLoading} />
        </label>
        <label>
          修订原因（必填）
          <textarea value={editReason} onChange={(e) => setEditReason(e.target.value)} rows={3} placeholder="说明你为何编辑该蓝图" />
        </label>
        <button onClick={() => void save()} disabled={isSaving || isLoading}>{isSaving ? '保存中...' : '人工修订蓝图并保存'}</button>
      </div>

      <div className="panel">
        <h3>下游内容可能已过期</h3>
        {dependencyItems.length === 0 ? <div>当前蓝图没有检测到下游内容可能已过期。</div> : (
          <ul>
            {dependencyItems.map((item) => (
              <li key={String(item.stale_id || Math.random())}>
                影响步骤：{String(item.affected_type || '-')}；原因：{String(item.reason || '-')}
              </li>
            ))}
          </ul>
        )}
        <button onClick={() => void recompute('recompute_scenes')} disabled={isRecomputing || dependencyItems.length === 0}>
          {isRecomputing ? '执行中...' : '重新生成场景安排'}
        </button>
        <button onClick={() => void recompute('recompute_draft')} disabled={isRecomputing || dependencyItems.length === 0}>
          {isRecomputing ? '执行中...' : '重新生成草稿'}
        </button>
        <div>说明：仅重新生成下游内容，不会自动发布章节。</div>
      </div>

      <div className="panel">
        <h3>继续主链</h3>
        <button onClick={() => void decompose()} disabled={isDecomposing}>{isDecomposing ? '场景生成中...' : '生成场景安排'}</button>
        <button onClick={() => void generateDraft()} disabled={isGeneratingDraft}>{isGeneratingDraft ? '草稿生成中...' : '基于当前场景生成章节草稿'}</button>
        <div>已生成场景数：{sceneIds.length}</div>
        <div className="project-nav">
          <Link to={`/projects/${projectId}/workbench`}>回工作台</Link>
          <Link to={`/projects/${projectId}/gates`}>下一步：质量检查</Link>
          <Link to={`/projects/${projectId}/changesets`}>下一步：变更提案</Link>
          <Link to={`/projects/${projectId}/published`}>下一步：发布章节</Link>
          {draftId ? <Link to={`/projects/${projectId}/drafts/${draftId}/edit`}>人工修订草稿</Link> : null}
          <button type="button" onClick={() => navigate(`/projects/${projectId}/workbench`)}>返回工作台继续</button>
        </div>
      </div>

      <div className="panel">
        <h3>蓝图人工修订记录</h3>
        {history.length === 0 ? (
          <EmptyState text="暂无人工修订记录。" />
        ) : (
          <ul>
            {history.map((item) => (
              <li key={String(item.id || Math.random())}>
                修订来源：{String(item.trigger_type || '-')} / 修订原因：{String(item.reason || '-')} / 修订时间：
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
