import { Outlet, useParams } from 'react-router-dom';
import { ProjectNav } from './ProjectNav';
import { BlockedState } from './Status';

export function ProjectLayout() {
  const { projectId } = useParams();
  if (!projectId) return <BlockedState text="缺少 projectId，无法进入项目域页面" />;

  return (
    <div>
      <h1>项目工作台：{projectId}</h1>
      <ProjectNav />
      <Outlet />
    </div>
  );
}
