import { FormEvent, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ActionFailure, ActionSuccess, EmptyState, ErrorState, LoadingState } from '../components/Status';
import { useAsync } from '../features/useAsync';
import type { Dict } from '../types/api';
import type { CreativeObject } from '../types/domain';

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

interface CreateFormState {
  character_name: string;
  rule_name: string;
  description: string;
  loop_name: string;
  source_character_id: string;
  target_character_id: string;
  relation_type: string;
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

const DEFAULT_CREATE_FORM: CreateFormState = {
  character_name: '',
  rule_name: '',
  description: '',
  loop_name: '',
  source_character_id: '',
  target_character_id: '',
  relation_type: '',
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
  const [createForm, setCreateForm] = useState<CreateFormState>(DEFAULT_CREATE_FORM);
  const [createdObjectsByResource, setCreatedObjectsByResource] = useState<Record<ObjectResource, CreativeObject[]>>({
    characters: [],
    rules: [],
    'open-loops': [],
    relationships: [],
  });
  const [createFeedback, setCreateFeedback] = useState('');
  const [createErrorFeedback, setCreateErrorFeedback] = useState('');
  const [feedback, setFeedback] = useState('');
  const [errorFeedback, setErrorFeedback] = useState('');

  const listState = useAsync<Awaited<ReturnType<typeof api.listObjects>>>();
  const historyState = useAsync<Awaited<ReturnType<typeof api.objectHistory>>>();

  useEffect(() => {
    void listState.run(() => api.listObjects(resource, projectId));
    setSelectedId('');
    setFeedback('');
    setErrorFeedback('');
    setCreateFeedback('');
    setCreateErrorFeedback('');
  }, [resource, projectId]);

  const visibleObjects = useMemo(() => {
    const remoteObjects = listState.data || [];
    const localObjects = createdObjectsByResource[resource] || [];
    const merged = [...remoteObjects];
    localObjects.forEach((item) => {
      if (!merged.some((remoteItem) => remoteItem.id === item.id)) {
        merged.push(item);
      }
    });
    return merged;
  }, [createdObjectsByResource, listState.data, resource]);

  const selectedObject = useMemo(
    () => visibleObjects.find((item) => String(item.logical_object_id || '') === selectedId),
    [visibleObjects, selectedId],
  );

  const buildCreatePayload = (): Dict => {
    const basePayload = {
      project_id: projectId,
      source_ref: 'frontend_objects_page',
    };
    if (resource === 'characters') {
      return { ...basePayload, character_name: createForm.character_name.trim() };
    }
    if (resource === 'rules') {
      return {
        ...basePayload,
        rule_name: createForm.rule_name.trim(),
        description: createForm.description.trim(),
      };
    }
    if (resource === 'open-loops') {
      return { ...basePayload, loop_name: createForm.loop_name.trim() };
    }
    return {
      ...basePayload,
      source_character_id: createForm.source_character_id.trim(),
      target_character_id: createForm.target_character_id.trim(),
      relation_type: createForm.relation_type.trim(),
    };
  };

  const onSubmitCreate = async (e: FormEvent) => {
    e.preventDefault();
    if (!projectId) {
      setCreateErrorFeedback('缺少 project_id，无法创建对象。');
      return;
    }
    setCreateFeedback('');
    setCreateErrorFeedback('');
    try {
      const created = await api.createObject(resource, buildCreatePayload());
      setCreatedObjectsByResource((prev) => {
        const existing = prev[resource];
        if (existing.some((item) => item.id === created.id)) {
          return prev;
        }
        return {
          ...prev,
          [resource]: [...existing, created],
        };
      });
      const logicalId = String(created.logical_object_id || '');
      if (logicalId) {
        setSelectedId(logicalId);
      }
      setCreateFeedback(`创建成功：${created.id}`);
      void listState.run(() => api.listObjects(resource, projectId));
    } catch (err) {
      setCreateErrorFeedback(err instanceof Error ? err.message : '对象创建失败');
    }
  };

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
      {visibleObjects.length === 0 && (
        <div className="panel">
          <EmptyState text="当前类型无对象" />
          <form onSubmit={onSubmitCreate}>
            <h3>新建当前类型对象</h3>
            {resource === 'characters' && (
              <label>
                character_name
                <input
                  value={createForm.character_name}
                  onChange={(e) => setCreateForm((s) => ({ ...s, character_name: e.target.value }))}
                  required
                />
              </label>
            )}
            {resource === 'rules' && (
              <>
                <label>
                  rule_name
                  <input value={createForm.rule_name} onChange={(e) => setCreateForm((s) => ({ ...s, rule_name: e.target.value }))} required />
                </label>
                <label>
                  description
                  <input value={createForm.description} onChange={(e) => setCreateForm((s) => ({ ...s, description: e.target.value }))} required />
                </label>
              </>
            )}
            {resource === 'open-loops' && (
              <label>
                loop_name
                <input value={createForm.loop_name} onChange={(e) => setCreateForm((s) => ({ ...s, loop_name: e.target.value }))} required />
              </label>
            )}
            {resource === 'relationships' && (
              <>
                <label>
                  source_character_id
                  <input
                    value={createForm.source_character_id}
                    onChange={(e) => setCreateForm((s) => ({ ...s, source_character_id: e.target.value }))}
                    required
                  />
                </label>
                <label>
                  target_character_id
                  <input
                    value={createForm.target_character_id}
                    onChange={(e) => setCreateForm((s) => ({ ...s, target_character_id: e.target.value }))}
                    required
                  />
                </label>
                <label>
                  relation_type
                  <input
                    value={createForm.relation_type}
                    onChange={(e) => setCreateForm((s) => ({ ...s, relation_type: e.target.value }))}
                    required
                  />
                </label>
              </>
            )}
            <button type="submit" disabled={!projectId}>创建对象</button>
          </form>
          {createFeedback && <ActionSuccess text={createFeedback} />}
          {createErrorFeedback && <ActionFailure text={createErrorFeedback} />}
        </div>
      )}

      <div className="grid">
        <ul>
          {visibleObjects.map((o) => {
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
