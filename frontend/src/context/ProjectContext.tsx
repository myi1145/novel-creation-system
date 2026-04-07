import { createContext, useContext, useMemo, useState } from 'react';

interface ProjectContextValue {
  projectId: string;
  setProjectId: (id: string) => void;
}

const ProjectContext = createContext<ProjectContextValue | undefined>(undefined);

export function ProjectProvider({ children }: { children: React.ReactNode }) {
  const [projectId, setProjectId] = useState<string>(localStorage.getItem('project_id') || '');

  const value = useMemo(
    () => ({
      projectId,
      setProjectId: (id: string) => {
        setProjectId(id);
        localStorage.setItem('project_id', id);
      },
    }),
    [projectId],
  );

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

export function useProject() {
  const context = useContext(ProjectContext);
  if (!context) {
    throw new Error('ProjectContext 未挂载');
  }
  return context;
}
