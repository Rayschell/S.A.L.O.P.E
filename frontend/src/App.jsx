import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext.jsx'
import { ThemeProvider } from './contexts/ThemeContext.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'
import Layout from './components/layout/Layout.jsx'
import LoginPage from './pages/LoginPage.jsx'
import MembersPage from './pages/MembersPage.jsx'
import EventsPage from './pages/EventsPage.jsx'
import EventDetailPage from './pages/EventDetailPage.jsx'
import HistoricalImportPage from './pages/HistoricalImportPage.jsx'
import PublicPollPage from './pages/PublicPollPage.jsx'
import Toaster from './components/ui/Toaster.jsx'
import ConfirmModal from './components/ui/ConfirmModal.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'

export default function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/dispo/:token" element={<PublicPollPage />} />
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <Layout />
                  </ProtectedRoute>
                }
              >
                <Route index element={<Navigate to="/events" replace />} />
                <Route path="events" element={<EventsPage />} />
                <Route path="events/:id" element={<EventDetailPage />} />
                <Route path="members" element={<MembersPage />} />
                <Route path="import-historique" element={<HistoricalImportPage />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </AuthProvider>
        <Toaster />
        <ConfirmModal />
      </ThemeProvider>
    </ErrorBoundary>
  )
}
