import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import { EmptyState, ErrorState, LoadingState } from '../components/Status';
import { useAsync } from '../features/useAsync';

const OBJECT_TYPES = ['characters', 'rules', 'open-loops', 'relationships'] as const;

export function ObjectsPage() {
  const { projectId = '' } = useParams();
  const [resource, setResource] = useState<(typeof OBJECT_TYPES)[number]>('characters');
  const [selectedId, setSelectedId] = useState('');
  const listState = useAsync<Awaited<ReturnType<typeof api.listObjects>>>();
  const historyState = useAsync<Awaited<ReturnType<typeof api.objectHistory>>>();

  useEffect(() => { void listState.run(() => api.listObjects(resource, projectId)); }, [resource, projectId]);

  return <div><h2>结构化对象库</h2>
    <div className="panel">{OBJECT_TYPES.map((t)=><button key={t} onClick={()=>setResource(t)}>{t}</button>)}</div>
    {listState.loading && <LoadingState />} {listState.error && <ErrorState text={listState.error} />} {listState.data?.length===0 && <EmptyState text="当前类型无对象"/>}
    <div className="grid">
      <ul>{listState.data?.map((o)=><li key={o.id} className="panel"><button onClick={()=>setSelectedId(String(o.logical_object_id || ''))}>详情</button><pre>{JSON.stringify(o,null,2)}</pre></li>)}</ul>
      <div>
        <h3>对象历史版本</h3>
        {selectedId && <button onClick={()=>void historyState.run(()=>api.objectHistory(resource, projectId, selectedId))}>查看历史</button>}
        {historyState.loading && <LoadingState text="历史加载中"/>}
        {historyState.error && <ErrorState text={historyState.error} />}
        <pre className="panel">{JSON.stringify(historyState.data,null,2)}</pre>
      </div>
    </div>
  </div>;
}
