import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ActionFailure, ActionSuccess } from '../components/Status';
import { toActionErrorMessage } from '../utils/actionError';

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
  const [isPublishing, setIsPublishing] = useState(false);
  const [isRefreshingPublished, setIsRefreshingPublished] = useState(false);
  const [isRefreshingRecords, setIsRefreshingRecords] = useState(false);
  const [isSummarizing, setIsSummarizing] = useState(false);
  const [isLoadingLatestSummary, setIsLoadingLatestSummary] = useState(false);

  const run = async (action: () => Promise<void>, message: string, actionLabel: string, suggestion?: string) => {
    setFeedback(''); setError('');
    try { await action(); setFeedback(message); } catch (e) { setError(toActionErrorMessage(actionLabel, e, suggestion)); }
  };

  return <div><h2>已发布章节 / 摘要</h2>
    <div className="panel"><input value={draftId} onChange={(e)=>setDraftId(e.target.value)} placeholder="draft_id"/><button disabled={isPublishing} onClick={()=>void (async()=>{ if (isPublishing) return; setIsPublishing(true); try { await run(async()=>{await api.publishDraft({project_id:projectId,draft_id:draftId,published_by:'frontend_user'});},'已发布','发布章节','请检查草稿是否完成必要前置步骤。'); } finally { setIsPublishing(false); } })()}>{isPublishing ? '发布中...' : '发布'}</button></div>
    <div className="panel"><button disabled={isRefreshingPublished} onClick={()=>void (async()=>{ if (isRefreshingPublished) return; setIsRefreshingPublished(true); try { await run(async()=>setPublished(await api.listPublished(projectId)),'已加载已发布章节','刷新已发布章节'); } finally { setIsRefreshingPublished(false); } })()}>{isRefreshingPublished ? '加载中...' : '刷新已发布章节'}</button><button disabled={isRefreshingRecords} onClick={()=>void (async()=>{ if (isRefreshingRecords) return; setIsRefreshingRecords(true); try { await run(async()=>setRecords(await api.listPublishRecords(projectId)),'已加载发布记录','刷新发布记录'); } finally { setIsRefreshingRecords(false); } })()}>{isRefreshingRecords ? '加载中...' : '刷新发布记录'}</button></div>
    <div className="panel"><input value={publishedId} onChange={(e)=>setPublishedId(e.target.value)} placeholder="published_chapter_id"/><button disabled={isSummarizing} onClick={()=>void (async()=>{ if (isSummarizing) return; setIsSummarizing(true); try { await run(async()=>setSummary(await api.getSummary(projectId,publishedId)),'已加载单章摘要','查看单章摘要','请检查发布章节编号是否正确。'); } finally { setIsSummarizing(false); } })()}>{isSummarizing ? '加载中...' : '查看单章摘要'}</button><button disabled={isLoadingLatestSummary} onClick={()=>void (async()=>{ if (isLoadingLatestSummary) return; setIsLoadingLatestSummary(true); try { await run(async()=>setLatestSummary(await api.getLatestSummary(projectId)),'已加载 latest summary','查看 latest summary'); } finally { setIsLoadingLatestSummary(false); } })()}>{isLoadingLatestSummary ? '加载中...' : '查看 latest summary'}</button></div>
    {(isPublishing || isRefreshingPublished || isRefreshingRecords || isSummarizing || isLoadingLatestSummary) && <ActionSuccess text="正在执行请求，请稍候..." />}
    {feedback && <ActionSuccess text={feedback}/>} {error && <ActionFailure text={error}/>} 
    <pre className="panel">published={JSON.stringify(published,null,2)}</pre>
    <pre className="panel">records={JSON.stringify(records,null,2)}</pre>
    <pre className="panel">summary={JSON.stringify(summary,null,2)}</pre>
    <pre className="panel">latestSummary={JSON.stringify(latestSummary,null,2)}</pre>
  </div>;
}
