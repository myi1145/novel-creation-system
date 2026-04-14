import { FormEvent, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ApiError } from '../api/http';
import { ActionFailure, ActionSuccess, EmptyState } from '../components/Status';
import type { TerminologyCard } from '../types/domain';

const defaultForm = {
  term: '', term_type: '', definition: '', usage_rules: '', examples: '', first_appearance_chapter: '',
};

export function TerminologyCardsPage() {
  const { projectId = '' } = useParams();
  const [cards, setCards] = useState<TerminologyCard[]>([]);
  const [selected, setSelected] = useState<TerminologyCard | null>(null);
  const [form, setForm] = useState(defaultForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');

  const load = async () => {
    if (!projectId) return;
    try {
      setCards(await api.listTerminologyCards(projectId));
    } catch {
      setError('加载术语卡失败，请稍后重试。');
    }
  };

  useEffect(() => { void load(); }, [projectId]);

  const buildPayload = () => ({
    term: form.term.trim(),
    term_type: form.term_type.trim(),
    definition: form.definition.trim(),
    usage_rules: form.usage_rules.trim(),
    examples: form.examples.split('、').map((v) => v.trim()).filter(Boolean),
    first_appearance_chapter: form.first_appearance_chapter ? Number(form.first_appearance_chapter) : null,
  });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!projectId) return;
    setFeedback('');
    setError('');
    try {
      if (editingId) {
        await api.updateTerminologyCard(projectId, editingId, buildPayload());
        setFeedback('术语卡已更新。');
      } else {
        await api.createTerminologyCard(projectId, buildPayload());
        setFeedback('术语卡已创建。');
      }
      setForm(defaultForm);
      setEditingId(null);
      await load();
    } catch (e2) {
      if (e2 instanceof ApiError && e2.status === 422) setError('请检查必填字段是否完整。');
      else setError('保存术语卡失败，请稍后重试。');
    }
  };

  return <div>
    <h2>术语卡</h2>
    <div className="panel">用于维护修炼体系、阵法术语、世界观概念等固定说法，保证后续章节用词一致。</div>
    {cards.length === 0 ? <EmptyState text="还没有术语卡，可以先创建本书最核心的修炼、阵法或世界观术语。" /> : (
      <div className="panel"><h3>术语卡列表</h3><ul>
        {cards.map((card) => <li key={card.id}><button type="button" onClick={() => setSelected(card)}>{card.term}</button>
          <button type="button" onClick={() => { setEditingId(card.id); setSelected(card); setForm({
            term: card.term,
            term_type: card.term_type,
            definition: card.definition,
            usage_rules: card.usage_rules,
            examples: card.examples.join('、'),
            first_appearance_chapter: card.first_appearance_chapter ? String(card.first_appearance_chapter) : '',
          }); }}>编辑</button></li>)}
      </ul></div>
    )}
    {selected && <div className="panel"><h3>详情</h3><pre>{JSON.stringify(selected, null, 2)}</pre></div>}
    <form className="panel" onSubmit={submit}>
      <h3>{editingId ? '编辑术语卡' : '创建术语卡'}</h3>
      <input placeholder="术语" value={form.term} onChange={(e) => setForm({ ...form, term: e.target.value })} required />
      <input placeholder="术语类型" value={form.term_type} onChange={(e) => setForm({ ...form, term_type: e.target.value })} required />
      <textarea placeholder="术语定义" value={form.definition} onChange={(e) => setForm({ ...form, definition: e.target.value })} required />
      <textarea placeholder="使用规则" value={form.usage_rules} onChange={(e) => setForm({ ...form, usage_rules: e.target.value })} />
      <input placeholder="示例（用、分隔）" value={form.examples} onChange={(e) => setForm({ ...form, examples: e.target.value })} />
      <input placeholder="首次出现章节（可选）" value={form.first_appearance_chapter} onChange={(e) => setForm({ ...form, first_appearance_chapter: e.target.value })} />
      <button type="submit">{editingId ? '保存修改' : '创建术语卡'}</button>
    </form>
    {feedback && <ActionSuccess text={feedback} />}
    {error && <ActionFailure text={error} />}
  </div>;
}
