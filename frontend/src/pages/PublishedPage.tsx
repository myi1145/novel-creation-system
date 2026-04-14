import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ApiError } from '../api/http';
import { ActionFailure, ActionSuccess, EmptyState } from '../components/Status';
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
  const [chapterNoForReadiness, setChapterNoForReadiness] = useState('1');
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
      setError('请先在下方选择已发布章节，再查看摘要。');
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
      setFeedback('已加载单章摘要。');
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setError('没有找到对应内容，请确认章节是否已生成或发布。');
      } else if (e instanceof ApiError && e.status === 400) {
        setError('章节编号无效，请重新选择已发布章节。');
      } else {
        setError(toActionErrorMessage('查看单章摘要', e, '请稍后重试。'));
      }
    } finally {
      setIsSummarizing(false);
    }
  };

  return <div><h2>发布章节</h2>
    <div className="panel">用于把当前章节发布为正式版本。发布前建议先完成质量检查、变更提案与发布前检查。</div>
    <div className="panel"><input value={draftId} onChange={(e)=>setDraftId(e.target.value)} placeholder="请输入草稿编号"/><button disabled={isPublishing} onClick={()=>void (async()=>{ if (isPublishing) return; setIsPublishing(true); try { await run(async()=>{ const normalizedDraftId = draftId.trim(); const result = await api.publishDraft({project_id:projectId,draft_id:normalizedDraftId,published_by:'frontend_user'}); setPublishResult(result); if (normalizedDraftId) { window.localStorage.setItem(lastDraftStorageKey, normalizedDraftId); } const id = getPublishedChapterIdFromPublishResult(result); if (id) { setPublishedId(id); window.localStorage.setItem(lastPublishedStorageKey, id); mergeProjectChainState(projectId, { publishedChapterId: id }); setFeedback('发布成功，已自动带入本次章节。'); } },'已发布章节。','发布章节','请先确认前置流程已完成。'); } finally { setIsPublishing(false); } })()}>{isPublishing ? '发布中...' : '发布章节'}</button></div>
    <div className="panel"><button disabled={isRefreshingPublished} onClick={()=>void (async()=>{ if (isRefreshingPublished) return; setIsRefreshingPublished(true); try { await run(async()=>setPublished(await api.listPublished(projectId)),'已更新章节列表。','更新章节列表'); } finally { setIsRefreshingPublished(false); } })()}>{isRefreshingPublished ? '加载中...' : '更新章节列表'}</button><button disabled={isRefreshingRecords} onClick={()=>void (async()=>{ if (isRefreshingRecords) return; setIsRefreshingRecords(true); try { await run(async()=>setRecords(await api.listPublishRecords(projectId)),'已更新发布记录。','更新发布记录'); } finally { setIsRefreshingRecords(false); } })()}>{isRefreshingRecords ? '加载中...' : '更新发布记录'}</button></div>
    <div className="panel"><input value={publishedId} onChange={(e)=>setPublishedId(e.target.value)} placeholder="请输入已发布章节编号"/><button disabled={isSummarizing} onClick={()=>void handleGetSummary()}>{isSummarizing ? '加载中...' : '查看单章摘要'}</button><button disabled={isLoadingLatestSummary} onClick={()=>void (async()=>{ if (isLoadingLatestSummary) return; setIsLoadingLatestSummary(true); try { await run(async()=>setLatestSummary(await api.getLatestSummary(projectId)),'已加载最新章节摘要。','查看最新章节摘要'); } finally { setIsLoadingLatestSummary(false); } })()}>{isLoadingLatestSummary ? '加载中...' : '查看最新章节摘要'}</button></div>
    <div className="panel"><small>提示：建议先从章节列表中选择章节，再查看摘要。</small></div>
    {publishedList.length > 0 ? (
      <div className="panel">
        <h3>已发布章节</h3>
        <ul>
          {publishedList.map((item) => (
            <li key={item.publishedChapterId}>
              <div>
                <strong>{typeof item.chapterNo === 'number' ? `第 ${item.chapterNo} 章` : '章节'}</strong>
                {item.title ? `｜${item.title}` : ''}
                {item.publishedAt ? `｜发布时间：${item.publishedAt}` : ''}
              </div>
              <button type="button" onClick={() => { setPublishedId(item.publishedChapterId); window.localStorage.setItem(lastPublishedStorageKey, item.publishedChapterId); setFeedback('已带入该章节，可继续查看摘要。'); setError(''); }}>带入该章节并查看摘要</button>
              <button type="button" disabled={isSummarizing} onClick={()=>void handleGetSummary(item.publishedChapterId)}>查看单章摘要</button>
            </li>
          ))}
        </ul>
      </div>
    ) : (
      <EmptyState text="还没有已发布章节，请先完成发布章节。" />
    )}
    <div className="panel"><div className="project-nav"><Link to={`/projects/${projectId}/overview`}>回项目概览</Link><Link to={`/projects/${projectId}/workbench`}>回创作工作台</Link><Link to={`/projects/${projectId}/changesets`}>查看变更提案</Link></div></div>
    <div className="panel">
      <label>
        章节号
        <input value={chapterNoForReadiness} onChange={(e) => setChapterNoForReadiness(e.target.value)} />
      </label>
      <Link to={`/projects/${projectId}/chapters/${Number(chapterNoForReadiness) || 1}/release-readiness`}>发布前检查</Link>
      <Link to={`/projects/${projectId}/chapters/${Number(chapterNoForReadiness) || 1}/publish-history`}>章节发布历史</Link>
      <Link to={`/projects/${projectId}/chapters/${Number(chapterNoForReadiness) || 1}/version-diff`}>版本差异与重发建议</Link>
      <Link to={`/projects/${projectId}/chapters/${Number(chapterNoForReadiness) || 1}/published-reader`}>阅读已发布章节</Link>
    </div>
    {(isPublishing || isRefreshingPublished || isRefreshingRecords || isSummarizing || isLoadingLatestSummary) && <ActionSuccess text="正在处理，请稍候..." />}
    {feedback && <ActionSuccess text={feedback}/>} {error && <ActionFailure text={error}/>} 
    <details className="panel"><summary>调试信息（默认折叠）</summary>
      <pre>publishResult={JSON.stringify(publishResult,null,2)}</pre>
      <pre>published={JSON.stringify(published,null,2)}</pre>
      <pre>records={JSON.stringify(records,null,2)}</pre>
      <pre>summary={JSON.stringify(summary,null,2)}</pre>
      <pre>latestSummary={JSON.stringify(latestSummary,null,2)}</pre>
    </details>
  </div>;
}
