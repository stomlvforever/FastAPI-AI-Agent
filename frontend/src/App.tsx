import { Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell.tsx";
import { RequireAuth } from "./components/RequireAuth.tsx";
import { ArticlePage } from "./pages/ArticlePage.tsx";
import { AuthPage } from "./pages/AuthPage.tsx";
import { AuthorPage } from "./pages/AuthorPage.tsx";
import { CopilotPage } from "./pages/CopilotPage.tsx";
import { EditorPage } from "./pages/EditorPage.tsx";
import { HomePage } from "./pages/HomePage.tsx";
import { NotFoundPage } from "./pages/NotFoundPage.tsx";
import { ProfilePage } from "./pages/ProfilePage.tsx";

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route element={<HomePage />} index />
        <Route element={<AuthPage />} path="/auth" />

        <Route element={<RequireAuth />}>
          <Route element={<ArticlePage />} path="/articles/:slug" />
          <Route element={<EditorPage />} path="/editor" />
          <Route element={<EditorPage />} path="/editor/:slug" />
          <Route element={<ProfilePage />} path="/profile" />
          <Route element={<AuthorPage />} path="/profiles/:userId" />
          <Route element={<CopilotPage />} path="/copilot" />
        </Route>

        <Route element={<NotFoundPage />} path="*" />
      </Route>
    </Routes>
  );
}

export default App;
