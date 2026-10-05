import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from '../layouts/AppLayout.jsx'
import AuthLayout from '../layouts/AuthLayout.jsx'
import ProtectedRoute from './ProtectedRoute.jsx'

import Login from '../pages/Login.jsx'
import Signup from '../pages/Signup.jsx'
import Dashboard from '../pages/Dashboard.jsx'
import Upload from '../pages/Upload.jsx'
import Profile from '../pages/Profile.jsx'
import ColumnAnalysis from '../pages/ColumnAnalysis.jsx'
import Preprocessing from '../pages/Preprocessing.jsx'
import Generation from '../pages/Generation.jsx'
import Evaluation from '../pages/Evaluation.jsx'
import EvaluationDashboard from '../pages/EvaluationDashboard.jsx'
import Report from '../pages/Report.jsx'
import Relationships from '../pages/Relationships.jsx'
import NotFound from '../pages/NotFound.jsx'
import OtpVerify from '../pages/OtpVerify.jsx'
import MyDatasets from '../pages/MyDatasets.jsx'
import Settings from '../pages/Settings.jsx'

function Protect({ children }) {
  return <ProtectedRoute>{children}</ProtectedRoute>
}

export default function AppRouter() {
  return (
    <Routes>
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/verify-otp" element={<OtpVerify />} />
      </Route>

      <Route
        element={
          <Protect>
            <AppLayout />
          </Protect>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/datasets" element={<MyDatasets />} />

        <Route path="/datasets/:datasetId/profile" element={<Profile />} />
        <Route path="/datasets/:datasetId/columns" element={<ColumnAnalysis />} />
        <Route path="/datasets/:datasetId/preprocess" element={<Preprocessing />} />
        <Route path="/datasets/:datasetId/generate" element={<Generation />} />
        <Route path="/datasets/:datasetId/evaluate" element={<Evaluation />} />

        <Route path="/evaluations" element={<EvaluationDashboard />} />
        <Route path="/reports" element={<Report />} />
        <Route path="/relationships" element={<Relationships />} />
        <Route path="/settings" element={<Settings />} />

      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}