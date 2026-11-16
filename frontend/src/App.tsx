import { BrowserRouter, Link, Route, Routes } from "react-router";
import { AuthProvider } from "./auth/AuthContext";
import { HomeRedirect, RequireAuth } from "./auth/guards";
import { Layout } from "./components/Layout";
import { ToastProvider } from "./components/Toasts";
import { EmptyState } from "./components/ui";
import { AuditLogPage } from "./pages/admin/AuditLog";
import { ConfigurationPage } from "./pages/admin/Configuration";
import { AdminDashboardPage } from "./pages/admin/Dashboard";
import { SlaReportPage } from "./pages/admin/SlaReport";
import { UsersPage } from "./pages/admin/Users";
import { MyIncidentsPage } from "./pages/employee/MyIncidents";
import { ReportIncidentPage } from "./pages/employee/ReportIncident";
import { IncidentDetailPage } from "./pages/shared/IncidentDetail";
import { IncidentSearchPage } from "./pages/shared/IncidentSearch";
import { LoginPage } from "./pages/shared/Login";
import { NotificationsPage } from "./pages/shared/Notifications";
import { RegisterPage } from "./pages/shared/Register";
import { ServiceHealthPage } from "./pages/shared/ServiceHealth";
import { WorkloadPage } from "./pages/shared/Workload";
import { TechnicianQueuePage } from "./pages/technician/Queue";

function NotFound() {
  return (
    <EmptyState title="Page not found">
      <Link className="link" to="/">Go to your home page</Link>
    </EmptyState>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/" element={<HomeRedirect />} />

            <Route element={<RequireAuth><Layout /></RequireAuth>}>
              {/* shared by every role (the API scopes the data) */}
              <Route path="/incidents" element={<IncidentSearchPage />} />
              <Route path="/incidents/:id" element={<IncidentDetailPage />} />
              <Route path="/notifications" element={<NotificationsPage />} />

              <Route path="/employee" element={<RequireAuth roles={["EMPLOYEE"]}><MyIncidentsPage /></RequireAuth>} />
              <Route path="/employee/report" element={<RequireAuth roles={["EMPLOYEE"]}><ReportIncidentPage /></RequireAuth>} />

              <Route path="/tech" element={<RequireAuth roles={["TECHNICIAN"]}><TechnicianQueuePage /></RequireAuth>} />
              <Route path="/tech/workload" element={<RequireAuth roles={["TECHNICIAN"]}><WorkloadPage /></RequireAuth>} />
              <Route path="/tech/services" element={<RequireAuth roles={["TECHNICIAN"]}><ServiceHealthPage /></RequireAuth>} />

              <Route path="/admin" element={<RequireAuth roles={["ADMINISTRATOR"]}><AdminDashboardPage /></RequireAuth>} />
              <Route path="/admin/sla" element={<RequireAuth roles={["ADMINISTRATOR"]}><SlaReportPage /></RequireAuth>} />
              <Route path="/admin/workload" element={<RequireAuth roles={["ADMINISTRATOR"]}><WorkloadPage /></RequireAuth>} />
              <Route path="/admin/services" element={<RequireAuth roles={["ADMINISTRATOR"]}><ServiceHealthPage /></RequireAuth>} />
              <Route path="/admin/users" element={<RequireAuth roles={["ADMINISTRATOR"]}><UsersPage /></RequireAuth>} />
              <Route path="/admin/config" element={<RequireAuth roles={["ADMINISTRATOR"]}><ConfigurationPage /></RequireAuth>} />
              <Route path="/admin/audit" element={<RequireAuth roles={["ADMINISTRATOR"]}><AuditLogPage /></RequireAuth>} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
