import { Navigate, Route, Routes } from 'react-router-dom';
import { ProjectLayout } from '../components/ProjectLayout';
import { CanonPage } from '../pages/CanonPage';
import { ChangesetsPage } from '../pages/ChangesetsPage';
import { GatesPage } from '../pages/GatesPage';
import { GenresPage } from '../pages/GenresPage';
import { ObjectsPage } from '../pages/ObjectsPage';
import { OverviewPage } from '../pages/OverviewPage';
import { ProjectsPage } from '../pages/ProjectsPage';
import { PublishedPage } from '../pages/PublishedPage';
import { WorkbenchPage } from '../pages/WorkbenchPage';
import { WorkflowsPage } from '../pages/WorkflowsPage';

export function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/projects" replace />} />
      <Route path="/projects" element={<ProjectsPage />} />
      <Route path="/projects/:projectId" element={<ProjectLayout />}>
        <Route path="overview" element={<OverviewPage />} />
        <Route path="genres" element={<GenresPage />} />
        <Route path="canon" element={<CanonPage />} />
        <Route path="objects" element={<ObjectsPage />} />
        <Route path="workbench" element={<WorkbenchPage />} />
        <Route path="gates" element={<GatesPage />} />
        <Route path="changesets" element={<ChangesetsPage />} />
        <Route path="published" element={<PublishedPage />} />
        <Route path="workflows" element={<WorkflowsPage />} />
      </Route>
    </Routes>
  );
}
