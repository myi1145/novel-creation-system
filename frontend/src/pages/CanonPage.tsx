import { FormEvent, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ActionFailure, ActionSuccess, EmptyState, ErrorState, LoadingState } from '../components/Status';
import { useAsync } from '../features/useAsync';
import { toActionErrorMessage } from '../utils/actionError';

export function CanonPage() {
  const { projectId = '' } = useParams();
  const snapshots = useAsync<Awaited<ReturnType<typeof api.listCanonSnapshots>>>();
  const [title, setTitle] = useState('initial_snapshot');
  const [feedback, setFeedback] = useState('');
  const [feedbackErr, setFeedbackErr] = useState('');
  const [isInitializingCanon, setIsInitializingCanon] = useState(false);
  const [isRefreshingCanon, setIsRefreshingCanon] = useState(false);

  const reload = async () => {
    if (isRefreshingCanon) return;
    setIsRefreshingCanon(true);
    try {
      await snapshots.run(() => api.listCanonSnapshots(projectId));
    } finally {
      setIsRefreshingCanon(false);
    }
  };
  useEffect(() => { void reload(); }, [projectId]);

  const onInit = async (e: FormEvent) => {
    e.preventDefault();
    setFeedback(''); setFeedbackErr('');
    if (isInitializingCanon) return;
    setIsInitializingCanon(true);
    try {
      const snap = await api.initCanonSnapshot({ project_id: projectId, title, initial_rules: [], initial_characters: [] });
      setFeedback(`Canon 初始化成功：${snap.id}`);
      await reload();
    } catch (err) {
      setFeedbackErr(toActionErrorMessage('初始化 Canon', err, '请确认项目上下文与快照标题。'));
    } finally {
      setIsInitializingCanon(false);
    }
  };

  return <div><h2>Canon 快照</h2>
    <form onSubmit={onInit} className="panel"><input value={title} onChange={(e)=>setTitle(e.target.value)} /><button disabled={isInitializingCanon}>{isInitializingCanon ? '初始化中...' : '初始化初始 Canon'}</button><button type="button" disabled={isRefreshingCanon} onClick={() => void reload()}>{isRefreshingCanon ? '刷新中...' : '刷新快照'}</button></form>
    {(isInitializingCanon || isRefreshingCanon) && <LoadingState text={isInitializingCanon ? '正在初始化 Canon...' : '正在刷新 Canon 快照...'} />}
    {feedback && <ActionSuccess text={feedback} />} {feedbackErr && <ActionFailure text={feedbackErr} />}
    {snapshots.loading && <LoadingState />} {snapshots.error && <ErrorState text={snapshots.error} />}
    {snapshots.data?.length===0 && <EmptyState text="暂无快照"/>}
    <ul>{snapshots.data?.map((s)=><li key={s.id} className="panel"><div>{s.title} v{s.version_no}</div><pre>{JSON.stringify(s,null,2)}</pre></li>)}</ul>
  </div>;
}
