import { FormEvent, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ApiError } from '../api/http';
import { ActionFailure, ActionSuccess, EmptyState } from '../components/Status';
import type { CharacterCard } from '../types/domain';

const defaultForm = {
  name: '', aliases: '', role_position: '', profile: '', personality_keywords: '', relationship_notes: '', current_status: '', first_appearance_chapter: '',
};

export function CharacterCardsPage() {
  const { projectId = '' } = useParams();
  const [cards, setCards] = useState<CharacterCard[]>([]);
  const [selected, setSelected] = useState<CharacterCard | null>(null);
  const [form, setForm] = useState(defaultForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');

  const load = async () => {
    if (!projectId) return;
    try {
      setCards(await api.listCharacterCards(projectId));
    } catch {
      setError('加载角色卡失败，请稍后重试。');
    }
  };

  useEffect(() => { void load(); }, [projectId]);

  const buildPayload = () => ({
    name: form.name.trim(),
    aliases: form.aliases.split('、').map((v) => v.trim()).filter(Boolean),
    role_position: form.role_position.trim(),
    profile: form.profile.trim(),
    personality_keywords: form.personality_keywords.split('、').map((v) => v.trim()).filter(Boolean),
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
        await api.updateCharacterCard(projectId, editingId, buildPayload());
        setFeedback('角色卡已更新。');
      } else {
        await api.createCharacterCard(projectId, buildPayload());
        setFeedback('角色卡已创建。');
      }
      setForm(defaultForm);
      setEditingId(null);
      await load();
    } catch (e2) {
      if (e2 instanceof ApiError && e2.status === 422) setError('请检查必填字段是否完整。');
      else setError('保存角色卡失败，请稍后重试。');
    }
  };

  return <div>
    <h2>角色卡</h2>
    <div className="panel">用于集中维护本项目的重要人物设定，避免长篇创作中人物身份、性格和关系前后不一致。</div>
    {cards.length === 0 ? <EmptyState text="还没有角色卡，可以先创建主角或核心配角。" /> : (
      <div className="panel"><h3>角色卡列表</h3><ul>
        {cards.map((card) => <li key={card.id}><button type="button" onClick={() => setSelected(card)}>{card.name}</button>
          <button type="button" onClick={() => { setEditingId(card.id); setSelected(card); setForm({
            name: card.name,
            aliases: card.aliases.join('、'),
            role_position: card.role_position,
            profile: card.profile,
            personality_keywords: card.personality_keywords.join('、'),
            relationship_notes: card.relationship_notes,
            current_status: card.current_status,
            first_appearance_chapter: card.first_appearance_chapter ? String(card.first_appearance_chapter) : '',
          }); }}>编辑</button></li>)}
      </ul></div>
    )}
    {selected && <div className="panel"><h3>详情</h3><pre>{JSON.stringify(selected, null, 2)}</pre></div>}
    <form className="panel" onSubmit={submit}>
      <h3>{editingId ? '编辑角色卡' : '创建角色卡'}</h3>
      <input placeholder="姓名" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
      <input placeholder="别名（用、分隔）" value={form.aliases} onChange={(e) => setForm({ ...form, aliases: e.target.value })} />
      <input placeholder="角色定位" value={form.role_position} onChange={(e) => setForm({ ...form, role_position: e.target.value })} required />
      <textarea placeholder="人物简介" value={form.profile} onChange={(e) => setForm({ ...form, profile: e.target.value })} required />
      <input placeholder="性格关键词（用、分隔）" value={form.personality_keywords} onChange={(e) => setForm({ ...form, personality_keywords: e.target.value })} />
      <textarea placeholder="关系备注" value={form.relationship_notes} onChange={(e) => setForm({ ...form, relationship_notes: e.target.value })} />
      <textarea placeholder="当前状态" value={form.current_status} onChange={(e) => setForm({ ...form, current_status: e.target.value })} />
      <input placeholder="首次出场章节（可选）" value={form.first_appearance_chapter} onChange={(e) => setForm({ ...form, first_appearance_chapter: e.target.value })} />
      <button type="submit">{editingId ? '保存修改' : '创建角色卡'}</button>
    </form>
    {feedback && <ActionSuccess text={feedback} />}
    {error && <ActionFailure text={error} />}
  </div>;
}
