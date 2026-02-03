import { Routes, Route } from 'react-router-dom';
import App from './App.jsx';
import { LoginPage } from './pages/LoginPage';
import { RequireAuth } from './auth/RequireAuth';
import { RequireAdmin } from './auth/RequireAdmin';
import { PlansPage } from './pages/PlansPage.jsx';
import { AdminPage } from './pages/AdminPage.jsx';

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/plans"
        element={
          <RequireAuth>
            <PlansPage />
          </RequireAuth>
        }
      />
      <Route
        path="/admin"
        element={
          <RequireAdmin>
            <AdminPage />
          </RequireAdmin>
        }
      />
      <Route
        path="/*"
        element={
          <RequireAuth>
            <App />
          </RequireAuth>
        }
      />
    </Routes>
  );
}
