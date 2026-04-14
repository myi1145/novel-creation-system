import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ActionFailure, ActionSuccess, EmptyState } from '../components/Status';

type PublishedReaderPayload = {
  project_id: string;
  chapter_no: number;
  title: string;
  content: string;
  published_at: string;
  publish_record_id: string;
  draft_ref_id: string;
  changeset_ref_id: string;
  word_count: number;
  status: string;
};

export function PublishedChapterReaderPage() {
  const { projectId = '', chapterNo = '' } = useParams();
  const chapterNoNum = Number(chapterNo);
  const [data, setData] = useState<PublishedReaderPayload | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [copyFeedback, setCopyFeedback] = useState('');

  useEffect(() => {
    if (!projectId || !Number.isFinite(chapterNoNum) || chapterNoNum <= 0) return;
    let mounted = true;
    setIsLoading(true);
    setError('');
    setCopyFeedback('');
    void api
      .getPublishedReader(projectId, chapterNoNum)
      .then((payload) => {
        if (!mounted) return;
        setData(payload as PublishedReaderPayload);
      })
      .catch((e) => {
        if (!mounted) return;
        setData(null);
        setError(e instanceof Error ? e.message : '获取已发布章节阅读内容失败');
      })
      .finally(() => {
        if (!mounted) return;
        setIsLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [chapterNoNum, projectId]);

  const markdownUrl = useMemo(() => api.getPublishedMarkdownExportUrl(projectId, chapterNoNum), [chapterNoNum, projectId]);
  const txtUrl = useMemo(() => api.getPublishedTxtExportUrl(projectId, chapterNoNum), [chapterNoNum, projectId]);

  const handleCopyContent = async () => {
    if (!data?.content) {
      setCopyFeedback('暂无可复制正文。');
      return;
    }
    try {
      await navigator.clipboard.writeText(data.content);
      setCopyFeedback('正文复制成功。');
    } catch {
      setCopyFeedback('复制失败，请检查浏览器剪贴板权限后重试。');
    }
  };

  return (
    <div>
      <h2>已发布章节阅读</h2>
      <div className="panel">像阅读正式作品一样查看本章已发布成品，并支持复制与单章导出。</div>
      <div className="panel">project_id={projectId} | chapter_no={chapterNoNum}</div>

      {isLoading && <ActionSuccess text="加载中..." />}
      {error && <ActionFailure text={error} />}
      {copyFeedback && <ActionSuccess text={copyFeedback} />}

      {!isLoading && !error && !data && <EmptyState text="本章还没有正式发布内容。" />}

      {!isLoading && !error && data && (
        <>
          <div className="panel">
            <h3>{`第 ${data.chapter_no} 章 ${data.title}`}</h3>
            <div>发布时间：{data.published_at || '-'}</div>
            <div>字数：{typeof data.word_count === 'number' ? data.word_count : 0}</div>
          </div>

          <div className="panel">
            <button type="button" onClick={() => void handleCopyContent()}>复制正文</button>
            <a href={markdownUrl} download>
              下载 Markdown
            </a>
            <a href={txtUrl} download>
              下载 txt
            </a>
          </div>

          <div className="panel">
            <h3>正文</h3>
            <div style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>{data.content}</div>
          </div>
        </>
      )}

      <div className="panel">
        <div className="project-nav">
          <Link to={`/projects/${projectId}/published`}>回发布章节</Link>
          <Link to={`/projects/${projectId}/chapters/${chapterNoNum}/publish-history`}>回章节发布历史</Link>
          <Link to={`/projects/${projectId}/chapters/${chapterNoNum}/version-diff`}>回版本差异与重发建议</Link>
          <Link to={`/projects/${projectId}/workbench`}>回工作台</Link>
        </div>
      </div>
    </div>
  );
}
