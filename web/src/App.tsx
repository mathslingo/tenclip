import { Navigate, Route, Routes } from "react-router-dom";
import { SiteLayout } from "./layouts/SiteLayout";
import { HomePage } from "./pages/Home";
import { MatchDetailPage } from "./pages/MatchDetail";
import { NewsDetailPage } from "./pages/NewsDetail";
import { PlayerDetailPage } from "./pages/PlayerDetail";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<SiteLayout />}>
        <Route index element={<HomePage />} />
        <Route path="news/:id" element={<NewsDetailPage />} />
        <Route path="matches/:id" element={<MatchDetailPage />} />
        <Route path="players/:id" element={<PlayerDetailPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
