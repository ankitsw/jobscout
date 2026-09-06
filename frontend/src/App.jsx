import { Routes, Route } from 'react-router-dom';
import AuthGate from './components/AuthGate.jsx';
import DashboardPage from './pages/DashboardPage.jsx';
import JobsTablePage from './pages/JobsTablePage.jsx';

export default function App() {
  return (
    <AuthGate>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/jobs-all" element={<JobsTablePage />} />
      </Routes>
    </AuthGate>
  );
}
