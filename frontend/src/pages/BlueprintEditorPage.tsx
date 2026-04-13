import { FormEvent, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api } from '../api/client';
import { ActionFailure, ActionSuccess, BlockedState } from '../components/Status';

function toTextareaValue(value: unknown): string {
  if (!Array.isArray(value)) return '';
  return value.map((item) => String(item || '').trim()).filter((item) => item.length > 0).join('\n');
}

function parseLines(value: string): string[] {
  return value
    .split('\n')
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

export function BlueprintEditorPage() {
  const { projectId = '', blueprintId = '' } = useParams();
  const navigate = useNavigate();
  const [titleHint, setTitleHint] = useState('');
  const [summary, setSummary] = useState('');
  const [advancesText, setAdvancesText] = useState('');
  const [risksText, setRisksText] = useState('');
  const [editReason, setEditReason] = useState('');
  const [feedback, setFeedback] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!projectId || !blueprintId) return;
    setIsLoading(true);
    setError('');
    void api
      .getBlueprint(projectId, blueprintId)
      .then((bp) => {
        setTitleHint(String(bp.title_hint || ''));
        setSummary(String(bp.summary || ''));
        setAdvancesText(toTextareaValue(bp.advances));
        setRisksText(toTextareaValue(bp.risks));
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : '读取蓝图失败');
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [blueprintId, projectId]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (isSaving) return;
    if (!titleHint.trim() || !summary.trim() || !editReason.trim()) {
      setError('标题提示、摘要、edit_reason 均不能为空');
      return;
    }
    setIsSaving(true);
    setFeedback('');
    setError('');
    void api
      .manualEditBlueprint(blueprintId, {
        project_id: projectId,
        title_hint: titleHint.trim(),
        summary: summary.trim(),
        advances: parseLines(advancesText),
        risks: parseLines(risksText),
        edit_reason: editReason.trim(),
        edited_by: 'frontend_user',
      })
      .then(() => {
        setFeedback('蓝图人工修订已保存。请回到工作台重新执行“场景拆解 / 生成草稿”以应用最新蓝图。');
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : '保存蓝图失败');
      })
      .finally(() => {
        setIsSaving(false);
      });
  };

  if (!projectId || !blueprintId) return <BlockedState text="缺少项目或蓝图上下文" />;

  return (
    <div>
      <h2>Blueprint 人工修订</h2>
      <div className="panel">
        本页只编辑 ChapterBlueprint 的核心字段。保存后不会直写 Canon；请回工作台继续场景拆解与草稿生成。
      </div>
      {isLoading && <ActionSuccess text="正在加载蓝图..." />}
      {feedback && <ActionSuccess text={feedback} />}
      {error && <ActionFailure text={error} />}
      <form className="panel" onSubmit={submit}>
        <label>
          标题提示（title_hint）
          <input value={titleHint} onChange={(e) => setTitleHint(e.target.value)} />
        </label>
        <label>
          蓝图摘要（summary）
          <textarea rows={6} value={summary} onChange={(e) => setSummary(e.target.value)} />
        </label>
        <label>
          推进要点（advances，一行一条）
          <textarea rows={5} value={advancesText} onChange={(e) => setAdvancesText(e.target.value)} />
        </label>
        <label>
          风险清单（risks，一行一条）
          <textarea rows={5} value={risksText} onChange={(e) => setRisksText(e.target.value)} />
        </label>
        <label>
          编辑原因（edit_reason）
          <textarea rows={3} value={editReason} onChange={(e) => setEditReason(e.target.value)} />
        </label>
        <button type="submit" disabled={isSaving || isLoading}>{isSaving ? '保存中...' : '保存蓝图人工修订'}</button>
      </form>
      <div className="project-nav">
        <button type="button" onClick={() => navigate(`/projects/${projectId}/workbench`)}>回工作台继续主链</button>
        <Link to={`/projects/${projectId}/workbench`}>去场景拆解 / 生成草稿</Link>
        <Link to={`/projects/${projectId}/gates`}>去 Gate</Link>
        <Link to={`/projects/${projectId}/changesets`}>去 ChangeSet</Link>
        <Link to={`/projects/${projectId}/published`}>去 Publish</Link>
      </div>
    </div>
  );
}
