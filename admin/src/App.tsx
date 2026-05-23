import { Navigate, Route, Routes } from "react-router-dom";
import { AdminLayout } from "./layouts/AdminLayout";
import { MatchForm } from "./pages/matches/MatchForm";
import { MatchList } from "./pages/matches/MatchList";
import { NewsForm } from "./pages/news/NewsForm";
import { NewsList } from "./pages/news/NewsList";
import { PlayerForm } from "./pages/players/PlayerForm";
import { PlayerList } from "./pages/players/PlayerList";
import { VideoForm } from "./pages/videos/VideoForm";
import { VideoList } from "./pages/videos/VideoList";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<AdminLayout />}>
        <Route index element={<Navigate to="/news" replace />} />
        <Route path="news" element={<NewsList />} />
        <Route path="news/new" element={<NewsForm />} />
        <Route path="news/:id" element={<NewsForm />} />
        <Route path="players" element={<PlayerList />} />
        <Route path="players/new" element={<PlayerForm />} />
        <Route path="players/:id" element={<PlayerForm />} />
        <Route path="matches" element={<MatchList />} />
        <Route path="matches/new" element={<MatchForm />} />
        <Route path="matches/:id" element={<MatchForm />} />
        <Route path="videos" element={<VideoList />} />
        <Route path="videos/new" element={<VideoForm />} />
        <Route path="videos/:id" element={<VideoForm />} />
      </Route>
      <Route path="*" element={<Navigate to="/news" replace />} />
    </Routes>
  );
}
