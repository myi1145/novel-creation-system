import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ActionFailure, ActionSuccess, EmptyState, LoadingState } from '../components/Status';
import { mergeProjectChainState, readMergedProjectChainState } from '../features/projectState';

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function asRunSummary(value: unknown) {
  const row = asRecord(value);
  if (!row) return null;
  return {
    id: String(row.id || row.workflow_run_id || '-'),
    runType: String(row.run_type || row.workflow_type || '-'),
    status: String(row.status || row.run_status || '-'),
    currentStep: String(row.current_step || row.current_stage || row.current_node || '-'),
    updatedAt: String(row.updated_at || row.last_updated_at || '-'),
    attentionRequired: Boolean(row.attention_required),
  };
}

export function OverviewPage() {
  const { projectId = '' } = useParams();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [projectName, setProjectName] = useState('');
  const [currentChapterNo, setCurrentChapterNo] = useState(1);
  const [canonHint, setCanonHint] = useState('');
  const [latestSummaryHint, setLatestSummaryHint] = useState('');
  const [changesetPendingCount, setChangesetPendingCount] = useState(0);
  const [latestRun, setLatestRun] = useState<ReturnType<typeof asRunSummary>>(null);
  const [nextActionHint, setNextActionHint] = useState('');
  const [feedback, setFeedback] = useState('');

  const chainState = useMemo(() => readMergedProjectChainState(projectId), [projectId, loading]);

  useEffect(() => {
    if (!projectId) return;
    setLoading(true);
    setError('');
    setFeedback('');
    void Promise.all([
      api.listProjects(),
      api.listCanonSnapshots(projectId),
      api.getLatestSummary(projectId),
      api.listChangeSets(),
      api.listWorkflowRuns(projectId),
    ])
      .then(([projects, snapshots, latestSummary, changeSets, runs]) => {
        const currentProject = projects.find((item) => item.id === projectId);
        setProjectName(currentProject?.project_name || projectId);
        setCurrentChapterNo(currentProject?.current_chapter_no || chainState.currentChapterNo || 1);

        const sortedSnapshots = [...snapshots].sort((a, b) => Number(b.version_no || 0) - Number(a.version_no || 0));
        const lastSnapshot = sortedSnapshots[0];
        setCanonHint(lastSnapshot ? `${lastSnapshot.title} / v${lastSnapshot.version_no}` : '暂无 Canon 快照');

        const summaryText = asRecord(latestSummary);
        const latestSummaryTitle = String(summaryText?.summary_title || summaryText?.title || summaryText?.summary || '').trim();
        setLatestSummaryHint(latestSummaryTitle || '暂无 latest summary');

        const pending = changeSets.filter((item) => String(item.project_id || '') === projectId && String(item.status || '').toLowerCase().includes('pending'));
        setChangesetPendingCount(pending.length);

        const sortedRuns = [...runs].sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')));
        const runSummary = asRunSummary(sortedRuns[0]);
        setLatestRun(runSummary);

        const hasAttentionRun = sortedRuns.some((item) => Boolean(item.attention_required));
        const hasBlockedRun = sortedRuns.some((item) => {
          const status = String(item.status || '').toLowerCase();
          return status.includes('blocked') || status.includes('failed') || status.includes('error');
        });
        mergeProjectChainState(projectId, {
          currentChapterNo: currentProject?.current_chapter_no || chainState.currentChapterNo || 1,
          hasPendingChangeset: pending.length > 0,
          hasAttentionRun,
          hasBlockedRun,
          latestWorkflowRunId: runSummary?.id || '',
        });

        if (hasBlockedRun) {
          setNextActionHint('建议先进入工作流运行中心处理阻断 run，再继续章节流程。');
        } else if (pending.length > 0) {
          setNextActionHint('建议先审批待处理 ChangeSet，避免 Canon 状态长期漂移。');
        } else if (chainState.draftId) {
          setNextActionHint('建议从当前草稿继续 Gate → ChangeSet → Publish。');
        } else {
          setNextActionHint('建议进入当前章工作台继续章节主链。');
        }

        setFeedback('项目概览已刷新');
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : '项目概览加载失败');
      })
      .finally(() => {
        setLoading(false);
      });
  }, [projectId]);

  return (
    <div>
      <h2>项目概览</h2>
      <div className="panel">项目：{projectName}</div>
      {loading && <LoadingState text="概览加载中..." />}
      {feedback && <ActionSuccess text={feedback} />}
      {error && <ActionFailure text={error} />}

      <div className="panel">
        <h3>当前项目状态</h3>
        <div>current_chapter_no：{currentChapterNo}</div>
        <div>最近 goal_id：{chainState.goalId || '-'}</div>
        <div>最近 blueprint_id：{chainState.blueprintId || '-'}</div>
        <div>最近 draft_id：{chainState.draftId || '-'}</div>
        <div>最近 published_chapter_id：{chainState.publishedChapterId || '-'}</div>
        <div>Canon 状态：{canonHint}</div>
        <div>latest summary：{latestSummaryHint}</div>
        <div>待审批 ChangeSet：{changesetPendingCount}</div>
      </div>

      <div className="panel">
        <h3>最近 workflow run</h3>
        {!latestRun ? (
          <EmptyState text="当前项目暂无 run" />
        ) : (
          <div>
            <div>run_id：{latestRun.id}</div>
            <div>类型：{latestRun.runType}</div>
            <div>状态：{latestRun.status}</div>
            <div>当前步骤：{latestRun.currentStep}</div>
            <div>更新时间：{latestRun.updatedAt}</div>
            {latestRun.attentionRequired && <div>attention required：是</div>}
            <Link to={`/projects/${projectId}/workflows`}>进入运行中心查看详情</Link>
          </div>
        )}
      </div>

      <div className="panel">
        <h3>建议下一步</h3>
        <div>{nextActionHint || '请先刷新页面加载项目状态。'}</div>
      </div>

      <div className="panel">
        <h3>继续处理</h3>
        <div className="project-nav">
          <Link to={`/projects/${projectId}/workbench`}>继续当前章工作台</Link>
          <Link to={`/projects/${projectId}/gates`}>去 Gate</Link>
          <Link to={`/projects/${projectId}/changesets`}>去 ChangeSet</Link>
          <Link to={`/projects/${projectId}/published`}>去发布/摘要</Link>
          <Link to={`/projects/${projectId}/workflows`}>去运行中心</Link>
        </div>
      </div>
    </div>
  );
}
