import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ActionFailure, ActionSuccess, BlockedState } from '../components/Status';

export function GatesPage() {
  const { projectId = '' } = useParams();
  const [draftId, setDraftId] = useState('');
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');

  const run = async () => {
    setFeedback(''); setError('');
    try {
      const data = await api.runGateReview({ project_id: projectId, draft_id: draftId, gate_names: ['schema', 'canon', 'narrative', 'style'] });
      setResult(data as Record<string, unknown>);
      setFeedback('Gate 审查完成');
    } catch (e) { setError(e instanceof Error ? e.message : 'Gate失败'); }
  };

  if (!projectId) return <BlockedState text="缺少项目上下文" />;

  return <div><h2>Gate 结果页</h2>
    <div className="panel"><input placeholder="draft_id" value={draftId} onChange={(e)=>setDraftId(e.target.value)} /><button onClick={run}>执行 Gate 审查</button></div>
    {feedback && <ActionSuccess text={feedback} />} {error && <ActionFailure text={error} />}
    <p><Link to={`/projects/${projectId}/workbench`}>返回工作台修订</Link></p>
    <pre className="panel">{JSON.stringify(result, null, 2)}</pre>
  </div>;
}
