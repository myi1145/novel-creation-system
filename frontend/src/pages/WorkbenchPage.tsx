import { FormEvent, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ApiError } from '../api/http';
import { ActionFailure, ActionSuccess, EmptyState, PendingApprovalState } from '../components/Status';
import type { ChapterBlueprint, ChapterWorkbenchState } from '../types/domain';

const STEPS = ['目标', '章节蓝图', '场景安排', '章节草稿', '质量检查', '变更提案', '发布章节'];

function toSummary(blueprint: ChapterBlueprint) {
  return {
    id: blueprint.id,
    title_hint: String(blueprint.title_hint || '-'),
    summary: String(blueprint.summary || '-'),
    advances: Array.isArray(blueprint.advances) ? blueprint.advances : [],
    risks: Array.isArray(blueprint.risks) ? blueprint.risks : [],
    selected: Boolean(blueprint.selected),
  };
}

type LastScenesPayload = {
  scene_ids: string[];
  scene_count: number;
  sample_titles: string[];
};

type LastDraftPayload = {
  draft_id: string;
  status: string;
  summary: string;
};

type CachedChapterState = {
  chapterNo?: number;
  goalId?: string;
  blueprintId?: string;
  sceneIds?: string[];
  draftId?: string;
  blueprintCandidates?: ChapterBlueprint[];
  lastScenesPayload?: LastScenesPayload | null;
  lastDraftPayload?: LastDraftPayload | null;
  lastRevisedDraftPayload?: LastDraftPayload | null;
  lastAction?: string;
  lastActionResultSummary?: string;
  lastActionError?: string;
};

export function WorkbenchPage() {
  const { projectId = '' } = useParams();
  const [chapterNo, setChapterNo] = useState(1);
  const [goalId, setGoalId] = useState('');
  const [blueprintId, setBlueprintId] = useState('');
  const [blueprintCandidates, setBlueprintCandidates] = useState<ChapterBlueprint[]>([]);
  const [sceneIds, setSceneIds] = useState<string[]>([]);
  const [draftId, setDraftId] = useState('');
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');
  const [stateDump, setStateDump] = useState<Record<string, unknown>>({});
  const [isDecomposing, setIsDecomposing] = useState(false);
  const [isGeneratingDraft, setIsGeneratingDraft] = useState(false);
  const [isRevisingDraft, setIsRevisingDraft] = useState(false);
  const [isCreatingGoal, setIsCreatingGoal] = useState(false);
  const [isGeneratingBlueprint, setIsGeneratingBlueprint] = useState(false);
  const [isSelectingBlueprint, setIsSelectingBlueprint] = useState(false);
  const [lastAction, setLastAction] = useState('');
  const [lastActionResultSummary, setLastActionResultSummary] = useState('');
  const [lastActionError, setLastActionError] = useState('');
  const [blueprintSource, setBlueprintSource] = useState<'none' | 'api' | 'cache'>('none');
  const [lastScenesPayload, setLastScenesPayload] = useState<LastScenesPayload | null>(null);
  const [lastDraftPayload, setLastDraftPayload] = useState<LastDraftPayload | null>(null);
  const [lastRevisedDraftPayload, setLastRevisedDraftPayload] = useState<LastDraftPayload | null>(null);
  const [chapterExistsHint, setChapterExistsHint] = useState('');
  const [isRehydratingChapter, setIsRehydratingChapter] = useState(false);
  const [expandedBlueprintId, setExpandedBlueprintId] = useState('');
  const [compareBlueprintA, setCompareBlueprintA] = useState('');
  const [compareBlueprintB, setCompareBlueprintB] = useState('');
  const [dependencyItems, setDependencyItems] = useState<Record<string, unknown>[]>([]);
  const [isRefreshingDependency, setIsRefreshingDependency] = useState(false);
  const [isRecomputingDependency, setIsRecomputingDependency] = useState(false);

  const chapterStorageKey = useMemo(() => `workbench:${projectId}:${chapterNo}`, [chapterNo, projectId]);
  const lastChapterStorageKey = useMemo(() => `workbench:${projectId}:lastChapterNo`, [projectId]);
  const lastDraftStorageKey = useMemo(() => `workbench:${projectId}:lastDraftId`, [projectId]);

  useEffect(() => {
    if (!projectId) return;
    const cachedChapterNo = window.localStorage.getItem(lastChapterStorageKey);
    if (!cachedChapterNo) return;
    const parsed = Number(cachedChapterNo);
    if (Number.isFinite(parsed) && parsed > 0) {
      setChapterNo(parsed);
    }
  }, [lastChapterStorageKey, projectId]);

  useEffect(() => {
    if (!projectId) return;
    window.localStorage.setItem(lastChapterStorageKey, String(chapterNo));
  }, [chapterNo, lastChapterStorageKey, projectId]);

  useEffect(() => {
    if (!projectId) return;
    const raw = window.localStorage.getItem(chapterStorageKey);
    if (!raw) return;
    try {
      const cached = JSON.parse(raw) as CachedChapterState;
      hydrateFromCache(cached);
      setFeedback(cached.lastActionResultSummary ? '已恢复当前章本地缓存状态' : '');
      setError('');
    } catch {
      setError('恢复本地缓存失败，请重新执行当前章步骤');
    }
  }, [chapterStorageKey, projectId]);

  useEffect(() => {
    if (!projectId) return;
    const payload = {
      chapterNo,
      goalId,
      blueprintId,
      sceneIds,
      draftId,
      blueprintCandidates,
      lastScenesPayload,
      lastDraftPayload,
      lastRevisedDraftPayload,
      lastAction,
      lastActionResultSummary,
      lastActionError,
    };
    window.localStorage.setItem(chapterStorageKey, JSON.stringify(payload));
  }, [
    blueprintCandidates,
    blueprintId,
    chapterNo,
    chapterStorageKey,
    draftId,
    goalId,
    lastDraftPayload,
    lastAction,
    lastActionError,
    lastActionResultSummary,
    lastRevisedDraftPayload,
    lastScenesPayload,
    projectId,
    sceneIds,
  ]);

  useEffect(() => {
    if (!projectId || !goalId) return;
    let mounted = true;
    void api
      .listBlueprints(projectId, goalId)
      .then((items) => {
        if (!mounted || items.length === 0) return;
        setBlueprintCandidates(items);
        setBlueprintSource('api');
      })
      .catch(() => undefined);
    return () => {
      mounted = false;
    };
  }, [goalId, projectId]);

  const refreshDependencyStatus = async () => {
    if (!projectId) return;
    setIsRefreshingDependency(true);
    try {
      const result = await api.getDependencyStatus({ project_id: projectId, chapter_no: chapterNo });
      setDependencyItems(Array.isArray(result.items) ? (result.items as Record<string, unknown>[]) : []);
    } catch {
      setDependencyItems([]);
    } finally {
      setIsRefreshingDependency(false);
    }
  };

  useEffect(() => {
    void refreshDependencyStatus();
  }, [chapterNo, projectId]);

  const run = async (action: () => Promise<unknown>, success: string) => {
    setFeedback('');
    setError('');
    setLastActionError('');
    setChapterExistsHint('');
    try {
      const data = await action();
      setStateDump((s) => ({ ...s, last_result: data }));
      setFeedback(success);
    } catch (e) {
      setError(e instanceof Error ? e.message : '执行失败');
    }
  };

  const hydrateFromCache = (cached: CachedChapterState) => {
    setGoalId(cached.goalId || '');
    setBlueprintId(cached.blueprintId || '');
    setSceneIds(Array.isArray(cached.sceneIds) ? cached.sceneIds : []);
    setDraftId(cached.draftId || '');
    const cachedBlueprints = Array.isArray(cached.blueprintCandidates) ? cached.blueprintCandidates : [];
    setBlueprintCandidates(cachedBlueprints);
    setBlueprintSource(cachedBlueprints.length > 0 ? 'cache' : 'none');
    setLastScenesPayload(cached.lastScenesPayload || null);
    setLastDraftPayload(cached.lastDraftPayload || null);
    setLastRevisedDraftPayload(cached.lastRevisedDraftPayload || null);
    setLastAction(cached.lastAction || '');
    setLastActionResultSummary(cached.lastActionResultSummary || '');
    setLastActionError(cached.lastActionError || '');
  };

  const hydrateFromApiState = (state: ChapterWorkbenchState) => {
    setGoalId(String(state.goal_id || ''));
    const candidates = Array.isArray(state.blueprint_candidates) ? state.blueprint_candidates : [];
    setBlueprintCandidates(candidates);
    setBlueprintSource(candidates.length > 0 ? 'api' : 'none');
    const selectedBlueprintId = String(state.selected_blueprint_id || '');
    if (selectedBlueprintId) setBlueprintId(selectedBlueprintId);
    const ids = Array.isArray(state.scene_ids) ? state.scene_ids.map((item) => String(item)) : [];
    if (ids.length > 0) {
      setSceneIds(ids);
      setLastScenesPayload((prev) => {
        const sampleTitles = Array.isArray(prev?.sample_titles) ? prev.sample_titles : [];
        return { scene_ids: ids, scene_count: ids.length, sample_titles: sampleTitles };
      });
    }
    const latestDraft = state.latest_draft;
    if (latestDraft?.id) {
      const draftSummary = String(latestDraft.summary || latestDraft.abstract || latestDraft.content_preview || '').trim();
      setDraftId(String(latestDraft.id));
      setLastDraftPayload({
        draft_id: String(latestDraft.id),
        status: String(latestDraft.status || '-'),
        summary: draftSummary || '（由恢复接口读取到草稿，但未返回摘要）',
      });
    }
  };

  const restoreCurrentChapter = async (trigger: 'manual' | 'auto') => {
    if (!projectId) return;
    setError('');
    setIsRehydratingChapter(true);
    try {
      let hasCache = false;
      let restoredGoalId = '';
      try {
        const raw = window.localStorage.getItem(chapterStorageKey);
        if (raw) {
          const cached = JSON.parse(raw) as CachedChapterState;
          hasCache = Boolean(cached.goalId || cached.blueprintId || cached.draftId || (cached.sceneIds || []).length > 0);
          if (hasCache) {
            hydrateFromCache(cached);
            restoredGoalId = cached.goalId || '';
          }
        }
      } catch {
        // ignore cache parse failure; keep trying api read.
      }
      if (restoredGoalId) {
        try {
          const items = await api.listBlueprints(projectId, restoredGoalId);
          if (items.length > 0) {
            setBlueprintCandidates(items);
            setBlueprintSource('api');
            const selected = items.find((item) => Boolean(item.selected));
            if (selected) setBlueprintId(selected.id);
          }
        } catch {
          // fallback to cache-only restore
        }
      }
      const remoteState = await api.getChapterWorkbenchState(projectId, chapterNo);
      hydrateFromApiState(remoteState);
      await refreshDependencyStatus();
      const remoteHasData = Boolean(remoteState.goal_id || (remoteState.blueprint_candidates || []).length > 0 || (remoteState.scene_ids || []).length > 0 || remoteState.latest_draft?.id);
      if (remoteHasData) {
        setLastAction('读取当前章已有内容');
        setLastActionResultSummary(`恢复阶段：${remoteState.recovery_stage || '-'}；${remoteState.recovery_hint || '已恢复当前章已有内容'}`);
        setFeedback(
          trigger === 'auto'
            ? `当前第 ${chapterNo} 章目标已存在，已自动读取已有内容：${remoteState.recovery_hint || '可继续当前章流程'}`
            : `已读取第 ${chapterNo} 章已有内容：${remoteState.recovery_hint || '可继续当前章流程'}`,
        );
      } else if (hasCache) {
        setFeedback(`已恢复第 ${chapterNo} 章本地缓存，但服务端未查到更多内容。`);
      } else {
        setFeedback(`当前第 ${chapterNo} 章暂无可恢复内容，可先创建章节目标。`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '读取当前章已有内容失败');
    } finally {
      setIsRehydratingChapter(false);
    }
  };

  const recomputeDependency = async (action: 'recompute_scenes' | 'recompute_draft') => {
    if (isRecomputingDependency || !projectId) return;
    setIsRecomputingDependency(true);
    setFeedback('');
    setError('');
    try {
      await api.recomputeDependencies({ project_id: projectId, chapter_no: chapterNo, action, confirmed_by: 'frontend_user' });
      await refreshDependencyStatus();
      setFeedback(action === 'recompute_scenes' ? '已确认重跑场景拆解。' : '已确认重跑草稿生成。');
    } catch (e) {
      setError(e instanceof Error ? e.message : '下游重跑失败');
    } finally {
      setIsRecomputingDependency(false);
    }
  };

  const createGoal = async () => {
    if (isCreatingGoal) return;
    setIsCreatingGoal(true);
    setFeedback('');
    setError('');
    setLastActionError('');
    setChapterExistsHint('');
    try {
      const g = await api.createGoal({
        project_id: projectId,
        chapter_no: chapterNo,
        current_volume_goal: '推进主线',
        previous_chapter_summary: '',
      });
      setGoalId(g.id);
      setBlueprintId('');
      setBlueprintCandidates([]);
      setStateDump((s) => ({ ...s, last_result: g }));
      setFeedback('章节目标已创建');
    } catch (e) {
      const isConflict = e instanceof ApiError && e.status === 409;
      if (!isConflict) {
        setError(e instanceof Error ? e.message : '执行失败');
        return;
      }
      setChapterExistsHint(`当前第 ${chapterNo} 章目标已存在，不能重复创建。`);
      await restoreCurrentChapter('auto');
    } finally {
      setIsCreatingGoal(false);
    }
  };

  const genBlueprint = () => {
    if (isGeneratingBlueprint) return;
    setIsGeneratingBlueprint(true);
    void run(async () => {
      const generated = await api.generateBlueprints({ project_id: projectId, chapter_goal_id: goalId, candidate_count: 3 });
      const all = await api.listBlueprints(projectId, goalId);
      const candidates = all.length > 0 ? all : generated;
      setBlueprintCandidates(candidates);
      setBlueprintSource(all.length > 0 ? 'api' : 'cache');
      return { generated_count: generated.length, loaded_count: candidates.length, candidates };
    }, '蓝图候选已生成并加载').finally(() => {
      setIsGeneratingBlueprint(false);
    });
  };

  const chooseBlueprint = (e: FormEvent) => {
    e.preventDefault();
    if (isSelectingBlueprint) return;
    setIsSelectingBlueprint(true);
    void run(
      async () =>
        api.selectBlueprint({
          project_id: projectId,
          blueprint_id: blueprintId,
          selected_by: 'frontend_user',
          selection_reason: 'Workbench 页面选择',
        }),
      '蓝图已选择',
    ).finally(() => {
      setIsSelectingBlueprint(false);
    });
  };

  const selectCandidateInUi = (candidateId: string) => {
    setBlueprintId(candidateId);
    setFeedback(`已回填 blueprint_id：${candidateId}`);
    setError('');
  };

  const decompose = () =>
    run(
      async () => {
        setIsDecomposing(true);
        setLastAction('场景拆解');
        setLastActionResultSummary('正在执行场景拆解…');
        try {
          const scenes = await api.decomposeScenes({ project_id: projectId, blueprint_id: blueprintId });
          const ids = scenes.map((s) => s.id);
          const sampleTitles = scenes
            .map((item) => String(item.title || item.scene_title || '').trim())
            .filter((item) => item.length > 0)
            .slice(0, 3);
          setSceneIds(ids);
          setLastScenesPayload({
            scene_ids: ids,
            scene_count: ids.length,
            sample_titles: sampleTitles,
          });
          setLastActionResultSummary(`场景拆解完成，生成 scene_ids 数量：${ids.length}`);
          return scenes;
        } catch (e) {
          const message = e instanceof Error ? e.message : '场景拆解失败';
          setLastActionError(`场景拆解失败：${message}`);
          throw new Error(`场景拆解失败：${message}`);
        } finally {
          setIsDecomposing(false);
        }
      },
      '场景拆解已完成',
    );

  const genDraft = () =>
    run(
      async () => {
        setIsGeneratingDraft(true);
        setLastAction('草稿生成');
        setLastActionResultSummary('正在生成草稿…');
        try {
          const d = await api.generateDraft({ project_id: projectId, blueprint_id: blueprintId, scene_ids: sceneIds });
          setDraftId(d.id);
          if (d.id) {
            window.localStorage.setItem(lastDraftStorageKey, String(d.id));
          }
          const summary = String(d.summary || d.abstract || d.content_preview || '').trim();
          setLastDraftPayload({
            draft_id: String(d.id || '-'),
            status: String(d.status || '-'),
            summary: summary || '（未返回草稿摘要）',
          });
          setLastActionResultSummary(`草稿生成完成，draft_id：${d.id}`);
          return d;
        } catch (e) {
          const message = e instanceof Error ? e.message : '草稿生成失败';
          setLastActionError(`草稿生成失败：${message}`);
          throw new Error(`草稿生成失败：${message}`);
        } finally {
          setIsGeneratingDraft(false);
        }
      },
      '草稿已生成',
    );

  const reviseDraft = () =>
    run(
      async () => {
        setIsRevisingDraft(true);
        setLastAction('草稿修订');
        setLastActionResultSummary('正在修订草稿…');
        try {
          const revised = await api.reviseDraft({
            project_id: projectId,
            draft_id: draftId,
            revision_instruction: '按 Gate 建议修订',
            revised_by: 'frontend_user',
          });
          const revisedDraftId = String(revised.id || draftId);
          const revisedSummary = String(revised.summary || revised.abstract || revised.content_preview || '').trim();
          setDraftId(revisedDraftId);
          if (revisedDraftId) {
            window.localStorage.setItem(lastDraftStorageKey, revisedDraftId);
          }
          setLastRevisedDraftPayload({
            draft_id: revisedDraftId,
            status: String(revised.status || '-'),
            summary: revisedSummary || '（未返回修订摘要）',
          });
          setLastActionResultSummary(`草稿修订完成，draft_id：${String(revised.id || draftId)}，status：${String(revised.status || '-')}`);
          return revised;
        } catch (e) {
          const message = e instanceof Error ? e.message : '草稿修订失败';
          setLastActionError(`草稿修订失败：${message}`);
          throw new Error(`草稿修订失败：${message}`);
        } finally {
          setIsRevisingDraft(false);
        }
      },
      '草稿已修订',
    );

  const selectedCompareA = blueprintCandidates.find((item) => item.id === compareBlueprintA) || null;
  const selectedCompareB = blueprintCandidates.find((item) => item.id === compareBlueprintB) || null;


  return (
    <div>
      <h2>创作工作台</h2>
      <div className="panel">用于查看当前处于哪一步，并按“目标 → 章节蓝图 → 场景安排 → 章节草稿 → 质量检查 → 变更提案 → 发布章节”继续推进。</div>
      <div className="panel">步骤：{STEPS.join(' → ')}</div>
      <div className="panel">
        <h3>下游内容可能已过期</h3>
        <button onClick={() => void refreshDependencyStatus()} disabled={isRefreshingDependency}>
          {isRefreshingDependency ? '刷新中...' : '刷新下游状态'}
        </button>
        {dependencyItems.length === 0 ? <div>当前章节没有检测到下游内容过期项。</div> : (
          <ul>
            {dependencyItems.map((item) => (
              <li key={String(item.stale_id || Math.random())}>
                来源={String(item.source_type || '-')}，影响={String(item.affected_type || '-')}，原因={String(item.reason || '-')}
              </li>
            ))}
          </ul>
        )}
        <button onClick={() => void recomputeDependency('recompute_scenes')} disabled={isRecomputingDependency || dependencyItems.length === 0}>
          {isRecomputingDependency ? '重跑中...' : '重新生成下游内容：场景安排'}
        </button>
        <button onClick={() => void recomputeDependency('recompute_draft')} disabled={isRecomputingDependency || dependencyItems.length === 0}>
          {isRecomputingDependency ? '重跑中...' : '重新生成下游内容：章节草稿'}
        </button>
        <div>重新生成不会自动发布章节，也不会绕过变更提案。</div>
      </div>
      <div className="panel">
        当前章摘要：chapter_no={chapterNo}，goal={goalId || '-'}，blueprint={blueprintId || '-'}，draft={draftId || '-'}
        ，scene_ids={sceneIds.length}，最近动作={lastAction || '-'}，最近结果={lastActionResultSummary || '-'}，最近错误=
        {lastActionError || '-'}
      </div>
      <div className="panel">
        <label>
          章节号
          <input type="number" value={chapterNo} onChange={(e) => setChapterNo(Number(e.target.value))} />
        </label>
        <button onClick={() => void createGoal()} disabled={isCreatingGoal}>
          {isCreatingGoal ? '1) 创建目标中…' : '1) 创建目标'}
        </button>
        <button onClick={() => void restoreCurrentChapter('manual')} disabled={isRehydratingChapter}>
          {isRehydratingChapter ? '读取当前章已有内容中…' : '读取当前章已有内容'}
        </button>
        <button onClick={genBlueprint} disabled={!goalId || isGeneratingBlueprint}>
          {isGeneratingBlueprint ? '2) 生成蓝图候选中…' : '2) 生成蓝图候选'}
        </button>
        <form onSubmit={chooseBlueprint}>
          <input placeholder="blueprint_id" value={blueprintId} onChange={(e) => setBlueprintId(e.target.value)} required />
          <button disabled={isSelectingBlueprint}>{isSelectingBlueprint ? '3) 选择蓝图中…' : '3) 选择蓝图'}</button>
        </form>
        <button onClick={decompose} disabled={!blueprintId || isDecomposing}>
          {isDecomposing ? '4) 场景拆解执行中…' : '4) 场景拆解'}
        </button>
        <button onClick={genDraft} disabled={!blueprintId || isGeneratingDraft}>
          {isGeneratingDraft ? '5) 草稿生成执行中…' : '5) 草稿生成'}
        </button>
        <button onClick={reviseDraft} disabled={!draftId || isRevisingDraft}>
          {isRevisingDraft ? '6) 草稿修订执行中…' : '6) 草稿修订'}
        </button>
      </div>

      <div className="panel">
        <h3>已有章节提示</h3>
        {chapterExistsHint ? (
          <div>
            <div>{chapterExistsHint}</div>
            <div>这不是系统故障，可直接读取并继续当前章流程。</div>
          </div>
        ) : (
          <EmptyState text="当前章暂无“已存在目标”冲突提示" />
        )}
      </div>

      <div className="panel">
        <h3>章节蓝图候选列表与对比</h3>
        <div>数据来源：{blueprintSource === 'api' ? '当前回读内容' : blueprintSource === 'cache' ? '最近缓存内容' : '-'}</div>
        {blueprintCandidates.length === 0 ? (
          <EmptyState text="请先执行“生成章节蓝图候选”" />
        ) : (
          <>
            <div className="panel">
              <label>对比 A
                <select value={compareBlueprintA} onChange={(e) => setCompareBlueprintA(e.target.value)}>
                  <option value="">请选择</option>
                  {blueprintCandidates.map((item) => (<option key={`a-${item.id}`} value={item.id}>{item.id}</option>))}
                </select>
              </label>
              <label>对比 B
                <select value={compareBlueprintB} onChange={(e) => setCompareBlueprintB(e.target.value)}>
                  <option value="">请选择</option>
                  {blueprintCandidates.map((item) => (<option key={`b-${item.id}`} value={item.id}>{item.id}</option>))}
                </select>
              </label>
            </div>
            {selectedCompareA && selectedCompareB && selectedCompareA.id !== selectedCompareB.id && (
              <div className="grid">
                <div className="panel">
                  <h4>对比 A：{selectedCompareA.id}</h4>
                  <div>摘要：{String(selectedCompareA.summary || '-')}</div>
                  <div>结构要点：{Array.isArray(selectedCompareA.advances) ? selectedCompareA.advances.join('；') || '-' : '-'}</div>
                  <div>冲突/风险：{Array.isArray(selectedCompareA.risks) ? selectedCompareA.risks.join('；') || '-' : '-'}</div>
                  <button onClick={() => selectCandidateInUi(selectedCompareA.id)}>选中 A 继续</button>
                </div>
                <div className="panel">
                  <h4>对比 B：{selectedCompareB.id}</h4>
                  <div>摘要：{String(selectedCompareB.summary || '-')}</div>
                  <div>结构要点：{Array.isArray(selectedCompareB.advances) ? selectedCompareB.advances.join('；') || '-' : '-'}</div>
                  <div>冲突/风险：{Array.isArray(selectedCompareB.risks) ? selectedCompareB.risks.join('；') || '-' : '-'}</div>
                  <button onClick={() => selectCandidateInUi(selectedCompareB.id)}>选中 B 继续</button>
                </div>
              </div>
            )}
            <ul>
              {blueprintCandidates.map((item) => {
                const summary = toSummary(item);
                const isExpanded = expandedBlueprintId === summary.id;
                return (
                  <li key={summary.id} className="panel">
                    <div>候选ID：{summary.id}</div>
                    <div>标题：{summary.title_hint}</div>
                    <div>后端 selected：{String(summary.selected)}</div>
                    <button onClick={() => setExpandedBlueprintId(isExpanded ? '' : summary.id)}>{isExpanded ? '收起详情' : '展开详情'}</button>
                    <button onClick={() => selectCandidateInUi(summary.id)}>设为当前章节蓝图</button>
                    <Link to={`/projects/${projectId}/blueprints/${summary.id}/edit`}>人工修订蓝图</Link>
                    {isExpanded && (
                      <div className="panel">
                        <div>摘要：{summary.summary}</div>
                        <div>推进点：{summary.advances.join('；') || '-'}</div>
                        <div>风险：{summary.risks.join('；') || '-'}</div>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </div>

      <div className="panel">
        <h3>最近场景结果（重进可见）</h3>
        {!lastScenesPayload ? (
          <EmptyState text="还没有场景安排结果，请先生成场景安排。" />
        ) : (
          <div>
            <div>场景数量：{lastScenesPayload.scene_count}</div>
            <div>scene_ids：{lastScenesPayload.scene_ids.join('，') || '-'}</div>
            <div>场景标题样例：{lastScenesPayload.sample_titles.join('；') || '-'}</div>
            <div>
              {lastScenesPayload.scene_ids.map((sceneId) => (
                <Link key={sceneId} to={`/projects/${projectId}/scenes/${sceneId}/edit`} style={{ marginRight: 8 }}>
                  编辑场景 {sceneId}
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="panel">
        <h3>最近草稿结果（重进可见）</h3>
        {!lastDraftPayload && !lastRevisedDraftPayload ? (
          <EmptyState text="还没有章节草稿结果，请先生成章节草稿。" />
        ) : (
          <div>
            {lastDraftPayload && (
              <div className="panel">
                <div>最近草稿生成：draft_id={lastDraftPayload.draft_id}</div>
                <div>status：{lastDraftPayload.status}</div>
                <div>摘要：{lastDraftPayload.summary}</div>
              </div>
            )}
            {lastRevisedDraftPayload && (
              <div className="panel">
                <div>最近草稿修订：draft_id={lastRevisedDraftPayload.draft_id}</div>
                <div>status：{lastRevisedDraftPayload.status}</div>
                <div>摘要：{lastRevisedDraftPayload.summary}</div>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="panel">
        <h3>最近动作结果</h3>
        <div>上一次执行：{lastAction || '-'}</div>
        <div>结果摘要：{lastActionResultSummary || '-'}</div>
        <div>建议下一步：{draftId ? '进入质量检查 / 变更提案 / 发布章节页面继续流程' : blueprintId ? '可继续生成场景安排或章节草稿' : goalId ? '可继续生成并选择章节蓝图' : '先创建章节目标'}</div>
      </div>

      <div className="panel">
        <h3>继续处理入口</h3>
        <div className="project-nav">
          <Link to={`/projects/${projectId}/overview`}>回项目概览</Link>
          {blueprintId ? <Link to={`/projects/${projectId}/blueprints/${blueprintId}/edit`}>人工修订蓝图</Link> : null}
          {sceneIds[0] ? <Link to={`/projects/${projectId}/scenes/${sceneIds[0]}/edit`}>人工修订场景</Link> : null}
          {draftId ? <Link to={`/projects/${projectId}/drafts/${draftId}/edit`}>人工修订草稿</Link> : null}
          <Link to={`/projects/${projectId}/gates`}>去质量检查</Link>
          <Link to={`/projects/${projectId}/changesets`}>去变更提案</Link>
          <Link to={`/projects/${projectId}/published`}>去发布章节</Link>
          <Link to={`/projects/${projectId}/chapters/${chapterNo}/release-readiness`}>发布前检查</Link>
        </div>
      </div>

      {feedback && <ActionSuccess text={feedback} />} {error && <ActionFailure text={error} />}
      {draftId && <PendingApprovalState text="可进入质量检查 / 变更提案 / 发布章节页面继续流程" />}
      <pre className="panel">{JSON.stringify(stateDump, null, 2)}</pre>
    </div>
  );
}
