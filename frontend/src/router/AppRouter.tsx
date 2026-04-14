import { Navigate, Route, Routes } from 'react-router-dom';
import { ProjectLayout } from '../components/ProjectLayout';
import { CanonPage } from '../pages/CanonPage';
import { ChangesetsPage } from '../pages/ChangesetsPage';
import { CharacterCardsPage } from '../pages/CharacterCardsPage';
import { BlueprintEditorPage } from '../pages/BlueprintEditorPage';
import { DraftEditorPage } from '../pages/DraftEditorPage';
import { SceneEditorPage } from '../pages/SceneEditorPage';
import { GatesPage } from '../pages/GatesPage';
import { GenresPage } from '../pages/GenresPage';
import { FactionCardsPage } from '../pages/FactionCardsPage';
import { LocationCardsPage } from '../pages/LocationCardsPage';
import { ObjectsPage } from '../pages/ObjectsPage';
import { OverviewPage } from '../pages/OverviewPage';
import { ProjectsPage } from '../pages/ProjectsPage';
import { PublishedPage } from '../pages/PublishedPage';
import { PublishedChapterReaderPage } from '../pages/PublishedChapterReaderPage';
import { PublishHistoryPage } from '../pages/PublishHistoryPage';
import { ReleaseReadinessPage } from '../pages/ReleaseReadinessPage';
import { StoryPlanningPage } from '../pages/StoryPlanningPage';
import { VersionDiffPage } from '../pages/VersionDiffPage';
import { TerminologyCardsPage } from '../pages/TerminologyCardsPage';
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
        <Route path="story-planning" element={<StoryPlanningPage />} />
        <Route path="genres" element={<GenresPage />} />
        <Route path="canon" element={<CanonPage />} />
        <Route path="objects" element={<ObjectsPage />} />
        <Route path="character-cards" element={<CharacterCardsPage />} />
        <Route path="terminology-cards" element={<TerminologyCardsPage />} />
        <Route path="faction-cards" element={<FactionCardsPage />} />
        <Route path="location-cards" element={<LocationCardsPage />} />
        <Route path="workbench" element={<WorkbenchPage />} />
        <Route path="blueprints/:blueprintId/edit" element={<BlueprintEditorPage />} />
        <Route path="scenes/:sceneId/edit" element={<SceneEditorPage />} />
        <Route path="drafts/:draftId/edit" element={<DraftEditorPage />} />
        <Route path="gates" element={<GatesPage />} />
        <Route path="changesets" element={<ChangesetsPage />} />
        <Route path="published" element={<PublishedPage />} />
        <Route path="chapters/:chapterNo/release-readiness" element={<ReleaseReadinessPage />} />
        <Route path="chapters/:chapterNo/publish-history" element={<PublishHistoryPage />} />
        <Route path="chapters/:chapterNo/version-diff" element={<VersionDiffPage />} />
        <Route path="chapters/:chapterNo/published-reader" element={<PublishedChapterReaderPage />} />
        <Route path="workflows" element={<WorkflowsPage />} />
      </Route>
    </Routes>
  );
}
