import { FormEvent, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ApiError } from '../api/http';
import { ActionFailure, ActionSuccess, EmptyState } from '../components/Status';
import type { LocationCard } from '../types/domain';

const defaultForm = {
  name: '', aliases: '', location_type: '', description: '', region: '', key_features: '', related_factions: '', narrative_role: '', current_status: '', first_appearance_chapter: '',
};

export function LocationCardsPage() {
  const { projectId = '' } = useParams();
  const [cards, setCards] = useState<LocationCard[]>([]);
  const [selected, setSelected] = useState<LocationCard | null>(null);
  const [form, setForm] = useState(defaultForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');

  const load = async () => {
    if (!projectId) return;
    try {
      setCards(await api.listLocationCards(projectId));
    } catch {
      setError('加载地点卡失败，请稍后重试。');
    }
  };

  useEffect(() => { void load(); }, [projectId]);

  const buildPayload = () => ({
    name: form.name.trim(),
    aliases: form.aliases.split('、').map((v) => v.trim()).filter(Boolean),
    location_type: form.location_type.trim(),
    description: form.description.trim(),
    region: form.region.trim(),
    key_features: form.key_features.split('、').map((v) => v.trim()).filter(Boolean),
    related_factions: form.related_factions.split('、').map((v) => v.trim()).filter(Boolean),
    narrative_role: form.narrative_role.trim(),
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
        await api.updateLocationCard(projectId, editingId, buildPayload());
        setFeedback('地点卡已更新。');
      } else {
        await api.createLocationCard(projectId, buildPayload());
        setFeedback('地点卡已创建。');
      }
      setForm(defaultForm);
      setEditingId(null);
      await load();
    } catch (e2) {
      if (e2 instanceof ApiError && e2.status === 422) setError('请检查必填字段是否完整。');
      else setError('保存地点卡失败，请稍后重试。');
    }
  };

  return <div>
    <h2>地点卡</h2>
    <div className="panel">用于集中维护城镇、宗门、秘境等地点设定，保证地理信息与叙事用途在后续章节一致。</div>
    {cards.length === 0 ? <EmptyState text="还没有地点卡，可以先创建当前主线最关键的地点。" /> : (
      <div className="panel"><h3>地点卡列表</h3><ul>
        {cards.map((card) => <li key={card.id}><button type="button" onClick={() => setSelected(card)}>{card.name}</button>
          <button type="button" onClick={() => { setEditingId(card.id); setSelected(card); setForm({
            name: card.name,
            aliases: card.aliases.join('、'),
            location_type: card.location_type,
            description: card.description,
            region: card.region,
            key_features: card.key_features.join('、'),
            related_factions: card.related_factions.join('、'),
            narrative_role: card.narrative_role,
            current_status: card.current_status,
            first_appearance_chapter: card.first_appearance_chapter ? String(card.first_appearance_chapter) : '',
          }); }}>编辑</button></li>)}
      </ul></div>
    )}
    {selected && <div className="panel"><h3>详情</h3><pre>{JSON.stringify(selected, null, 2)}</pre></div>}
    <form className="panel" onSubmit={submit}>
      <h3>{editingId ? '编辑地点卡' : '创建地点卡'}</h3>
      <input placeholder="地点名称" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
      <input placeholder="别名（用、分隔）" value={form.aliases} onChange={(e) => setForm({ ...form, aliases: e.target.value })} />
      <input placeholder="地点类型" value={form.location_type} onChange={(e) => setForm({ ...form, location_type: e.target.value })} required />
      <textarea placeholder="地点简介" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} required />
      <input placeholder="所属区域" value={form.region} onChange={(e) => setForm({ ...form, region: e.target.value })} />
      <input placeholder="关键特征（用、分隔）" value={form.key_features} onChange={(e) => setForm({ ...form, key_features: e.target.value })} />
      <input placeholder="相关势力（用、分隔）" value={form.related_factions} onChange={(e) => setForm({ ...form, related_factions: e.target.value })} />
      <textarea placeholder="叙事作用" value={form.narrative_role} onChange={(e) => setForm({ ...form, narrative_role: e.target.value })} />
      <textarea placeholder="当前状态" value={form.current_status} onChange={(e) => setForm({ ...form, current_status: e.target.value })} />
      <input placeholder="首次出现章节（可选）" value={form.first_appearance_chapter} onChange={(e) => setForm({ ...form, first_appearance_chapter: e.target.value })} />
      <button type="submit">{editingId ? '保存修改' : '创建地点卡'}</button>
    </form>
    {feedback && <ActionSuccess text={feedback} />}
    {error && <ActionFailure text={error} />}
  </div>;
}
