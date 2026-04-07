import { FormEvent, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ActionFailure, ActionSuccess, EmptyState, ErrorState, LoadingState } from '../components/Status';
import { useAsync } from '../features/useAsync';
import type { Dict } from '../types/api';

const OBJECT_TYPES = ['characters', 'rules', 'open-loops', 'relationships'] as const;

type ObjectResource = (typeof OBJECT_TYPES)[number];
type ProposalAction = 'update' | 'restore' | 'retire';

interface ProposalFormState {
  rationale: string;
  source_ref: string;
  bind_to_canon: boolean;
  update_payload_json: string;
  restore_mode: 'version_no' | 'version_id';
  restore_value: string;
  retire_reason: string;
}

const DEFAULT_FORM: ProposalFormState = {
  rationale: '对象修正提议',
  source_ref: 'frontend_objects_page',
  bind_to_canon: false,
  update_payload_json: '{}',
  restore_mode: 'version_no',
  restore_value: '1',
  retire_reason: '',
};

const UPDATE_FIELD_HINT: Record<ObjectResource, string> = {
  characters: '{"character_name":"新角色名","role_tags":["主角"]}',
  rules: '{"rule_name":"规则名","description":"规则描述","severity":"hard"}',
  'open-loops': '{"loop_name":"伏笔名","status":"open"}',
  relationships: '{"relation_type":"师徒","relation_stage":"established"}',
};

export function ObjectsPage() {
  const { projectId = '' } = useParams();
  const [resource, setResource] = useState<ObjectResource>('characters');
  const [selectedId, setSelectedId] = useState('');
  const [proposalAction, setProposalAction] = useState<ProposalAction>('update');
  const [proposalForm, setProposalForm] = useState<ProposalFormState>(DEFAULT_FORM);
  const [feedback, setFeedback] = useState('');
  const [errorFeedback, setErrorFeedback] = useState('');

  const listState = useAsync<Awaited<ReturnType<typeof api.listObjects>>>();
  const historyState = useAsync<Awaited<ReturnType<typeof api.objectHistory>>>();

  useEffect(() => {
    void listState.run(() => api.listObjects(resource, projectId));
    setSelectedId('');
    setFeedback('');
    setErrorFeedback('');
  }, [resource, projectId]);

  const selectedObject = useMemo(
    () => listState.data?.find((item) => String(item.logical_object_id || '') === selectedId),
    [listState.data, selectedId],
  );

  const onSubmitProposal = async (e: FormEvent) => {
    e.preventDefault();
    if (!selectedId) {
      setErrorFeedback('请先在左侧选择对象。');
      return;
    }
    setFeedback('');
    setErrorFeedback('');

    try {
      let response;
      if (proposalAction === 'update') {
        const parsed = JSON.parse(proposalForm.update_payload_json || '{}') as Dict;
        response = await api.proposeObjectUpdate(resource, selectedId, {
          project_id: projectId,
          rationale: proposalForm.rationale,
          source_ref: proposalForm.source_ref,
          bind_to_canon: proposalForm.bind_to_canon,
          ...parsed,
        });
      } else if (proposalAction === 'restore') {
        response = await api.proposeObjectRestore(resource, selectedId, {
          project_id: projectId,
          rationale: proposalForm.rationale,
          source_ref: proposalForm.source_ref,
          bind_to_canon: proposalForm.bind_to_canon,
          ...(proposalForm.restore_mode === 'version_no'
            ? { restore_from_version_no: Number(proposalForm.restore_value) }
            : { restore_from_version_id: proposalForm.restore_value }),
        });
      } else {
        response = await api.proposeObjectRetire(resource, selectedId, {
          project_id: projectId,
          rationale: proposalForm.rationale,
          source_ref: proposalForm.source_ref,
          retire_reason: proposalForm.retire_reason || undefined,
        });
      }
      setFeedback(`提议已创建：${response.id}（可前往 ChangeSet 页面审批）`);
    } catch (err) {
      setErrorFeedback(err instanceof Error ? err.message : '提议创建失败');
    }
  };

  return (
    <div>
      <h2>结构化对象库</h2>
      <div className="panel">项目：{projectId || '-'}</div>
      <div className="panel">
        {OBJECT_TYPES.map((t) => (
          <button key={t} onClick={() => setResource(t)} disabled={resource === t}>
            {t}
          </button>
        ))}
      </div>

      {listState.loading && <LoadingState />}
      {listState.error && <ErrorState text={listState.error} />}
      {listState.data?.length === 0 && <EmptyState text="当前类型无对象" />}

      <div className="grid">
        <ul>
          {listState.data?.map((o) => {
            const logicalId = String(o.logical_object_id || '');
            return (
              <li key={o.id} className="panel">
                <button onClick={() => setSelectedId(logicalId)} disabled={!logicalId}>
                  选择对象
                </button>
                <pre>{JSON.stringify(o, null, 2)}</pre>
              </li>
            );
          })}
        </ul>

        <div>
          <h3>对象历史版本</h3>
          {selectedId && (
            <button onClick={() => void historyState.run(() => api.objectHistory(resource, projectId, selectedId))}>
              查看历史
            </button>
          )}
          {historyState.loading && <LoadingState text="历史加载中" />}
          {historyState.error && <ErrorState text={historyState.error} />}
          <pre className="panel">{JSON.stringify(historyState.data, null, 2)}</pre>

          <h3>发起对象 ChangeSet 提议</h3>
          <form onSubmit={onSubmitProposal} className="panel">
            <div>当前对象 logical_object_id：{selectedId || '-'}</div>
            <label>
              动作
              <select value={proposalAction} onChange={(e) => setProposalAction(e.target.value as ProposalAction)}>
                <option value="update">update 提议</option>
                <option value="restore">restore 提议</option>
                <option value="retire">retire 提议</option>
              </select>
            </label>
            <label>
              rationale
              <input value={proposalForm.rationale} onChange={(e) => setProposalForm((s) => ({ ...s, rationale: e.target.value }))} required />
            </label>
            <label>
              source_ref
              <input value={proposalForm.source_ref} onChange={(e) => setProposalForm((s) => ({ ...s, source_ref: e.target.value }))} required />
            </label>

            {(proposalAction === 'update' || proposalAction === 'restore') && (
              <label>
                bind_to_canon
                <input
                  type="checkbox"
                  checked={proposalForm.bind_to_canon}
                  onChange={(e) => setProposalForm((s) => ({ ...s, bind_to_canon: e.target.checked }))}
                />
              </label>
            )}

            {proposalAction === 'update' && (
              <label>
                更新字段 JSON（仅填写该对象支持的字段）
                <textarea
                  rows={6}
                  value={proposalForm.update_payload_json}
                  placeholder={UPDATE_FIELD_HINT[resource]}
                  onChange={(e) => setProposalForm((s) => ({ ...s, update_payload_json: e.target.value }))}
                />
              </label>
            )}

            {proposalAction === 'restore' && (
              <>
                <label>
                  恢复方式
                  <select
                    value={proposalForm.restore_mode}
                    onChange={(e) => setProposalForm((s) => ({ ...s, restore_mode: e.target.value as ProposalFormState['restore_mode'] }))}
                  >
                    <option value="version_no">按版本号</option>
                    <option value="version_id">按版本ID</option>
                  </select>
                </label>
                <label>
                  {proposalForm.restore_mode === 'version_no' ? 'restore_from_version_no' : 'restore_from_version_id'}
                  <input
                    value={proposalForm.restore_value}
                    onChange={(e) => setProposalForm((s) => ({ ...s, restore_value: e.target.value }))}
                    required
                  />
                </label>
              </>
            )}

            {proposalAction === 'retire' && (
              <label>
                retire_reason（可选）
                <input
                  value={proposalForm.retire_reason}
                  onChange={(e) => setProposalForm((s) => ({ ...s, retire_reason: e.target.value }))}
                  placeholder="例如：剧情废弃"
                />
              </label>
            )}
            <button type="submit" disabled={!selectedObject || !projectId}>提交提议</button>
          </form>
          {feedback && <ActionSuccess text={feedback} />}
          {feedback && projectId && (
            <div className="panel">
              <Link to={`/projects/${projectId}/changesets`}>前往 ChangeSet 页继续审批 / 应用</Link>
            </div>
          )}
          {errorFeedback && <ActionFailure text={errorFeedback} />}
        </div>
      </div>
    </div>
  );
}
