import { FormEvent, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ApiError } from '../api/http';
import { ActionFailure, ActionSuccess, EmptyState } from '../components/Status';
import type { LocationCard } from '../types/domain';

const defaultForm = {
  name: '', aliases: '', location_type: '', description: '', region: '', key_features: '', related_factions: '', narrative_role: '', current_status: '', first_appearance_chapter: '',
};

const formatDate = (value: string) => (value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—');

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

  const startEdit = (card: LocationCard) => {
    setEditingId(card.id);
    setSelected(card);
    setForm({
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
    });
  };

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
    <div className="panel">
      用于维护城镇、宗门、秘境、禁地等空间设定，稳定地理信息与剧情作用。当前仅支持人工维护，不会自动写入正式设定。
    </div>
    {cards.length === 0 ? <EmptyState text="还没有地点卡，可以先创建主角出身地、宗门或关键秘境。" /> : (
      <div className="panel"><h3>地点卡列表</h3><ul>
        {cards.map((card) => <li key={card.id}>
          <button type="button" onClick={() => setSelected(card)}>{card.name}</button>
          <span>｜地点类型：{card.location_type || '未填写'}</span>
          <span>｜所属区域：{card.region || '未填写'}</span>
          <span>｜剧情作用：{card.narrative_role || '未填写'}</span>
          <button type="button" onClick={() => startEdit(card)}>编辑</button>
        </li>)}
      </ul></div>
    )}
    {selected && <div className="panel"><h3>详情</h3>
      <h4>基础信息</h4>
      <p>地点名称：{selected.name}</p>
      <p>别名：{selected.aliases.length ? selected.aliases.join('、') : '—'}</p>
      <p>地点类型：{selected.location_type || '—'}</p>
      <p>所属区域：{selected.region || '—'}</p>
      <p>首次出现章节：{selected.first_appearance_chapter ?? '—'}</p>
      <h4>设定内容</h4>
      <p>地点简介：{selected.description || '—'}</p>
      <p>关键特征：{selected.key_features.length ? selected.key_features.join('、') : '—'}</p>
      <h4>关系 / 关联</h4>
      <p>相关势力：{selected.related_factions.length ? selected.related_factions.join('、') : '—'}</p>
      <p>剧情作用：{selected.narrative_role || '—'}</p>
      <h4>当前状态</h4>
      <p>{selected.current_status || '—'}</p>
      <h4>来源与审计</h4>
      <p>来源：{selected.last_update_source === 'human' ? '人工维护' : selected.last_update_source || '人工维护'}</p>
      <p>是否进入正式设定：{selected.is_canon ? '是' : '否'}（当前仅用于标记，不会自动写入正式设定。）</p>
      <p>创建时间：{formatDate(selected.created_at)}</p>
      <p>更新时间：{formatDate(selected.updated_at)}</p>
    </div>}
    <form className="panel" onSubmit={submit}>
      <h3>{editingId ? '编辑地点卡' : '新建地点卡'}</h3>
      <input placeholder="地点名称（必填）" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
      <input placeholder="别名（可选，用、分隔）" value={form.aliases} onChange={(e) => setForm({ ...form, aliases: e.target.value })} />
      <input placeholder="地点类型（必填，如城镇/宗门/秘境）" value={form.location_type} onChange={(e) => setForm({ ...form, location_type: e.target.value })} required />
      <textarea placeholder="地点简介（必填，建议 1-3 句）" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} required />
      <input placeholder="所属区域（可选）" value={form.region} onChange={(e) => setForm({ ...form, region: e.target.value })} />
      <input placeholder="关键特征（可选，用、分隔）" value={form.key_features} onChange={(e) => setForm({ ...form, key_features: e.target.value })} />
      <input placeholder="相关势力（可选，用、分隔）" value={form.related_factions} onChange={(e) => setForm({ ...form, related_factions: e.target.value })} />
      <textarea placeholder="剧情作用（可选，如决战地/试炼地）" value={form.narrative_role} onChange={(e) => setForm({ ...form, narrative_role: e.target.value })} />
      <textarea placeholder="当前状态（可选）" value={form.current_status} onChange={(e) => setForm({ ...form, current_status: e.target.value })} />
      <input placeholder="首次出现章节（可选，用于帮助作者回忆该设定首次出现的位置）" value={form.first_appearance_chapter} onChange={(e) => setForm({ ...form, first_appearance_chapter: e.target.value })} />
      <p>最近更新来源：本阶段主要为人工维护。</p>
      <button type="submit">{editingId ? '保存地点卡' : '新建地点卡'}</button>
    </form>
    {feedback && <ActionSuccess text={feedback} />}
    {error && <ActionFailure text={error} />}
  </div>;
}
