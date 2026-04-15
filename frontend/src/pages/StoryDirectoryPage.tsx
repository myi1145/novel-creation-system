import { FormEvent, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ApiError } from '../api/http';
import { ActionFailure, ActionSuccess, EmptyState } from '../components/Status';
import type { StoryDirectoryChapterItem, StoryDirectoryUpsertPayload } from '../types/domain';

const createEmptyChapterItem = (chapterNo: number): StoryDirectoryChapterItem => ({
  chapter_no: chapterNo,
  chapter_title: '',
  chapter_role: '',
  chapter_goal: '',
  stage_label: '',
  required_entities: [],
  required_seed_points: [],
  foreshadow_constraints: [],
});

const defaultForm: StoryDirectoryUpsertPayload = {
  story_planning_id: null,
  directory_title: '全书章节目录',
  directory_summary: '',
  directory_status: 'draft',
  chapter_items: [createEmptyChapterItem(1)],
};

function formatDate(value?: string): string {
  if (!value) return '—';
  return new Date(value).toLocaleString('zh-CN', { hour12: false });
}

function parseSemicolonText(value: string): string[] {
  return value
    .split(';')
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

function stringifySemicolonText(items: string[]): string {
  return items.join(';');
}

export function StoryDirectoryPage() {
  const { projectId = '' } = useParams();
  const [form, setForm] = useState<StoryDirectoryUpsertPayload>(defaultForm);
  const [hasDirectory, setHasDirectory] = useState(false);
  const [lastUpdatedAt, setLastUpdatedAt] = useState('');
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');

  const load = async () => {
    if (!projectId) return;
    setFeedback('');
    setError('');
    try {
      const data = await api.getStoryDirectory(projectId);
      if (!data) {
        setHasDirectory(false);
        setForm(defaultForm);
        setLastUpdatedAt('');
        return;
      }
      setHasDirectory(true);
      setForm({
        story_planning_id: data.story_planning_id || null,
        directory_title: data.directory_title || '全书章节目录',
        directory_summary: data.directory_summary || '',
        directory_status: data.directory_status,
        chapter_items: Array.isArray(data.chapter_items) && data.chapter_items.length > 0
          ? data.chapter_items
          : [createEmptyChapterItem(1)],
      });
      setLastUpdatedAt(data.updated_at);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setHasDirectory(false);
        setForm(defaultForm);
        setLastUpdatedAt('');
      } else {
        setError('加载章节目录失败，请稍后重试。');
      }
    }
  };

  useEffect(() => {
    void load();
  }, [projectId]);

  const updateChapter = (index: number, next: StoryDirectoryChapterItem) => {
    setForm((prev) => {
      const updated = [...prev.chapter_items];
      updated[index] = next;
      return { ...prev, chapter_items: updated };
    });
  };

  const addChapter = () => {
    setForm((prev) => {
      const nextNo = prev.chapter_items.length > 0 ? prev.chapter_items[prev.chapter_items.length - 1].chapter_no + 1 : 1;
      return { ...prev, chapter_items: [...prev.chapter_items, createEmptyChapterItem(nextNo)] };
    });
  };

  const removeChapter = (index: number) => {
    setForm((prev) => {
      const updated = prev.chapter_items.filter((_, i) => i !== index);
      return { ...prev, chapter_items: updated.length > 0 ? updated : [createEmptyChapterItem(1)] };
    });
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!projectId) return;

    setFeedback('');
    setError('');

    try {
      const saved = await api.saveStoryDirectory(projectId, {
        story_planning_id: form.story_planning_id || null,
        directory_title: form.directory_title.trim() || '全书章节目录',
        directory_summary: form.directory_summary.trim(),
        directory_status: form.directory_status,
        chapter_items: form.chapter_items.map((item, idx) => ({
          chapter_no: Number.isFinite(item.chapter_no) ? item.chapter_no : idx + 1,
          chapter_title: item.chapter_title.trim(),
          chapter_role: item.chapter_role.trim(),
          chapter_goal: item.chapter_goal.trim(),
          stage_label: item.stage_label.trim(),
          required_entities: item.required_entities,
          required_seed_points: item.required_seed_points,
          foreshadow_constraints: item.foreshadow_constraints,
        })),
      });
      setHasDirectory(true);
      setLastUpdatedAt(saved.updated_at);
      setFeedback('章节目录已保存。');
    } catch {
      setError('保存失败，请稍后重试。');
    }
  };

  return (
    <div>
      <h2>章节目录</h2>
      <div className="panel">
        <p><Link to={`/projects/${projectId}/story-planning/card-candidates`}>生成卡槽候选</Link></p>
        用于把全书规划落到逐章目录，明确每一章的标题、职责、推进目标和关键设定落点。这里的内容会作为后续卡槽候选和章节规划的重要依据，但本轮不会自动生成候选卡，也不会自动进入正式设定。
      </div>

      {!hasDirectory && <EmptyState text="还没有章节目录，可以先整理每一章的标题、职责和推进目标。" />}

      <form className="panel" onSubmit={onSubmit}>
        <h3>{hasDirectory ? '编辑章节目录' : '新建章节目录'}</h3>

        <label>
          目录标题
          <input
            value={form.directory_title}
            onChange={(e) => setForm({ ...form, directory_title: e.target.value })}
            placeholder="全书章节目录"
          />
        </label>

        <label>
          目录摘要
          <textarea
            value={form.directory_summary}
            onChange={(e) => setForm({ ...form, directory_summary: e.target.value })}
            rows={5}
            placeholder="记录整份目录的节奏、分卷、阶段推进说明。"
          />
        </label>

        <label>
          目录状态
          <select
            value={form.directory_status}
            onChange={(e) => setForm({ ...form, directory_status: e.target.value as 'draft' | 'confirmed' })}
          >
            <option value="draft">草稿</option>
            <option value="confirmed">已确认</option>
          </select>
        </label>

        <div>
          <h4>章节项</h4>
          {form.chapter_items.map((chapter, index) => (
            <div className="panel" key={`${index}-${chapter.chapter_no}`}>
              <label>
                章节序号
                <input
                  type="number"
                  value={chapter.chapter_no}
                  onChange={(e) => updateChapter(index, { ...chapter, chapter_no: Number(e.target.value || 0) })}
                />
              </label>

              <label>
                章节标题
                <input
                  value={chapter.chapter_title}
                  onChange={(e) => updateChapter(index, { ...chapter, chapter_title: e.target.value })}
                  placeholder="例如：灵根初现"
                />
              </label>

              <label>
                章节职责
                <textarea
                  value={chapter.chapter_role}
                  onChange={(e) => updateChapter(index, { ...chapter, chapter_role: e.target.value })}
                  rows={3}
                />
              </label>

              <label>
                章节推进目标
                <textarea
                  value={chapter.chapter_goal}
                  onChange={(e) => updateChapter(index, { ...chapter, chapter_goal: e.target.value })}
                  rows={3}
                />
              </label>

              <label>
                所属阶段 / 分卷标签
                <input
                  value={chapter.stage_label}
                  onChange={(e) => updateChapter(index, { ...chapter, stage_label: e.target.value })}
                />
              </label>

              <label>
                关键出场实体（用 ; 分隔）
                <textarea
                  value={stringifySemicolonText(chapter.required_entities)}
                  onChange={(e) => updateChapter(index, { ...chapter, required_entities: parseSemicolonText(e.target.value) })}
                  rows={2}
                />
              </label>

              <label>
                必须落地的设定点（用 ; 分隔）
                <textarea
                  value={stringifySemicolonText(chapter.required_seed_points)}
                  onChange={(e) => updateChapter(index, { ...chapter, required_seed_points: parseSemicolonText(e.target.value) })}
                  rows={2}
                />
              </label>

              <label>
                伏笔约束（用 ; 分隔）
                <textarea
                  value={stringifySemicolonText(chapter.foreshadow_constraints)}
                  onChange={(e) => updateChapter(index, { ...chapter, foreshadow_constraints: parseSemicolonText(e.target.value) })}
                  rows={2}
                />
              </label>

              <button type="button" onClick={() => removeChapter(index)}>删除章节</button>
            </div>
          ))}
          <button type="button" onClick={addChapter}>新增章节</button>
        </div>

        <p>最后更新时间：{formatDate(lastUpdatedAt)}</p>
        <button type="submit">保存章节目录</button>
      </form>

      {feedback && <ActionSuccess text={feedback} />}
      {error && <ActionFailure text={error} />}
    </div>
  );
}
