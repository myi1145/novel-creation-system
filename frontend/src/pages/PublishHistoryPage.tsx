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
  if (status === 'up_to_date') return '已与发布版本对齐';
  if (status === 'work_in_progress_after_publish') return '当前工作态晚于已发布态';
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
      .catch((e) => {
        if (!mounted) return;
        setError(e instanceof Error ? e.message : '获取章节发布历史失败');
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
      <div className="panel">用于查看本章发布版本、来源信息，以及当前工作态是否晚于最近发布态。</div>
      <div className="panel">project_id={projectId} | chapter_no={chapterNoNum}</div>
      {isLoading && <ActionSuccess text="加载中..." />}
      {error && <ActionFailure text={error} />}

      {!isLoading && !error && data && (
        <>
          <div className="panel">
            <h3>当前工作态关系</h3>
            <div>状态：<strong>{toRelationTitle(data.working_state_relation?.status || '')}</strong></div>
            <div>提示：{data.working_state_relation?.message || '-'}</div>
          </div>

          <div className="panel">
            <h3>最近一次发布</h3>
            {!data.latest_published ? (
              <EmptyState text="本章还没有正式发布记录。" />
            ) : (
              <div>
                <div>发布记录：{data.latest_published.publish_record_id}</div>
                <div>发布时间：{data.latest_published.published_at}</div>
                <div>来源草稿：{data.latest_published.draft_ref_id}</div>
                <div>来源变更提案：{data.latest_published.changeset_ref_id}</div>
                <div>摘要：{data.latest_published.summary}</div>
                <div>状态：{data.latest_published.status}</div>
              </div>
            )}
          </div>

          <div className="panel">
            <h3>历史发布列表</h3>
            {history.length === 0 ? (
              <EmptyState text="本章暂无历史发布记录。" />
            ) : (
              <ul>
                {history.map((item) => (
                  <li key={item.publish_record_id}>
                    <div>发布记录：{item.publish_record_id}</div>
                    <div>发布时间：{item.published_at}</div>
                    <div>来源草稿：{item.draft_ref_id}</div>
                    <div>来源变更提案：{item.changeset_ref_id}</div>
                    <div>摘要：{item.summary}</div>
                    <div>状态：{item.status}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}

      {!isLoading && !error && !data && <EmptyState text="还没有可展示的发布历史数据。" />}

      <div className="panel">
        <div className="project-nav">
          <Link to={`/projects/${projectId}/published`}>回发布章节</Link>
          <Link to={`/projects/${projectId}/chapters/${chapterNoNum}/release-readiness`}>回发布前检查</Link>
          <Link to={`/projects/${projectId}/chapters/${chapterNoNum}/version-diff`}>版本差异与重发建议</Link>
          <Link to={`/projects/${projectId}/chapters/${chapterNoNum}/published-reader`}>阅读已发布章节</Link>
          <Link to={`/projects/${projectId}/workbench`}>回工作台</Link>
        </div>
      </div>
    </div>
  );
}
