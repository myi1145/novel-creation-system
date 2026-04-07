import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api, type ObjectResource } from '../api/client';
import { ActionFailure, ActionSuccess, EmptyState, ErrorState, LoadingState } from '../components/Status';
import { useAsync } from '../features/useAsync';

const OBJECT_TYPES: ObjectResource[] = ['characters', 'rules', 'open-loops', 'relationships'];

const UPDATE_FIELDS: Record<ObjectResource, string[]> = {
  characters: ['character_name', 'role_tags', 'current_state'],
  rules: ['rule_name', 'description', 'severity'],
  'open-loops': ['loop_name', 'status'],
  relationships: ['relation_type', 'relation_stage', 'metadata'],
};

export function ObjectsPage() {
  const { projectId = '' } = useParams();
  const [resource, setResource] = useState<ObjectResource>('characters');
  const [selectedId, setSelectedId] = useState('');
  const [rationale, setRationale] = useState('前端对象变更提议');
  const [sourceRef, setSourceRef] = useState('frontend_objects_page');
  const [updateJson, setUpdateJson] = useState('{}');
  const [restoreVersionNo, setRestoreVersionNo] = useState('1');
  const [retireReason, setRetireReason] = useState('不再使用');
  const [feedback, setFeedback] = useState('');
  const [actionError, setActionError] = useState('');
  const listState = useAsync<Awaited<ReturnType<typeof api.listObjects>>>();
  const historyState = useAsync<Awaited<ReturnType<typeof api.objectHistory>>>();

  useEffect(() => {
    void listState.run(() => api.listObjects(resource, projectId));
    setSelectedId('');
  }, [resource, projectId]);

  const selectedObject = useMemo(
    () => listState.data?.find((item) => String(item.logical_object_id || '') === selectedId),
    [listState.data, selectedId],
  );

  const runAction = async (action: () => Promise<unknown>, successText: string) => {
    setFeedback('');
    setActionError('');
    try {
      await action();
      setFeedback(successText);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '提交失败');
    }
  };

  const buildUpdatePayload = (): Record<string, unknown> => {
    const raw = JSON.parse(updateJson) as Record<string, unknown>;
    const picked: Record<string, unknown> = {
      project_id: projectId,
      rationale,
      source_ref: sourceRef,
      bind_to_canon: false,
    };
    UPDATE_FIELDS[resource].forEach((field) => {
      if (raw[field] !== undefined) {
        picked[field] = raw[field];
      }
    });
    return picked;
  };

  return (
    <div>
      <h2>结构化对象库</h2>
      <div className="panel">{OBJECT_TYPES.map((t) => <button key={t} onClick={() => setResource(t)}>{t}</button>)}</div>
      {listState.loading && <LoadingState />}
      {listState.error && <ErrorState text={listState.error} />}
      {listState.data?.length === 0 && <EmptyState text="当前类型无对象" />}
      <div className="grid">
        <ul>
          {listState.data?.map((o) => (
            <li key={o.id} className="panel">
              <button onClick={() => setSelectedId(String(o.logical_object_id || ''))}>详情/操作</button>
              <pre>{JSON.stringify(o, null, 2)}</pre>
            </li>
          ))}
        </ul>
        <div>
          <h3>对象详情与历史</h3>
          {!selectedId && <EmptyState text="请先在左侧选择一个对象" />}
          {selectedId && (
            <div className="panel">
              <p>logical_object_id: {selectedId}</p>
              <pre>{JSON.stringify(selectedObject, null, 2)}</pre>
              <button onClick={() => void historyState.run(() => api.objectHistory(resource, projectId, selectedId))}>查看历史</button>
              {historyState.loading && <LoadingState text="历史加载中" />}
              {historyState.error && <ErrorState text={historyState.error} />}
              <pre>{JSON.stringify(historyState.data, null, 2)}</pre>
            </div>
          )}

          <h3>对象侧 ChangeSet 提议入口（update / restore / retire）</h3>
          <div className="panel">
            <label>rationale<input value={rationale} onChange={(e) => setRationale(e.target.value)} /></label>
            <label>source_ref<input value={sourceRef} onChange={(e) => setSourceRef(e.target.value)} /></label>

            <p>update 字段（当前类型允许：{UPDATE_FIELDS[resource].join(', ')}）</p>
            <textarea value={updateJson} onChange={(e) => setUpdateJson(e.target.value)} rows={4} />
            <button
              disabled={!selectedId}
              onClick={() =>
                void runAction(
                  async () => api.proposeObjectUpdate(resource, selectedId, buildUpdatePayload()),
                  'update ChangeSet 已提议',
                )
              }
            >
              提议 update
            </button>

            <p>restore 版本号</p>
            <input value={restoreVersionNo} onChange={(e) => setRestoreVersionNo(e.target.value)} />
            <button
              disabled={!selectedId}
              onClick={() =>
                void runAction(
                  async () =>
                    api.proposeObjectRestore(resource, selectedId, {
                      project_id: projectId,
                      rationale,
                      source_ref: sourceRef,
                      restore_from_version_no: Number(restoreVersionNo),
                      bind_to_canon: false,
                    }),
                  'restore ChangeSet 已提议',
                )
              }
            >
              提议 restore
            </button>

            <p>retire 原因</p>
            <input value={retireReason} onChange={(e) => setRetireReason(e.target.value)} />
            <button
              disabled={!selectedId}
              onClick={() =>
                void runAction(
                  async () =>
                    api.proposeObjectRetire(resource, selectedId, {
                      project_id: projectId,
                      rationale,
                      source_ref: sourceRef,
                      retire_reason: retireReason,
                    }),
                  'retire ChangeSet 已提议',
                )
              }
            >
              提议 retire
            </button>
          </div>

          {feedback && <ActionSuccess text={feedback} />}
          {actionError && <ActionFailure text={actionError} />}
        </div>
      </div>
    </div>
  );
}
