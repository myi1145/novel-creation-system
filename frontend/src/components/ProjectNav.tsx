import { Link, useParams } from 'react-router-dom';

const tabs = [
  ['overview', '项目概览'],
  ['workflows', '运行中心'],
  ['genres', '题材装载'],
  ['canon', 'Canon 快照'],
  ['objects', '对象库'],
  ['workbench', '创作工作台'],
  ['gates', '质量检查结果图表'],
  ['changesets', '变更提案'],
  ['published', '发布章节'],
];

export function ProjectNav() {
  const { projectId } = useParams();
  if (!projectId) return null;
  return (
    <nav className="project-nav">
      <Link to="/projects">返回项目列表</Link>
      {tabs.map(([path, label]) => (
        <Link key={path} to={`/projects/${projectId}/${path}`}>{label}</Link>
      ))}
    </nav>
  );
}
