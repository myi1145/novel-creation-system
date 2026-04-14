import { FormEvent, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ApiError } from '../api/http';
import { ActionFailure, ActionSuccess, EmptyState } from '../components/Status';
import type { FactionCard } from '../types/domain';

const defaultForm = {
  name: '', aliases: '', faction_type: '', description: '', core_members: '', territory: '', stance: '', goals: '', relationship_notes: '', current_status: '', first_appearance_chapter: '',
};

const formatDate = (value: string) => (value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—');

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

  const startEdit = (card: FactionCard) => {
    setEditingId(card.id);
    setSelected(card);
    setForm({
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
    });
  };

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
    <div className="panel">
      用于维护宗门、王朝、组织、族群等设定，稳定势力立场、目标与阶段状态。当前仅支持人工维护，不会自动写入正式设定。
    </div>
    {cards.length === 0 ? <EmptyState text="还没有势力卡，可以先创建主角所在宗门、王朝或主要敌对势力。" /> : (
      <div className="panel"><h3>势力卡列表</h3><ul>
        {cards.map((card) => <li key={card.id}>
          <button type="button" onClick={() => setSelected(card)}>{card.name}</button>
          <span>｜势力类型：{card.faction_type || '未填写'}</span>
          <span>｜立场：{card.stance || '未填写'}</span>
          <span>｜当前状态：{card.current_status || '未填写'}</span>
          <button type="button" onClick={() => startEdit(card)}>编辑</button>
        </li>)}
      </ul></div>
    )}
    {selected && <div className="panel"><h3>详情</h3>
      <h4>基础信息</h4>
      <p>势力名称：{selected.name}</p>
      <p>别名：{selected.aliases.length ? selected.aliases.join('、') : '—'}</p>
      <p>势力类型：{selected.faction_type || '—'}</p>
      <p>首次出现章节：{selected.first_appearance_chapter ?? '—'}</p>
      <h4>设定内容</h4>
      <p>势力简介：{selected.description || '—'}</p>
      <p>主要活动范围：{selected.territory || '—'}</p>
      <p>当前目标：{selected.goals || '—'}</p>
      <h4>关系 / 关联</h4>
      <p>核心成员：{selected.core_members.length ? selected.core_members.join('、') : '—'}</p>
      <p>关系备注：{selected.relationship_notes || '—'}</p>
      <h4>当前状态</h4>
      <p>立场：{selected.stance || '—'}</p>
      <p>势力状态：{selected.current_status || '—'}</p>
      <h4>来源与审计</h4>
      <p>来源：{selected.last_update_source === 'human' ? '人工维护' : selected.last_update_source || '人工维护'}</p>
      <p>是否进入正式设定：{selected.is_canon ? '是' : '否'}（当前仅用于标记，不会自动写入正式设定。）</p>
      <p>创建时间：{formatDate(selected.created_at)}</p>
      <p>更新时间：{formatDate(selected.updated_at)}</p>
    </div>}
    <form className="panel" onSubmit={submit}>
      <h3>{editingId ? '编辑势力卡' : '新建势力卡'}</h3>
      <input placeholder="势力名称（必填）" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
      <input placeholder="别名（可选，用、分隔）" value={form.aliases} onChange={(e) => setForm({ ...form, aliases: e.target.value })} />
      <input placeholder="势力类型（必填，如宗门/王朝/家族）" value={form.faction_type} onChange={(e) => setForm({ ...form, faction_type: e.target.value })} required />
      <textarea placeholder="势力简介（必填，建议 1-3 句）" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} required />
      <input placeholder="核心成员（可选，用、分隔）" value={form.core_members} onChange={(e) => setForm({ ...form, core_members: e.target.value })} />
      <textarea placeholder="主要活动范围（可选）" value={form.territory} onChange={(e) => setForm({ ...form, territory: e.target.value })} />
      <textarea placeholder="立场（可选，如中立/敌对）" value={form.stance} onChange={(e) => setForm({ ...form, stance: e.target.value })} />
      <textarea placeholder="当前目标（可选）" value={form.goals} onChange={(e) => setForm({ ...form, goals: e.target.value })} />
      <textarea placeholder="关系备注（可选，记录与其他势力或角色关系）" value={form.relationship_notes} onChange={(e) => setForm({ ...form, relationship_notes: e.target.value })} />
      <textarea placeholder="当前状态（可选）" value={form.current_status} onChange={(e) => setForm({ ...form, current_status: e.target.value })} />
      <input placeholder="首次出现章节（可选，用于帮助作者回忆该设定首次出现的位置）" value={form.first_appearance_chapter} onChange={(e) => setForm({ ...form, first_appearance_chapter: e.target.value })} />
      <p>最近更新来源：本阶段主要为人工维护。</p>
      <button type="submit">{editingId ? '保存势力卡' : '新建势力卡'}</button>
    </form>
    {feedback && <ActionSuccess text={feedback} />}
    {error && <ActionFailure text={error} />}
  </div>;
}
