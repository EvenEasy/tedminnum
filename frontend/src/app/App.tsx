import { AuthProvider, useAuth } from "../features/auth/AuthProvider";
import { Login } from "../features/auth/Login";
import { ThemeProvider } from "../shared/ThemeProvider";
import { WorkspaceApp } from "./WorkspaceApp";
function AuthGate() {
  const { user, initial, epoch } = useAuth();
  if (initial) return <main className="loading">Opening your workspace…</main>;
  if (!user) return <Login />;
  return <WorkspaceApp key={`${user.id}:${epoch}`} />;
}
export function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <AuthGate />
      </AuthProvider>
    </ThemeProvider>
  );
}
