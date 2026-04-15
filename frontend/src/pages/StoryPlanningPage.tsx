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

  return (
    <div>
      <h2>全书规划</h2>
      <div className="panel">
        <p><Link to={`/projects/${projectId}/story-planning/card-candidates`}>生成卡槽候选</Link></p>
        用于维护整部小说的世界观、主线大纲和分卷/阶段规划。这里的内容会作为后续章节创作的重要参考，但本轮不会自动写入正式设定，也不会自动生成角色卡或术语卡。
      </div>

      {!hasPlanning && (
        <EmptyState text="还没有全书规划，可以先整理整部小说的世界观、主线大纲和分卷规划。" />
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
            placeholder="记录世界规则、体系设定、社会结构、题材边界。"
          />
        </label>

        <label>
          全书主线大纲
          <textarea
            value={form.main_outline}
            onChange={(e) => setForm({ ...form, main_outline: e.target.value })}
            rows={8}
            placeholder="记录主线目标、核心冲突、关键转折。"
          />
        </label>

        <label>
          分卷 / 阶段规划
          <textarea
            value={form.volume_plan}
            onChange={(e) => setForm({ ...form, volume_plan: e.target.value })}
            rows={8}
            placeholder="记录分卷推进与阶段节奏。"
          />
        </label>

        <label>
          核心设定种子摘要
          <textarea
            value={form.core_seed_summary}
            onChange={(e) => setForm({ ...form, core_seed_summary: e.target.value })}
            rows={8}
            placeholder="记录核心角色、势力、地点、术语的摘要线索。"
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
