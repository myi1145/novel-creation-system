import { FormEvent, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ApiError } from '../api/http';
import { ActionFailure, ActionSuccess, EmptyState } from '../components/Status';
import type { CharacterCard } from '../types/domain';

const defaultForm = {
  name: '', aliases: '', role_position: '', profile: '', personality_keywords: '', relationship_notes: '', current_status: '', first_appearance_chapter: '',
};

const formatDate = (value: string) => (value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '—');

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

  const startEdit = (card: CharacterCard) => {
    setEditingId(card.id);
    setSelected(card);
    setForm({
      name: card.name,
      aliases: card.aliases.join('、'),
      role_position: card.role_position,
      profile: card.profile,
      personality_keywords: card.personality_keywords.join('、'),
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
    <div className="panel">
      用于维护人物身份、性格、关系与当前状态，减少跨章节人物设定漂移。当前仅支持人工维护，不会自动写入正式设定。 
    </div>
    {cards.length === 0 ? <EmptyState text="还没有角色卡，可以先创建主角或核心配角。" /> : (
      <div className="panel"><h3>角色卡列表</h3><ul>
        {cards.map((card) => <li key={card.id}>
          <button type="button" onClick={() => setSelected(card)}>{card.name}</button>
          <span>｜身份定位：{card.role_position || '未填写'}</span>
          <span>｜当前状态：{card.current_status || '未填写'}</span>
          <span>｜是否进入正式设定：{card.is_canon ? '是' : '否'}</span>
          <button type="button" onClick={() => startEdit(card)}>编辑</button>
        </li>)}
      </ul></div>
    )}
    {selected && <div className="panel"><h3>详情</h3>
      <h4>基础信息</h4>
      <p>名称：{selected.name}</p>
      <p>别名：{selected.aliases.length ? selected.aliases.join('、') : '—'}</p>
      <p>身份定位：{selected.role_position || '—'}</p>
      <p>首次出现章节：{selected.first_appearance_chapter ?? '—'}</p>
      <h4>设定内容</h4>
      <p>人物简介：{selected.profile || '—'}</p>
      <p>性格关键词：{selected.personality_keywords.length ? selected.personality_keywords.join('、') : '—'}</p>
      <h4>关系 / 关联</h4>
      <p>关系备注：{selected.relationship_notes || '—'}</p>
      <h4>当前状态</h4>
      <p>{selected.current_status || '—'}</p>
      <h4>来源与审计</h4>
      <p>来源：{selected.last_update_source === 'human' ? '人工维护' : selected.last_update_source || '人工维护'}</p>
      <p>是否进入正式设定：{selected.is_canon ? '是' : '否'}（当前仅用于标记，不会自动写入正式设定。）</p>
      <p>创建时间：{formatDate(selected.created_at)}</p>
      <p>更新时间：{formatDate(selected.updated_at)}</p>
    </div>}
    <form className="panel" onSubmit={submit}>
      <h3>{editingId ? '编辑角色卡' : '新建角色卡'}</h3>
      <input placeholder="名称（必填）" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
      <input placeholder="别名（可选，用、分隔）" value={form.aliases} onChange={(e) => setForm({ ...form, aliases: e.target.value })} />
      <input placeholder="身份定位（必填，如主角/反派/导师）" value={form.role_position} onChange={(e) => setForm({ ...form, role_position: e.target.value })} required />
      <textarea placeholder="人物简介（必填，建议 1-3 句）" value={form.profile} onChange={(e) => setForm({ ...form, profile: e.target.value })} required />
      <input placeholder="性格关键词（可选，用、分隔）" value={form.personality_keywords} onChange={(e) => setForm({ ...form, personality_keywords: e.target.value })} />
      <textarea placeholder="关系备注（可选，记录关键人物关系）" value={form.relationship_notes} onChange={(e) => setForm({ ...form, relationship_notes: e.target.value })} />
      <textarea placeholder="当前状态（可选，如闭关中/失踪）" value={form.current_status} onChange={(e) => setForm({ ...form, current_status: e.target.value })} />
      <input placeholder="首次出现章节（可选，用于帮助作者回忆首次出现位置）" value={form.first_appearance_chapter} onChange={(e) => setForm({ ...form, first_appearance_chapter: e.target.value })} />
      <p>最近更新来源：本阶段主要为人工维护。</p>
      <button type="submit">{editingId ? '保存角色卡' : '新建角色卡'}</button>
    </form>
    {feedback && <ActionSuccess text={feedback} />}
    {error && <ActionFailure text={error} />}
  </div>;
}
