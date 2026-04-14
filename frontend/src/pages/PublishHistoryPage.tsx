import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ActionFailure, ActionSuccess, EmptyState } from '../components/Status';

type PublishHistoryItem = {
  publish_record_id: string;
  published_at: string;
  draft_ref_id: string;
  changeset_ref_id: string;
  summary: string;
  status: string;
};

type PublishHistoryRelation = {
  status: 'never_published' | 'up_to_date' | 'work_in_progress_after_publish' | string;
  message: string;
};

type PublishHistoryPayload = {
  project_id: string;
  chapter_no: number;
  latest_published: PublishHistoryItem | null;
  working_state_relation: PublishHistoryRelation;
  history: PublishHistoryItem[];
};

function toRelationTitle(status: string): string {
  if (status === 'never_published') return '尚未发布';
  if (status === 'up_to_date') return '当前版本已同步';
  if (status === 'work_in_progress_after_publish') return '当前工作内容晚于最近发布版本';
  return status || '-';
}

export function PublishHistoryPage() {
  const { projectId = '', chapterNo = '' } = useParams();
  const chapterNoNum = Number(chapterNo);
  const [data, setData] = useState<PublishHistoryPayload | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!projectId || !Number.isFinite(chapterNoNum) || chapterNoNum <= 0) return;
    let mounted = true;
    setIsLoading(true);
    setError('');
    void api
      .getPublishHistory(projectId, chapterNoNum)
      .then((payload) => {
        if (!mounted) return;
        setData(payload as PublishHistoryPayload);
      })
      .catch(() => {
        if (!mounted) return;
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

  const history: PublishHistoryItem[] = Array.isArray(data?.history) ? data.history : [];

  return (
    <div>
      <h2>章节发布历史</h2>
      <div className="panel">用于查看本章每次发布的时间、来源与记录。</div>
      {isLoading && <ActionSuccess text="加载中..." />}
      {error && <ActionFailure text={error} />}

      {!isLoading && !error && data && (
        <>
          <div className="panel">
            <h3>当前工作内容与最近发布版本</h3>
            <div>状态：<strong>{toRelationTitle(data.working_state_relation?.status || '')}</strong></div>
            <div>提示：{data.working_state_relation?.message || '-'}</div>
          </div>

          <div className="panel">
            <h3>最近一次发布</h3>
            {!data.latest_published ? (
              <EmptyState text="本章暂无发布记录。完成发布后可在此查看历史。" />
            ) : (
              <div>
                <div>发布时间：{data.latest_published.published_at}</div>
                <div>摘要：{data.latest_published.summary || '-'}</div>
              </div>
            )}
          </div>

          <div className="panel">
            <h3>历史发布列表</h3>
            {history.length === 0 ? (
              <EmptyState text="本章暂无发布记录。完成发布后可在此查看历史。" />
            ) : (
              <ul>
                {history.map((item) => (
                  <li key={item.publish_record_id}>
                    <div>发布时间：{item.published_at}</div>
                    <div>摘要：{item.summary || '-'}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <details className="panel">
            <summary>调试信息（默认折叠）</summary>
            {!data.latest_published ? (
              <div>暂无可展示的调试信息。</div>
            ) : (
              <div>
                <div>发布记录编号：{data.latest_published.publish_record_id}</div>
                <div>来源草稿编号：{data.latest_published.draft_ref_id}</div>
                <div>来源变更提案编号：{data.latest_published.changeset_ref_id}</div>
                <div>原始状态：{data.latest_published.status}</div>
              </div>
            )}
          </details>
        </>
      )}

      {!isLoading && !error && !data && <EmptyState text="还没有可展示的章节发布历史。" />}

      <div className="panel">
        <div className="project-nav">
          <Link to={`/projects/${projectId}/published`}>回发布章节</Link>
          <Link to={`/projects/${projectId}/chapters/${chapterNoNum}/release-readiness`}>回发布前检查</Link>
          <Link to={`/projects/${projectId}/chapters/${chapterNoNum}/version-diff`}>版本差异与重发建议</Link>
          <Link to={`/projects/${projectId}/chapters/${chapterNoNum}/published-reader`}>阅读已发布章节</Link>
          <Link to={`/projects/${projectId}/workbench`}>回创作工作台</Link>
        </div>
      </div>
    </div>
  );
}
