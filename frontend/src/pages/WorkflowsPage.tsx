import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ActionFailure, ActionSuccess, EmptyState, LoadingState } from '../components/Status';
import { mergeProjectChainState } from '../features/projectState';
import type { Dict } from '../types/api';

type WorkflowRunView = {
  runId: string;
  runType: string;
  status: string;
  currentStep: string;
  updatedAt: string;
  attentionRequired: boolean;
};

function parseRun(row: Dict): WorkflowRunView {
  return {
    runId: String(row.id || row.workflow_run_id || '-'),
    runType: String(row.run_type || row.workflow_type || '-'),
    status: String(row.status || row.run_status || '-'),
    currentStep: String(row.current_step || row.current_stage || row.current_node || '-'),
    updatedAt: String(row.updated_at || row.last_updated_at || '-'),
    attentionRequired: Boolean(row.attention_required),
  };
}

export function WorkflowsPage() {
  const { projectId = '' } = useParams();
  const [runs, setRuns] = useState<WorkflowRunView[]>([]);
  const [selectedRunId, setSelectedRunId] = useState('');
  const [selectedRunDetail, setSelectedRunDetail] = useState<Dict | null>(null);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');

  const blockedRuns = useMemo(() => runs.filter((item) => {
    const normalized = item.status.toLowerCase();
    return normalized.includes('blocked') || normalized.includes('failed') || normalized.includes('error');
  }), [runs]);

  const refresh = async () => {
    if (!projectId) return;
    setLoading(true);
    setFeedback('');
    setError('');
    try {
      const payload = await api.listWorkflowRuns(projectId);
      const nextRuns = payload.map((item) => parseRun(item));
      setRuns(nextRuns);
      if (nextRuns.length > 0 && !selectedRunId) {
        setSelectedRunId(nextRuns[0].runId);
      }
      mergeProjectChainState(projectId, {
        hasAttentionRun: nextRuns.some((item) => item.attentionRequired),
        hasBlockedRun: nextRuns.some((item) => {
          const status = item.status.toLowerCase();
          return status.includes('blocked') || status.includes('failed') || status.includes('error');
        }),
        latestWorkflowRunId: nextRuns[0]?.runId || '',
      });
      setFeedback('运行中心数据已刷新');
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载 workflow runs 失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, [projectId]);

  useEffect(() => {
    if (!selectedRunId || !projectId) {
      setSelectedRunDetail(null);
      return;
    }
    setDetailLoading(true);
    void api.getWorkflowRunDetail(selectedRunId)
      .then((payload) => {
        setSelectedRunDetail(payload);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : '加载 run 详情失败');
      })
      .finally(() => {
        setDetailLoading(false);
      });
  }, [projectId, selectedRunId]);

  return (
    <div>
      <h2>工作流运行中心</h2>
      <div className="panel">
        <button onClick={() => void refresh()} disabled={loading}>{loading ? '刷新中...' : '刷新状态'}</button>
      </div>
      {loading && <LoadingState text="run 列表加载中..." />}
      {detailLoading && <LoadingState text="run 详情加载中..." />}
      {feedback && <ActionSuccess text={feedback} />}
      {error && <ActionFailure text={error} />}

      <div className="panel">
        <h3>阻断 / attention 状态</h3>
        <div>attention required run：{runs.filter((item) => item.attentionRequired).length}</div>
        <div>阻断 run：{blockedRuns.length}</div>
      </div>

      <div className="grid">
        <div className="panel">
          <h3>项目 run 列表</h3>
          {runs.length === 0 ? (
            <EmptyState text="当前项目暂无 workflow run" />
          ) : (
            <ul>
              {runs.map((item) => (
                <li key={item.runId} className="panel">
                  <div>run_id：{item.runId}</div>
                  <div>类型：{item.runType}</div>
                  <div>状态：{item.status}</div>
                  <div>当前步骤：{item.currentStep}</div>
                  <div>更新时间：{item.updatedAt}</div>
                  <button onClick={() => setSelectedRunId(item.runId)}>查看详情</button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="panel">
          <h3>重点 run 详情</h3>
          {!selectedRunId ? <EmptyState text="请先选择 run" /> : <div>当前 run：{selectedRunId}</div>}
          <div className="panel">仅展示后端已公开接口能力：刷新 + 查看详情。暂停/恢复/人工接管可在后端开启时接入。</div>
          <pre>{JSON.stringify(selectedRunDetail, null, 2)}</pre>
        </div>
      </div>

      <div className="panel">
        <h3>继续处理</h3>
        <div className="project-nav">
          <Link to={`/projects/${projectId}/overview`}>回项目概览</Link>
          <Link to={`/projects/${projectId}/workbench`}>去工作台</Link>
          <Link to={`/projects/${projectId}/changesets`}>去 ChangeSet</Link>
          <Link to={`/projects/${projectId}/published`}>去发布/摘要</Link>
        </div>
      </div>
    </div>
  );
}
