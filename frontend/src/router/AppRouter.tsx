import { Navigate, Route, Routes } from 'react-router-dom';
import { ProjectLayout } from '../components/ProjectLayout';
import { CanonPage } from '../pages/CanonPage';
import { ChangesetsPage } from '../pages/ChangesetsPage';
import { BlueprintEditorPage } from '../pages/BlueprintEditorPage';
import { DraftEditorPage } from '../pages/DraftEditorPage';
import { SceneEditorPage } from '../pages/SceneEditorPage';
import { GatesPage } from '../pages/GatesPage';
import { GenresPage } from '../pages/GenresPage';
import { ObjectsPage } from '../pages/ObjectsPage';
import { OverviewPage } from '../pages/OverviewPage';
import { ProjectsPage } from '../pages/ProjectsPage';
import { PublishedPage } from '../pages/PublishedPage';
import { PublishHistoryPage } from '../pages/PublishHistoryPage';
import { ReleaseReadinessPage } from '../pages/ReleaseReadinessPage';
import { WorkbenchPage } from '../pages/WorkbenchPage';
import { WorkflowsPage } from '../pages/WorkflowsPage';

export function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/projects" replace />} />
      <Route path="/projects" element={<ProjectsPage />} />
      <Route path="/projects/:projectId" element={<ProjectLayout />}>
        <Route index element={<Navigate to="overview" replace />} />
        <Route path="overview" element={<OverviewPage />} />
        <Route path="genres" element={<GenresPage />} />
        <Route path="canon" element={<CanonPage />} />
        <Route path="objects" element={<ObjectsPage />} />
        <Route path="workbench" element={<WorkbenchPage />} />
        <Route path="blueprints/:blueprintId/edit" element={<BlueprintEditorPage />} />
        <Route path="scenes/:sceneId/edit" element={<SceneEditorPage />} />
        <Route path="drafts/:draftId/edit" element={<DraftEditorPage />} />
        <Route path="gates" element={<GatesPage />} />
        <Route path="changesets" element={<ChangesetsPage />} />
        <Route path="published" element={<PublishedPage />} />
        <Route path="chapters/:chapterNo/release-readiness" element={<ReleaseReadinessPage />} />
        <Route path="chapters/:chapterNo/publish-history" element={<PublishHistoryPage />} />
        <Route path="workflows" element={<WorkflowsPage />} />
      </Route>
    </Routes>
  );
}
