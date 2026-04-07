import { AppRouter } from '../router/AppRouter';
import { ProjectProvider } from '../context/ProjectContext';

export function App() {
  return (
    <ProjectProvider>
      <AppRouter />
    </ProjectProvider>
  );
}
