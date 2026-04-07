import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import type { ChapterBlueprint } from '../types/domain';
import { ActionFailure, ActionSuccess, EmptyState, PendingApprovalState } from '../components/Status';

const STEPS = ['目标', '蓝图', '场景', '草稿', 'Gate', 'ChangeSet', 'Publish'];

export function WorkbenchPage() {
  const { projectId = '' } = useParams();
  const [chapterNo, setChapterNo] = useState(1);
  const [goalId, setGoalId] = useState('');
  const [blueprints, setBlueprints] = useState<ChapterBlueprint[]>([]);
  const [blueprintId, setBlueprintId] = useState('');
  const [sceneIds, setSceneIds] = useState<string[]>([]);
  const [draftId, setDraftId] = useState('');
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');
  const [stateDump, setStateDump] = useState<Record<string, unknown>>({});

  const run = async (action: () => Promise<unknown>, success: string) => {
    setFeedback('');
    setError('');
    try {
      const data = await action();
      setStateDump((s) => ({ ...s, last_result: data }));
      setFeedback(success);
    } catch (e) {
      setError(e instanceof Error ? e.message : '执行失败');
    }
  };

  const reloadBlueprints = async () => {
    if (!goalId) return;
    const items = await api.listBlueprints(projectId, goalId);
    setBlueprints(items);
  };

  useEffect(() => {
    void reloadBlueprints();
  }, [goalId]);

  const createGoal = () =>
    run(async () => {
      const g = await api.createGoal({ project_id: projectId, chapter_no: chapterNo, current_volume_goal: '推进主线', previous_chapter_summary: '' });
      setGoalId(g.id);
      setBlueprintId('');
      setDraftId('');
      return g;
    }, '章节目标已创建');

  const genBlueprint = () =>
    run(async () => {
      const generated = await api.generateBlueprints({ project_id: projectId, chapter_goal_id: goalId, candidate_count: 3 });
      setBlueprints(generated);
      return generated;
    }, '蓝图候选已生成');

  const chooseBlueprint = (targetBlueprintId: string) =>
    run(async () => {
      const selected = await api.selectBlueprint({ project_id: projectId, blueprint_id: targetBlueprintId, selected_by: 'frontend_user', selection_reason: 'UI选择' });
      setBlueprintId(targetBlueprintId);
      await reloadBlueprints();
      return selected;
    }, `蓝图已选择：${targetBlueprintId}`);

  const decompose = () =>
    run(async () => {
      const scenes = await api.decomposeScenes({ project_id: projectId, blueprint_id: blueprintId });
      setSceneIds(scenes.map((s) => s.id));
      return scenes;
    }, '场景拆解已完成');

  const genDraft = () =>
    run(async () => {
      const d = await api.generateDraft({ project_id: projectId, blueprint_id: blueprintId, scene_ids: sceneIds });
      setDraftId(d.id);
      return d;
    }, '草稿已生成');

  const reviseDraft = () =>
    run(
      async () => api.reviseDraft({ project_id: projectId, draft_id: draftId, revision_instruction: '按 Gate 建议修订', revised_by: 'frontend_user' }),
      '草稿已修订',
    );

  return (
    <div>
      <h2>章节工作台</h2>
      <div className="panel">步骤：{STEPS.join(' → ')}</div>
      <div className="panel">当前章摘要：chapter_no={chapterNo}，goal={goalId || '-'}，blueprint={blueprintId || '-'}，draft={draftId || '-'}</div>
      <div className="panel">
        <label>章节号<input type="number" value={chapterNo} onChange={(e) => setChapterNo(Number(e.target.value))} /></label>
        <button onClick={createGoal}>1) 创建目标</button>
        <button onClick={genBlueprint} disabled={!goalId}>2) 生成蓝图候选</button>
        <button onClick={() => void run(reloadBlueprints, '已刷新蓝图候选')} disabled={!goalId}>刷新蓝图候选</button>
      </div>

      <div className="panel">
        <h3>蓝图候选最小选择子视图</h3>
        {blueprints.length === 0 && <EmptyState text="请先生成蓝图候选" />}
        {blueprints.map((bp) => (
          <div key={bp.id} className="panel">
            <div><strong>{String(bp.id)}</strong> {bp.selected ? '（已选中）' : ''}</div>
            <div>摘要：{String(bp.summary || '-')}</div>
            <button onClick={() => void chooseBlueprint(bp.id)}>选中该蓝图</button>
          </div>
        ))}
      </div>

      <div className="panel">
        <button onClick={decompose} disabled={!blueprintId}>4) 场景拆解</button>
        <button onClick={genDraft} disabled={!blueprintId}>5) 草稿生成</button>
        <button onClick={reviseDraft} disabled={!draftId}>6) 草稿修订</button>
      </div>

      {feedback && <ActionSuccess text={feedback} />}
      {error && <ActionFailure text={error} />}
      {draftId && <PendingApprovalState text="可进入 Gate / ChangeSet / Publish 页面继续闭环" />}
      <pre className="panel">{JSON.stringify(stateDump, null, 2)}</pre>
    </div>
  );
}
