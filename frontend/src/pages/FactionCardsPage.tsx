import { FormEvent, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ApiError } from '../api/http';
import { ActionFailure, ActionSuccess, EmptyState } from '../components/Status';
import type { FactionCard } from '../types/domain';

const defaultForm = {
  name: '', aliases: '', faction_type: '', description: '', core_members: '', territory: '', stance: '', goals: '', relationship_notes: '', current_status: '', first_appearance_chapter: '',
};

export function FactionCardsPage() {
  const { projectId = '' } = useParams();
  const [cards, setCards] = useState<FactionCard[]>([]);
  const [selected, setSelected] = useState<FactionCard | null>(null);
  const [form, setForm] = useState(defaultForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');

  const load = async () => {
    if (!projectId) return;
    try {
      setCards(await api.listFactionCards(projectId));
    } catch {
      setError('加载势力卡失败，请稍后重试。');
    }
  };

  useEffect(() => { void load(); }, [projectId]);

  const buildPayload = () => ({
    name: form.name.trim(),
    aliases: form.aliases.split('、').map((v) => v.trim()).filter(Boolean),
    faction_type: form.faction_type.trim(),
    description: form.description.trim(),
    core_members: form.core_members.split('、').map((v) => v.trim()).filter(Boolean),
    territory: form.territory.trim(),
    stance: form.stance.trim(),
    goals: form.goals.trim(),
    relationship_notes: form.relationship_notes.trim(),
    current_status: form.current_status.trim(),
    first_appearance_chapter: form.first_appearance_chapter ? Number(form.first_appearance_chapter) : null,
  });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!projectId) return;
    setFeedback('');
    setError('');
    try {
      if (editingId) {
        await api.updateFactionCard(projectId, editingId, buildPayload());
        setFeedback('势力卡已更新。');
      } else {
        await api.createFactionCard(projectId, buildPayload());
        setFeedback('势力卡已创建。');
      }
      setForm(defaultForm);
      setEditingId(null);
      await load();
    } catch (e2) {
      if (e2 instanceof ApiError && e2.status === 422) setError('请检查必填字段是否完整。');
      else setError('保存势力卡失败，请稍后重试。');
    }
  };

  return <div>
    <h2>势力卡</h2>
    <div className="panel">用于集中维护宗门、王朝、家族等势力设定，避免组织立场与目标在章节推进中漂移。</div>
    {cards.length === 0 ? <EmptyState text="还没有势力卡，可以先创建当前剧情最关键的组织。" /> : (
      <div className="panel"><h3>势力卡列表</h3><ul>
        {cards.map((card) => <li key={card.id}><button type="button" onClick={() => setSelected(card)}>{card.name}</button>
          <button type="button" onClick={() => { setEditingId(card.id); setSelected(card); setForm({
            name: card.name,
            aliases: card.aliases.join('、'),
            faction_type: card.faction_type,
            description: card.description,
            core_members: card.core_members.join('、'),
            territory: card.territory,
            stance: card.stance,
            goals: card.goals,
            relationship_notes: card.relationship_notes,
            current_status: card.current_status,
            first_appearance_chapter: card.first_appearance_chapter ? String(card.first_appearance_chapter) : '',
          }); }}>编辑</button></li>)}
      </ul></div>
    )}
    {selected && <div className="panel"><h3>详情</h3><pre>{JSON.stringify(selected, null, 2)}</pre></div>}
    <form className="panel" onSubmit={submit}>
      <h3>{editingId ? '编辑势力卡' : '创建势力卡'}</h3>
      <input placeholder="势力名称" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
      <input placeholder="别名（用、分隔）" value={form.aliases} onChange={(e) => setForm({ ...form, aliases: e.target.value })} />
      <input placeholder="势力类型" value={form.faction_type} onChange={(e) => setForm({ ...form, faction_type: e.target.value })} required />
      <textarea placeholder="势力简介" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} required />
      <input placeholder="核心成员（用、分隔）" value={form.core_members} onChange={(e) => setForm({ ...form, core_members: e.target.value })} />
      <textarea placeholder="主要活动范围" value={form.territory} onChange={(e) => setForm({ ...form, territory: e.target.value })} />
      <textarea placeholder="立场与倾向" value={form.stance} onChange={(e) => setForm({ ...form, stance: e.target.value })} />
      <textarea placeholder="当前目标" value={form.goals} onChange={(e) => setForm({ ...form, goals: e.target.value })} />
      <textarea placeholder="关系备注" value={form.relationship_notes} onChange={(e) => setForm({ ...form, relationship_notes: e.target.value })} />
      <textarea placeholder="当前状态" value={form.current_status} onChange={(e) => setForm({ ...form, current_status: e.target.value })} />
      <input placeholder="首次出现章节（可选）" value={form.first_appearance_chapter} onChange={(e) => setForm({ ...form, first_appearance_chapter: e.target.value })} />
      <button type="submit">{editingId ? '保存修改' : '创建势力卡'}</button>
    </form>
    {feedback && <ActionSuccess text={feedback} />}
    {error && <ActionFailure text={error} />}
  </div>;
}
