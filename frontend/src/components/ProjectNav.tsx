import { Link, useParams } from 'react-router-dom';

const tabs = [
  ['overview', '项目概览'],
  ['workflows', '运行记录'],
  ['genres', '题材装载'],
  ['canon', '正式设定快照'],
  ['objects', '对象库'],
  ['character-cards', '角色卡（基础）'],
  ['terminology-cards', '术语卡（基础）'],
  ['faction-cards', '势力卡（基础）'],
  ['location-cards', '地点卡（基础）'],
  ['workbench', '创作工作台'],
  ['gates', '质量检查'],
  ['changesets', '变更提案'],
  ['published', '发布章节'],
];

export function ProjectNav() {
  const { projectId } = useParams();
  if (!projectId) return null;
  return (
    <nav className="project-nav">
      <Link to="/projects">返回项目列表</Link>
      <span>主路径：</span>
      {tabs.map(([path, label]) => (
        <Link key={path} to={`/projects/${projectId}/${path}`}>{label}</Link>
      ))}
    </nav>
  );
}
