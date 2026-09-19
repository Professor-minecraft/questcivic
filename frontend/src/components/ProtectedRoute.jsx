import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function ProtectedRoute({ role, children }) {
  const { token, role: userRole } = useAuth();

  if (!token || userRole !== role) {
    if (role === 'auditor' || role === 'admin') {
      return <Navigate to="/auditor/login" replace />;
    }
    return <Navigate to="/login" replace />;
  }

  return children;
}
