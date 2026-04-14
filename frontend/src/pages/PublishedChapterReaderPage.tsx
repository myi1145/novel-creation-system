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
      .catch(() => {
        if (!mounted) return;
        setData(null);
        setError('加载失败，请稍后重试。');
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
      <div className="panel">用于阅读、复制和导出已经发布的章节成品。</div>

      {isLoading && <ActionSuccess text="加载中..." />}
      {error && <ActionFailure text={error} />}
      {copyFeedback && <ActionSuccess text={copyFeedback} />}

      {!isLoading && !error && !data && <EmptyState text="本章尚未发布。请先在“发布章节”页面完成发布。" />}

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
              导出 Markdown
            </a>
            <a href={txtUrl} download>
              导出 TXT
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
          <Link to={`/projects/${projectId}/workbench`}>回创作工作台</Link>
        </div>
      </div>
    </div>
  );
}
