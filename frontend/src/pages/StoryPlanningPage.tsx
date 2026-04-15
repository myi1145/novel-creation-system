import { FormEvent, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ApiError } from '../api/http';
import { ActionFailure, ActionSuccess, EmptyState } from '../components/Status';
import type { StoryPlanningUpsertPayload } from '../types/domain';

const defaultForm: StoryPlanningUpsertPayload = {
  worldview: '',
  main_outline: '',
  volume_plan: '',
  core_seed_summary: '',
  planning_status: 'draft',
};

function formatDate(value?: string): string {
  if (!value) return '—';
  return new Date(value).toLocaleString('zh-CN', { hour12: false });
}

export function StoryPlanningPage() {
  const { projectId = '' } = useParams();
  const [form, setForm] = useState<StoryPlanningUpsertPayload>(defaultForm);
  const [hasPlanning, setHasPlanning] = useState(false);
  const [lastUpdatedAt, setLastUpdatedAt] = useState('');
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);

  const load = async () => {
    if (!projectId) return;
    setFeedback('');
    setError('');
    try {
      const data = await api.getStoryPlanning(projectId);
      if (!data) {
        setHasPlanning(false);
        setForm(defaultForm);
        setLastUpdatedAt('');
        return;
      }
      setHasPlanning(true);
      setForm({
        worldview: data.worldview || '',
        main_outline: data.main_outline || '',
        volume_plan: data.volume_plan || '',
        core_seed_summary: data.core_seed_summary || '',
        planning_status: data.planning_status,
      });
      setLastUpdatedAt(data.updated_at);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setHasPlanning(false);
        setForm(defaultForm);
        setLastUpdatedAt('');
      } else {
        setError('加载全书规划失败，请稍后重试。');
      }
    }
  };

  useEffect(() => {
    void load();
  }, [projectId]);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!projectId) return;

    setFeedback('');
    setError('');

    try {
      const saved = await api.saveStoryPlanning(projectId, {
        worldview: form.worldview.trim(),
        main_outline: form.main_outline.trim(),
        volume_plan: form.volume_plan.trim(),
        core_seed_summary: form.core_seed_summary.trim(),
        planning_status: form.planning_status,
      });
      setHasPlanning(true);
      setLastUpdatedAt(saved.updated_at);
      setFeedback('全书规划已保存。');
    } catch {
      setError('保存失败，请稍后重试。');
    }
  };

  const onGenerate = async () => {
    if (!projectId || isGenerating) return;
    setFeedback('');
    setError('');
    setIsGenerating(true);
    try {
      const generated = await api.generateStoryPlanning(projectId);
      setForm({
        worldview: generated.data.worldview || '',
        main_outline: generated.data.main_outline || '',
        volume_plan: generated.data.volume_plan || '',
        core_seed_summary: generated.data.core_seed_summary || '',
        planning_status: form.planning_status,
      });
      setFeedback('全书规划草稿已生成，请检查后保存。');
    } catch {
      setError('生成失败，请稍后重试。');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div>
      <h2>全书规划</h2>
      <div className="panel">
        <p><Link to={`/projects/${projectId}/story-planning/card-candidates`}>生成卡槽候选</Link></p>
        用于维护整部小说的整书架构规划（核心种子、角色动力学、世界规则、主线架构、分卷职责、初始状态快照）。这里的内容会作为后续章节创作的重要参考，但本轮不会自动写入正式设定，也不会自动生成角色卡或术语卡。
        <p>
          <button type="button" onClick={() => void onGenerate()} disabled={isGenerating}>
            {isGenerating ? '正在生成全书规划...' : '生成全书规划'}
          </button>
        </p>
      </div>

      {!hasPlanning && (
        <EmptyState text="还没有全书规划，可先生成整书架构草稿，再按阅读承诺/角色动力学/分卷职责逐项细化。" />
      )}

      <form className="panel" onSubmit={onSubmit}>
        <h3>{hasPlanning ? '编辑全书规划' : '新建全书规划'}</h3>

        <label>
          状态
          <select
            value={form.planning_status}
            onChange={(e) => setForm({ ...form, planning_status: e.target.value as 'draft' | 'confirmed' })}
          >
            <option value="draft">草稿</option>
            <option value="confirmed">已确认</option>
          </select>
        </label>

        <label>
          全书世界观
          <textarea
            value={form.worldview}
            onChange={(e) => setForm({ ...form, worldview: e.target.value })}
            rows={8}
            placeholder="建议包含：[世界背景][力量体系][社会秩序][势力格局][资源与代价][隐藏真相方向][规则边界]。"
          />
        </label>

        <label>
          全书主线大纲
          <textarea
            value={form.main_outline}
            onChange={(e) => setForm({ ...form, main_outline: e.target.value })}
            rows={8}
            placeholder="建议包含：[阅读承诺][主角长期成长主线][关键角色关系张力][核心冲突][主线架构][关键转折点][长程悬念问题]。"
          />
        </label>

        <label>
          分卷 / 阶段规划
          <textarea
            value={form.volume_plan}
            onChange={(e) => setForm({ ...form, volume_plan: e.target.value })}
            rows={8}
            placeholder="建议按[卷一职责][卷二职责][卷三职责]描述每卷目标/冲突/关键推进/卷末转折。"
          />
        </label>

        <label>
          核心设定种子摘要
          <textarea
            value={form.core_seed_summary}
            onChange={(e) => setForm({ ...form, core_seed_summary: e.target.value })}
            rows={8}
            placeholder="建议包含：[核心种子][初始状态快照][主角初始状态][关键关系初始状态][已知开放问题][埋下的谜团/伏笔]。"
          />
        </label>

        <p>最后更新时间：{formatDate(lastUpdatedAt)}</p>
        <button type="submit">保存全书规划</button>
      </form>

      {feedback && <ActionSuccess text={feedback} />}
      {error && <ActionFailure text={error} />}
    </div>
  );
}
