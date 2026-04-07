import { Link, useParams } from 'react-router-dom';

const tabs = [
  ['genres', '题材装载'],
  ['canon', 'Canon 快照'],
  ['objects', '对象库'],
  ['workbench', '章节工作台'],
  ['gates', 'Gate 结果'],
  ['changesets', 'ChangeSet 审批'],
  ['published', '发布与摘要'],
];

export function ProjectNav() {
  const { projectId } = useParams();
  if (!projectId) return null;
  return (
    <nav className="project-nav">
      {tabs.map(([path, label]) => (
        <Link key={path} to={`/projects/${projectId}/${path}`}>{label}</Link>
      ))}
    </nav>
  );
}
