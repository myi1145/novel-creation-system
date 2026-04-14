import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ActionFailure, ActionSuccess, EmptyState } from '../components/Status';

type VersionDiffCheck = {
  key: string;
  status: 'ok' | 'warning' | 'missing' | string;
  title: string;
  message: string;
};

type VersionDiffRef = {
  publish_record_id?: string;
  published_at?: string;
  draft_ref_id?: string;
  changeset_ref_id?: string;
  draft_id?: string;
  updated_at?: string;
  source_type?: string;
};

type VersionDiffPayload = {
  project_id: string;
  chapter_no: number;
  comparison_status: 'never_published' | 'no_current_work' | 'comparable' | string;
  recommendation: 'cannot_compare' | 'republish_not_needed' | 'republish_recommended' | string;
  summary: string;
  published_ref: VersionDiffRef;
  current_ref: VersionDiffRef;
  diff: {
    length_delta: number;
    paragraph_delta: number;
    changed_summary: string;
    change_level: 'none' | 'minor' | 'moderate' | 'major' | string;
  };
  checks: VersionDiffCheck[];
};

function toComparisonLabel(status: string): string {
  if (status === 'never_published') return '尚未发布';
  if (status === 'no_current_work') return '缺少当前工作内容';
  if (status === 'comparable') return '可正常对比';
  return status || '-';
}

function toRecommendationLabel(status: string): string {
  if (status === 'cannot_compare') return '暂时无法对比';
  if (status === 'republish_not_needed') return '暂不需要重新发布';
  if (status === 'republish_recommended') return '建议重新发布';
  return status || '-';
}

function toCheckStatus(status: string): string {
  if (status === 'ok') return '正常';
  if (status === 'warning') return '需关注';
  if (status === 'missing') return '缺失';
  return status || '-';
}

export function VersionDiffPage() {
  const { projectId = '', chapterNo = '' } = useParams();
  const chapterNoNum = Number(chapterNo);
  const [data, setData] = useState<VersionDiffPayload | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!projectId || !Number.isFinite(chapterNoNum) || chapterNoNum <= 0) return;
    let mounted = true;
    setIsLoading(true);
    setError('');
    void api
      .getVersionDiff(projectId, chapterNoNum)
      .then((payload) => {
        if (!mounted) return;
        setData(payload as VersionDiffPayload);
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

  const checks = useMemo(() => (Array.isArray(data?.checks) ? data.checks : []), [data?.checks]);

  return (
    <div>
      <h2>版本差异与重发建议</h2>
      <div className="panel">用于查看当前工作内容相对最近发布版本的变化，并判断是否建议重新发布。</div>

      {isLoading && <ActionSuccess text="加载中..." />}
      {error && <ActionFailure text={error} />}

      {!isLoading && !error && !data && <EmptyState text="需要“已发布版本 + 当前草稿”后才能对比。" />}

      {!isLoading && !error && data && (
        <>
          <div className="panel">
            <div>对比结论：<strong>{toComparisonLabel(data.comparison_status)}</strong></div>
            <div>重发建议：<strong>{toRecommendationLabel(data.recommendation)}</strong></div>
            <div>摘要：{data.summary || '-'}</div>
          </div>

          <div className="panel">
            <h3>变化摘要</h3>
            <div>字数变化：{typeof data.diff?.length_delta === 'number' ? data.diff.length_delta : '-'}</div>
            <div>段落变化：{typeof data.diff?.paragraph_delta === 'number' ? data.diff.paragraph_delta : '-'}</div>
            <div>变化级别：{data.diff?.change_level || '-'}</div>
            <div>变化说明：{data.diff?.changed_summary || '-'}</div>
          </div>

          <div className="panel">
            <h3>检查项</h3>
            {checks.length === 0 ? (
              <EmptyState text="当前没有检查项。" />
            ) : (
              <ul>
                {checks.map((check) => (
                  <li key={`${check.key}-${check.title}`}>
                    <div><strong>{check.title}</strong></div>
                    <div>状态：{toCheckStatus(check.status)}</div>
                    <div>说明：{check.message}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <details className="panel">
            <summary>调试信息（默认折叠）</summary>
            <div>发布记录编号：{data.published_ref?.publish_record_id || '-'}</div>
            <div>发布于：{data.published_ref?.published_at || '-'}</div>
            <div>来源草稿编号：{data.published_ref?.draft_ref_id || '-'}</div>
            <div>来源变更提案编号：{data.published_ref?.changeset_ref_id || '-'}</div>
            <div>当前草稿编号：{data.current_ref?.draft_id || '-'}</div>
            <div>当前草稿更新时间：{data.current_ref?.updated_at || '-'}</div>
            <div>当前草稿来源：{data.current_ref?.source_type || '-'}</div>
          </details>
        </>
      )}

      <div className="panel">
        <div className="project-nav">
          <Link to={`/projects/${projectId}/chapters/${chapterNoNum}/publish-history`}>回章节发布历史</Link>
          <Link to={`/projects/${projectId}/chapters/${chapterNoNum}/release-readiness`}>回发布前检查</Link>
          <Link to={`/projects/${projectId}/chapters/${chapterNoNum}/published-reader`}>阅读已发布章节</Link>
          <Link to={`/projects/${projectId}/published`}>回发布章节</Link>
        </div>
      </div>
    </div>
  );
}
