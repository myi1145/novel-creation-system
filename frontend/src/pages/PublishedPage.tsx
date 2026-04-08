import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ApiError } from '../api/http';
import { ActionFailure, ActionSuccess } from '../components/Status';
import { toActionErrorMessage } from '../utils/actionError';
import { mergeProjectChainState } from '../features/projectState';

type PublishedListItem = {
  publishedChapterId: string;
  chapterNo?: number;
  title?: string;
  publishedAt?: string;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function getPublishedChapterIdFromPublishResult(result: unknown): string {
  const top = asRecord(result);
  if (!top) return '';

  const direct = typeof top.published_chapter_id === 'string' ? top.published_chapter_id : '';
  if (direct) return direct;

  const publishedChapter = asRecord(top.published_chapter);
  const nestedPublishedChapterId =
    (typeof publishedChapter?.id === 'string' && publishedChapter.id) ||
    (typeof publishedChapter?.published_chapter_id === 'string' && publishedChapter.published_chapter_id) ||
    '';
  if (nestedPublishedChapterId) return nestedPublishedChapterId;

  const publishRecord = asRecord(top.publish_record);
  return typeof publishRecord?.published_chapter_id === 'string' ? publishRecord.published_chapter_id : '';
}

function normalizePublishedList(payload: unknown): PublishedListItem[] {
  if (!Array.isArray(payload)) return [];
  return payload.reduce<PublishedListItem[]>((acc, item) => {
    const row = asRecord(item);
    if (!row) return acc;
    const publishedChapterId =
      (typeof row.id === 'string' && row.id) ||
      (typeof row.published_chapter_id === 'string' && row.published_chapter_id) ||
      '';
    if (!publishedChapterId) return acc;

    acc.push({
      publishedChapterId,
      chapterNo: typeof row.chapter_no === 'number' ? row.chapter_no : undefined,
      title: typeof row.title === 'string' ? row.title : undefined,
      publishedAt: typeof row.published_at === 'string' ? row.published_at : undefined,
    });
    return acc;
  }, []);
}

export function PublishedPage() {
  const { projectId = '' } = useParams();
  const [draftId, setDraftId] = useState('');
  const [publishedId, setPublishedId] = useState('');
  const [publishResult, setPublishResult] = useState<unknown>(null);
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
  const lastDraftStorageKey = useMemo(() => `workbench:${projectId}:lastDraftId`, [projectId]);
  const lastPublishedStorageKey = useMemo(() => `published:${projectId}:lastPublishedChapterId`, [projectId]);

  const publishedList = useMemo(() => normalizePublishedList(published), [published]);

  useEffect(() => {
    if (!projectId) return;
    const cachedPublishedId = window.localStorage.getItem(lastPublishedStorageKey);
    if (cachedPublishedId) {
      setPublishedId(cachedPublishedId);
    }
    const cachedDraftId = window.localStorage.getItem(lastDraftStorageKey);
    if (cachedDraftId) {
      setDraftId(cachedDraftId);
    }
  }, [lastDraftStorageKey, lastPublishedStorageKey, projectId]);

  const run = async (action: () => Promise<void>, message: string, actionLabel: string, suggestion?: string) => {
    setFeedback('');
    setError('');
    try {
      await action();
      setFeedback(message);
    } catch (e) {
      setError(toActionErrorMessage(actionLabel, e, suggestion));
    }
  };

  const handleGetSummary = async (idOverride?: string) => {
    const finalPublishedId = (idOverride || publishedId).trim();
    if (!finalPublishedId) {
      setFeedback('');
      setError('查看单章摘要失败。未选择已发布章节，请先从下方列表选择章节或填写 published_chapter_id。');
      return;
    }

    setIsSummarizing(true);
    setFeedback('');
    setError('');
    try {
      if (idOverride) {
        setPublishedId(finalPublishedId);
      }
      window.localStorage.setItem(lastPublishedStorageKey, finalPublishedId);
      const result = await api.getSummary(projectId, finalPublishedId);
      setSummary(result);
      setFeedback('已加载单章摘要');
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setError('查看单章摘要失败。未找到该章节摘要，请确认 published_chapter_id 来自当前项目且章节已成功发布。');
      } else if (e instanceof ApiError && e.status === 400) {
        setError('查看单章摘要失败。当前 published_chapter_id 无效，请检查是否选择了正确的已发布章节。');
      } else {
        setError(toActionErrorMessage('查看单章摘要', e, '请检查发布章节编号是否正确。'));
      }
    } finally {
      setIsSummarizing(false);
    }
  };

  return <div><h2>已发布章节 / 摘要</h2>
    <div className="panel"><input value={draftId} onChange={(e)=>setDraftId(e.target.value)} placeholder="draft_id"/><button disabled={isPublishing} onClick={()=>void (async()=>{ if (isPublishing) return; setIsPublishing(true); try { await run(async()=>{ const normalizedDraftId = draftId.trim(); const result = await api.publishDraft({project_id:projectId,draft_id:normalizedDraftId,published_by:'frontend_user'}); setPublishResult(result); if (normalizedDraftId) { window.localStorage.setItem(lastDraftStorageKey, normalizedDraftId); } const id = getPublishedChapterIdFromPublishResult(result); if (id) { setPublishedId(id); window.localStorage.setItem(lastPublishedStorageKey, id); mergeProjectChainState(projectId, { publishedChapterId: id }); setFeedback(`已发布，并自动带入 published_chapter_id：${id}`); } },'已发布','发布章节','请检查草稿是否完成必要前置步骤。'); } finally { setIsPublishing(false); } })()}>{isPublishing ? '发布中...' : '发布'}</button></div>
    <div className="panel"><button disabled={isRefreshingPublished} onClick={()=>void (async()=>{ if (isRefreshingPublished) return; setIsRefreshingPublished(true); try { await run(async()=>setPublished(await api.listPublished(projectId)),'已加载已发布章节','刷新已发布章节'); } finally { setIsRefreshingPublished(false); } })()}>{isRefreshingPublished ? '加载中...' : '刷新已发布章节'}</button><button disabled={isRefreshingRecords} onClick={()=>void (async()=>{ if (isRefreshingRecords) return; setIsRefreshingRecords(true); try { await run(async()=>setRecords(await api.listPublishRecords(projectId)),'已加载发布记录','刷新发布记录'); } finally { setIsRefreshingRecords(false); } })()}>{isRefreshingRecords ? '加载中...' : '刷新发布记录'}</button></div>
    <div className="panel"><input value={publishedId} onChange={(e)=>setPublishedId(e.target.value)} placeholder="published_chapter_id"/><button disabled={isSummarizing} onClick={()=>void handleGetSummary()}>{isSummarizing ? '加载中...' : '查看单章摘要'}</button><button disabled={isLoadingLatestSummary} onClick={()=>void (async()=>{ if (isLoadingLatestSummary) return; setIsLoadingLatestSummary(true); try { await run(async()=>setLatestSummary(await api.getLatestSummary(projectId)),'已加载 latest summary','查看 latest summary'); } finally { setIsLoadingLatestSummary(false); } })()}>{isLoadingLatestSummary ? '加载中...' : '查看 latest summary'}</button></div>
    <div className="panel"><small>提示：查看单章摘要需要 published_chapter_id；查看 latest summary 直接按项目获取最新摘要，不依赖手填单章 ID。</small></div>
    {publishedList.length > 0 && (
      <div className="panel">
        <h3>已发布章节（可直接用于摘要）</h3>
        <ul>
          {publishedList.map((item) => (
            <li key={item.publishedChapterId}>
              <div>
                <strong>{item.publishedChapterId}</strong>
                {typeof item.chapterNo === 'number' ? ` | chapter_no: ${item.chapterNo}` : ''}
                {item.title ? ` | title: ${item.title}` : ''}
                {item.publishedAt ? ` | published_at: ${item.publishedAt}` : ''}
              </div>
              <button type="button" onClick={() => { setPublishedId(item.publishedChapterId); window.localStorage.setItem(lastPublishedStorageKey, item.publishedChapterId); setFeedback(`已带入 published_chapter_id：${item.publishedChapterId}`); setError(''); }}>使用此 ID</button>
              <button type="button" disabled={isSummarizing} onClick={()=>void handleGetSummary(item.publishedChapterId)}>查看摘要</button>
            </li>
          ))}
        </ul>
      </div>
    )}
    <div className="panel"><div className="project-nav"><Link to={`/projects/${projectId}/overview`}>回项目概览</Link><Link to={`/projects/${projectId}/workbench`}>回当前章工作台</Link><Link to={`/projects/${projectId}/changesets`}>去 ChangeSet</Link></div></div>
    {(isPublishing || isRefreshingPublished || isRefreshingRecords || isSummarizing || isLoadingLatestSummary) && <ActionSuccess text="正在执行请求，请稍候..." />}
    {feedback && <ActionSuccess text={feedback}/>} {error && <ActionFailure text={error}/>} 
    <pre className="panel">publishResult={JSON.stringify(publishResult,null,2)}</pre>
    <pre className="panel">published={JSON.stringify(published,null,2)}</pre>
    <pre className="panel">records={JSON.stringify(records,null,2)}</pre>
    <pre className="panel">summary={JSON.stringify(summary,null,2)}</pre>
    <pre className="panel">latestSummary={JSON.stringify(latestSummary,null,2)}</pre>
  </div>;
}
