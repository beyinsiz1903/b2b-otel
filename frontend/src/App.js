import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import "@/App.css";

// ── Contexts ──────────────────────────────────────────────────────────────────
import { ThemeProvider } from "@/contexts/ThemeContext";
import { WSProvider } from "@/contexts/WSContext";
import { AuthProvider, ProtectedRoute } from "@/contexts/AuthContext";

// ── Components ────────────────────────────────────────────────────────────────
import ErrorBoundary from "@/components/ErrorBoundary";
import NotFoundPage from "@/components/NotFoundPage";

// ── Pages ─────────────────────────────────────────────────────────────────────
import LoginPage from "@/pages/LoginPage";
import RegisterPage from "@/pages/RegisterPage";
import DashboardPage from "@/pages/DashboardPage";
import ListingsPage from "@/pages/ListingsPage";
import ListingDetailPage from "@/pages/ListingDetailPage";
import AvailabilityPage from "@/pages/AvailabilityPage";
import RequestsPage from "@/pages/RequestsPage";
import MatchesPage from "@/pages/MatchesPage";
import MatchDetailPage from "@/pages/MatchDetailPage";
import ProfilePage from "@/pages/ProfilePage";
import ReportsPage from "@/pages/ReportsPage";
import AdminPage from "@/pages/AdminPage";
import InventoryPage from "@/pages/InventoryPage";
import PricingPage from "@/pages/PricingPage";
import PerformancePage from "@/pages/PerformancePage";
import PaymentsPage from "@/pages/PaymentsPage";
import InvoicesPage from "@/pages/InvoicesPage";
import SubscriptionPage from "@/pages/SubscriptionPage";
import NotificationsPage from "@/pages/NotificationsPage";

// ── App Router ────────────────────────────────────────────────────────────────
const App = () => (
  <ErrorBoundary>
    <ThemeProvider>
      <WSProvider>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
              <Route path="/listings" element={<ProtectedRoute><ListingsPage /></ProtectedRoute>} />
              <Route path="/listings/:id" element={<ProtectedRoute><ListingDetailPage /></ProtectedRoute>} />
              <Route path="/availability" element={<ProtectedRoute><AvailabilityPage /></ProtectedRoute>} />
              <Route path="/requests" element={<ProtectedRoute><RequestsPage /></ProtectedRoute>} />
              <Route path="/matches" element={<ProtectedRoute><MatchesPage /></ProtectedRoute>} />
              <Route path="/matches/:id" element={<ProtectedRoute><MatchDetailPage /></ProtectedRoute>} />
              <Route path="/profile" element={<ProtectedRoute><ProfilePage /></ProtectedRoute>} />
              <Route path="/reports" element={<ProtectedRoute><ReportsPage /></ProtectedRoute>} />
              <Route path="/admin" element={<ProtectedRoute><AdminPage /></ProtectedRoute>} />
              <Route path="/inventory" element={<ProtectedRoute><InventoryPage /></ProtectedRoute>} />
              <Route path="/pricing" element={<ProtectedRoute><PricingPage /></ProtectedRoute>} />
              <Route path="/performance" element={<ProtectedRoute><PerformancePage /></ProtectedRoute>} />
              <Route path="/payments" element={<ProtectedRoute><PaymentsPage /></ProtectedRoute>} />
              <Route path="/invoices" element={<ProtectedRoute><InvoicesPage /></ProtectedRoute>} />
              <Route path="/subscription" element={<ProtectedRoute><SubscriptionPage /></ProtectedRoute>} />
              <Route path="/notifications" element={<ProtectedRoute><NotificationsPage /></ProtectedRoute>} />
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </WSProvider>
    </ThemeProvider>
  </ErrorBoundary>
);

export default App;
