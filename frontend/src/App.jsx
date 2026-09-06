import { Routes, Route } from 'react-router-dom';
import DashboardPage from './pages/DashboardPage.jsx';
import JobsTablePage from './pages/JobsTablePage.jsx';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<DashboardPage />} />
      <Route path="/jobs-all" element={<JobsTablePage />} />
    </Routes>
  );
}
