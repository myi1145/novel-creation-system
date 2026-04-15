import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ActionFailure, ActionSuccess, EmptyState } from '../components/Status';
import type {
  StoryPlanningCardCandidate,
  StoryPlanningCardCandidateGenerateReport,
  StoryPlanningCardCandidateStatus,
  StoryPlanningCardCandidateType,
} from '../types/domain';

const cardTypeOptions: { value: '' | StoryPlanningCardCandidateType; label: string }[] = [
  { value: '', label: '全部类型' },
  { value: 'character', label: '角色' },
  { value: 'terminology', label: '术语' },
  { value: 'faction', label: '势力' },
  { value: 'location', label: '地点' },
];

const statusOptions: { value: '' | StoryPlanningCardCandidateStatus; label: string }[] = [
  { value: '', label: '全部状态' },
  { value: 'pending', label: '待确认' },
  { value: 'confirmed', label: '已确认' },
  { value: 'skipped', label: '已跳过' },
];

const cardTypeLabel: Record<StoryPlanningCardCandidateType, string> = {
  character: '角色',
  terminology: '术语',
  faction: '势力',
  location: '地点',
};

export function StoryPlanningCardCandidatesPage() {
  const { projectId = '' } = useParams();
  const [items, setItems] = useState<StoryPlanningCardCandidate[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [selected, setSelected] = useState<StoryPlanningCardCandidate | null>(null);
  const [cardTypeFilter, setCardTypeFilter] = useState<'' | StoryPlanningCardCandidateType>('');
  const [statusFilter, setStatusFilter] = useState<'' | StoryPlanningCardCandidateStatus>('pending');
  const [report, setReport] = useState<StoryPlanningCardCandidateGenerateReport | null>(null);
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');

  const load = async () => {
    if (!projectId) return;
    setError('');
    try {
      const list = await api.listStoryPlanningCardCandidates(projectId, {
        card_type: cardTypeFilter || undefined,
        status: statusFilter || undefined,
      });
      setItems(list);
      if (list.length === 0) {
        setSelectedId('');
        setSelected(null);
        return;
      }
      const nextSelected = selectedId && list.some((it) => it.id === selectedId) ? selectedId : list[0].id;
      setSelectedId(nextSelected);
      const detail = await api.getStoryPlanningCardCandidate(projectId, nextSelected);
      setSelected(detail);
    } catch {
      setError('加载候选卡失败，请稍后重试。');
    }
  };

  useEffect(() => {
    void load();
  }, [projectId, cardTypeFilter, statusFilter]);

  const selectedSummary = useMemo(() => {
    if (!selected) return '请选择候选卡查看详情。';
    return selected.summary || '暂无摘要';
  }, [selected]);

  const onGenerate = async () => {
    if (!projectId) return;
    setFeedback('');
    setError('');
    try {
      const result = await api.generateStoryPlanningCardCandidates(projectId);
      setReport(result);
      setFeedback(`已生成 ${result.generated_count} 条候选，跳过 ${result.skipped_count} 条。`);
      await load();
    } catch {
      setError('生成候选卡失败，请确认全书规划和章节目录已准备。');
    }
  };

  const onSelect = async (candidateId: string) => {
    if (!projectId) return;
    setSelectedId(candidateId);
    setError('');
    try {
      const detail = await api.getStoryPlanningCardCandidate(projectId, candidateId);
      setSelected(detail);
    } catch {
      setError('加载候选详情失败。');
    }
  };

  const onConfirm = async () => {
    if (!projectId || !selected) return;
    setFeedback('');
    setError('');
    try {
      const result = await api.confirmStoryPlanningCardCandidate(projectId, selected.id);
      setFeedback(result.message);
      await load();
    } catch {
      setError('确认候选失败，请刷新后重试。');
    }
  };

  const onSkip = async () => {
    if (!projectId || !selected) return;
    setFeedback('');
    setError('');
    try {
      const result = await api.skipStoryPlanningCardCandidate(projectId, selected.id);
      setFeedback(result.message);
      await load();
    } catch {
      setError('跳过候选失败，请刷新后重试。');
    }
  };

  return (
    <div>
      <h2>卡槽候选</h2>
      <div className="panel">
        这里展示从全书规划和章节目录中生成的角色、术语、势力和地点候选。候选卡不会自动进入正式设定，需作者确认后才会写入对应卡槽。
      </div>

      <div className="panel">
        <button type="button" onClick={onGenerate}>生成候选卡</button>
        <div style={{ marginTop: 12, display: 'flex', gap: 12 }}>
          <label>
            类型筛选
            <select value={cardTypeFilter} onChange={(e) => setCardTypeFilter(e.target.value as '' | StoryPlanningCardCandidateType)}>
              {cardTypeOptions.map((option) => (
                <option key={option.label} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>
          <label>
            状态筛选
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as '' | StoryPlanningCardCandidateStatus)}>
              {statusOptions.map((option) => (
                <option key={option.label} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {items.length === 0 ? (
        <EmptyState text="暂无候选卡，可先点击“生成候选卡”从全书规划与章节目录提取。" />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div className="panel">
            <h3>候选列表</h3>
            {items.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => onSelect(item.id)}
                style={{
                  display: 'block',
                  width: '100%',
                  textAlign: 'left',
                  marginBottom: 8,
                  border: selectedId === item.id ? '2px solid #4f46e5' : '1px solid #ddd',
                }}
              >
                {cardTypeLabel[item.card_type]}｜{item.name}｜{item.status}
              </button>
            ))}
          </div>

          <div className="panel">
            <h3>候选详情</h3>
            {selected ? (
              <>
                <p><b>名称：</b>{selected.name}</p>
                <p><b>类型：</b>{cardTypeLabel[selected.card_type]}</p>
                <p><b>状态：</b>{selected.status}</p>
                <p><b>摘要：</b>{selectedSummary}</p>
                <p><b>来源类型：</b>{selected.source_type}</p>
                <pre style={{ whiteSpace: 'pre-wrap', background: '#f8f8f8', padding: 8 }}>
                  {JSON.stringify(selected.payload || {}, null, 2)}
                </pre>
                {selected.status === 'pending' && (
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button type="button" onClick={onConfirm}>确认并写入卡槽</button>
                    <button type="button" onClick={onSkip}>跳过候选</button>
                  </div>
                )}
              </>
            ) : (
              <EmptyState text="请选择候选卡查看详情。" />
            )}
          </div>
        </div>
      )}

      {report && (
        <div className="panel">
          <h3>生成结果报告</h3>
          <p>已生成：{report.generated_count}，已跳过：{report.skipped_count}</p>
          {report.errors.length > 0 && <p>错误：{report.errors.join('；')}</p>}
          <ul>
            {report.items.map((item, idx) => (
              <li key={`${item.card_type}-${item.name}-${idx}`}>{item.card_type} / {item.name} / {item.status} / {item.message}</li>
            ))}
          </ul>
        </div>
      )}

      {feedback && <ActionSuccess text={feedback} />}
      {error && <ActionFailure text={error} />}
    </div>
  );
}
