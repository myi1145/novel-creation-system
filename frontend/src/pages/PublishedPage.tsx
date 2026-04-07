import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ActionFailure, ActionSuccess } from '../components/Status';

export function PublishedPage() {
  const { projectId = '' } = useParams();
  const [draftId, setDraftId] = useState('');
  const [publishedId, setPublishedId] = useState('');
  const [published, setPublished] = useState<unknown>(null);
  const [records, setRecords] = useState<unknown>(null);
  const [summary, setSummary] = useState<unknown>(null);
  const [latestSummary, setLatestSummary] = useState<unknown>(null);
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');

  const run = async (action: () => Promise<void>, message: string) => {
    setFeedback(''); setError('');
    try { await action(); setFeedback(message); } catch (e) { setError(e instanceof Error ? e.message : '失败'); }
  };

  return <div><h2>已发布章节 / 摘要</h2>
    <div className="panel"><input value={draftId} onChange={(e)=>setDraftId(e.target.value)} placeholder="draft_id"/><button onClick={()=>void run(async()=>{await api.publishDraft({project_id:projectId,draft_id:draftId,published_by:'frontend_user'});},'已发布')}>发布</button></div>
    <div className="panel"><button onClick={()=>void run(async()=>setPublished(await api.listPublished(projectId)),'已加载已发布章节')}>刷新已发布章节</button><button onClick={()=>void run(async()=>setRecords(await api.listPublishRecords(projectId)),'已加载发布记录')}>刷新发布记录</button></div>
    <div className="panel"><input value={publishedId} onChange={(e)=>setPublishedId(e.target.value)} placeholder="published_chapter_id"/><button onClick={()=>void run(async()=>setSummary(await api.getSummary(projectId,publishedId)),'已加载单章摘要')}>查看单章摘要</button><button onClick={()=>void run(async()=>setLatestSummary(await api.getLatestSummary(projectId)),'已加载 latest summary')}>查看 latest summary</button></div>
    {feedback && <ActionSuccess text={feedback}/>} {error && <ActionFailure text={error}/>} 
    <pre className="panel">published={JSON.stringify(published,null,2)}</pre>
    <pre className="panel">records={JSON.stringify(records,null,2)}</pre>
    <pre className="panel">summary={JSON.stringify(summary,null,2)}</pre>
    <pre className="panel">latestSummary={JSON.stringify(latestSummary,null,2)}</pre>
  </div>;
}
