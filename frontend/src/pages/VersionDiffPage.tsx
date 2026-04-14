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
  if (status === 'never_published') return '尚未发布无法对比';
  if (status === 'no_current_work') return '缺少当前工作态草稿';
  if (status === 'comparable') return '可对比';
  return status || '-';
}

function toRecommendationLabel(status: string): string {
  if (status === 'cannot_compare') return '尚未发布或无工作态，无法对比';
  if (status === 'republish_not_needed') return '暂不需要重新发布';
  if (status === 'republish_recommended') return '建议重新发布';
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
      .catch((e) => {
        if (!mounted) return;
        setError(e instanceof Error ? e.message : '获取版本差异失败');
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
      <div className="panel">用于对比当前工作态与最近发布版的轻量差异，并给出是否建议重新发布。</div>
      <div className="panel">project_id={projectId} | chapter_no={chapterNoNum}</div>

      {isLoading && <ActionSuccess text="加载中..." />}
      {error && <ActionFailure text={error} />}

      {!isLoading && !error && !data && <EmptyState text="还没有可展示的版本差异数据。" />}

      {!isLoading && !error && data && (
        <>
          <div className="panel">
            <div>对比状态：<strong>{toComparisonLabel(data.comparison_status)}</strong></div>
            <div>重发建议：<strong>{toRecommendationLabel(data.recommendation)}</strong></div>
            <div>摘要：{data.summary || '-'}</div>
          </div>

          <div className="panel">
            <h3>最近发布版</h3>
            <div>publish_record_id: {data.published_ref?.publish_record_id || '-'}</div>
            <div>published_at: {data.published_ref?.published_at || '-'}</div>
            <div>draft_ref_id: {data.published_ref?.draft_ref_id || '-'}</div>
            <div>changeset_ref_id: {data.published_ref?.changeset_ref_id || '-'}</div>
          </div>

          <div className="panel">
            <h3>当前工作态</h3>
            <div>draft_id: {data.current_ref?.draft_id || '-'}</div>
            <div>updated_at: {data.current_ref?.updated_at || '-'}</div>
            <div>source_type: {data.current_ref?.source_type || '-'}</div>
          </div>

          <div className="panel">
            <h3>轻量差异摘要</h3>
            <div>length_delta: {typeof data.diff?.length_delta === 'number' ? data.diff.length_delta : '-'}</div>
            <div>paragraph_delta: {typeof data.diff?.paragraph_delta === 'number' ? data.diff.paragraph_delta : '-'}</div>
            <div>change_level: {data.diff?.change_level || '-'}</div>
            <div>changed_summary: {data.diff?.changed_summary || '-'}</div>
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
                    <div>key: {check.key}</div>
                    <div>status: {check.status}</div>
                    <div>message: {check.message}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}

      <div className="panel">
        <div className="project-nav">
          <Link to={`/projects/${projectId}/chapters/${chapterNoNum}/publish-history`}>回章节发布历史</Link>
          <Link to={`/projects/${projectId}/chapters/${chapterNoNum}/release-readiness`}>回发布前检查</Link>
          <Link to={`/projects/${projectId}/published`}>回发布章节</Link>
        </div>
      </div>
    </div>
  );
}
