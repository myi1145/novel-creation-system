import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ActionFailure, ActionSuccess, EmptyState } from '../components/Status';

type ReleaseReadinessCheck = {
  key: string;
  status: 'ok' | 'warning' | 'missing' | string;
  title: string;
  message: string;
  next_action: string;
  target: string;
};

type ReleaseReadinessPayload = {
  project_id: string;
  chapter_no: number;
  overall_status: 'ready_to_publish' | 'needs_attention' | string;
  summary: string;
  checks: ReleaseReadinessCheck[];
};

export function ReleaseReadinessPage() {
  const { projectId = '', chapterNo = '' } = useParams();
  const chapterNoNum = Number(chapterNo);
  const [data, setData] = useState<ReleaseReadinessPayload | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!projectId || !Number.isFinite(chapterNoNum) || chapterNoNum <= 0) return;
    let mounted = true;
    setIsLoading(true);
    setError('');
    void api
      .getReleaseReadiness(projectId, chapterNoNum)
      .then((payload) => {
        if (!mounted) return;
        setData(payload as ReleaseReadinessPayload);
      })
      .catch((e) => {
        if (!mounted) return;
        setError(e instanceof Error ? e.message : '获取发布前一致性验收失败');
      })
      .finally(() => {
        if (!mounted) return;
        setIsLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [chapterNoNum, projectId]);

  const checks = Array.isArray(data?.checks) ? data.checks : [];

  return (
    <div>
      <h2>发布前一致性验收</h2>
      <div className="panel">project_id={projectId} | chapter_no={chapterNoNum}</div>
      {isLoading && <ActionSuccess text="加载中..." />}
      {error && <ActionFailure text={error} />}
      {!isLoading && !error && !data && <EmptyState text="暂无验收数据" />}
      {data && (
        <>
          <div className="panel">
            <div>总状态：<strong>{data.overall_status}</strong></div>
            <div>总结：{data.summary}</div>
          </div>
          {checks.length === 0 ? (
            <EmptyState text="当前未返回检查项" />
          ) : (
            checks.map((check) => (
              <div key={check.key} className="panel">
                <h3>{check.title}</h3>
                <div>状态：{check.status}</div>
                <div>说明：{check.message}</div>
                <div>下一步：{check.next_action}</div>
                <Link to={check.target}>去处理</Link>
              </div>
            ))
          )}
        </>
      )}
      <div className="panel">
        <div className="project-nav">
          <Link to={`/projects/${projectId}/workbench`}>回工作台</Link>
          <Link to={`/projects/${projectId}/published`}>回发布页</Link>
        </div>
      </div>
    </div>
  );
}
