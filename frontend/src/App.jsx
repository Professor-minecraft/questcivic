import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Login from './pages/Login';
import ForgotPassword from './pages/ForgotPassword';
import LocationSetup from './pages/LocationSetup';
import Works from './pages/Works';
import Profile from './pages/Profile';
import AuditorLogin from './pages/AuditorLogin';
import AuditorDashboard from './pages/AuditorDashboard';
import Leaderboard from './pages/Leaderboard';
import AdminDashboard from './pages/AdminDashboard';
import AuditorSetPassword from './pages/AuditorSetPassword';

function RootRedirect() {
  const { token, role } = useAuth();
  if (!token) return <Navigate to="/login" replace />;
  if (role === 'admin') return <Navigate to="/admin" replace />;
  if (role === 'auditor') return <Navigate to="/auditor" replace />;
  return <Navigate to="/works" replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/" element={<RootRedirect />} />
          <Route path="/login" element={<Login />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/auditor/login" element={<AuditorLogin />} />
          <Route
            path="/location"
            element={
              <ProtectedRoute role="user">
                <LocationSetup />
              </ProtectedRoute>
            }
          />
          <Route
            path="/works"
            element={
              <ProtectedRoute role="user">
                <Works />
              </ProtectedRoute>
            }
          />
          <Route
            path="/profile"
            element={
              <ProtectedRoute role="user">
                <Profile />
              </ProtectedRoute>
            }
          />
          <Route
            path="/leaderboard"
            element={
              <ProtectedRoute role="user">
                <Leaderboard />
              </ProtectedRoute>
            }
          />
          <Route path="/auditor/set-password" element={<AuditorSetPassword />} />
          <Route
            path="/auditor"
            element={
              <ProtectedRoute role="auditor">
                <AuditorDashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <ProtectedRoute role="admin">
                <AdminDashboard />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}
