import { FormEvent, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { useAsync } from '../features/useAsync';
import { ActionFailure, ActionSuccess, EmptyState, ErrorState, LoadingState } from '../components/Status';
import { useProject } from '../context/ProjectContext';

export function ProjectsPage() {
  const navigate = useNavigate();
  const { setProjectId } = useProject();
  const projects = useAsync<Awaited<ReturnType<typeof api.listProjects>>>();
  const [projectName, setProjectName] = useState('');
  const [premise, setPremise] = useState('');
  const [feedback, setFeedback] = useState('');
  const [feedbackErr, setFeedbackErr] = useState('');

  useEffect(() => { void projects.run(() => api.listProjects()); }, []);

  const onCreate = async (e: FormEvent) => {
    e.preventDefault();
    setFeedback('');
    setFeedbackErr('');
    try {
      const created = await api.createProject({ project_name: projectName, premise });
      setFeedback(`项目 ${created.project_name} 创建成功`);
      setProjectName(''); setPremise('');
      await projects.run(() => api.listProjects());
    } catch (err) { setFeedbackErr(err instanceof Error ? err.message : '创建失败'); }
  };

  return (
    <div>
      <h1>项目列表 / 新建项目</h1>
      <form onSubmit={onCreate} className="panel">
        <input placeholder="项目名" value={projectName} onChange={(e) => setProjectName(e.target.value)} required />
        <textarea placeholder="项目 premise" value={premise} onChange={(e) => setPremise(e.target.value)} required />
        <button type="submit">新建项目</button>
      </form>
      {feedback && <ActionSuccess text={feedback} />}
      {feedbackErr && <ActionFailure text={feedbackErr} />}

      {projects.loading && <LoadingState />}
      {projects.error && <ErrorState text={projects.error} />}
      {!projects.loading && !projects.error && projects.data?.length === 0 && <EmptyState text="还没有项目，先创建一个。" />}
      <ul>
        {projects.data?.map((p) => (
          <li key={p.id} className="panel">
            <strong>{p.project_name}</strong>（chapter_no={p.current_chapter_no}）
            <p>{p.premise}</p>
            <button onClick={() => { setProjectId(p.id); navigate(`/projects/${p.id}/genres`); }}>进入项目</button>
            <Link to={`/projects/${p.id}/workbench`}>直达工作台</Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
