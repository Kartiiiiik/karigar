import { Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import SubscriptionGate from "./components/SubscriptionGate";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Karigars from "./pages/Karigars";
import Ornaments from "./pages/Ornaments";
import Gold from "./pages/Gold";
import Cash from "./pages/Cash";
import Managers from "./pages/Managers";
import Settings from "./pages/Settings";
import Reports from "./pages/Reports";
import Backups from "./pages/Backups";
import Bandaki from "./pages/Bandaki";
import NotFound from "./pages/NotFound";

const STAFF = ["owner", "manager"];

function Staff({ children }) {
  return <ProtectedRoute roles={STAFF}>{children}</ProtectedRoute>;
}

export default function App() {
  return (
    <SubscriptionGate>
      <Routes>
        <Route path="/login" element={<Login />} />

      <Route
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="karigars" element={<Staff><Karigars /></Staff>} />
        <Route path="ornaments" element={<Staff><Ornaments /></Staff>} />
        <Route path="gold" element={<Gold />} />
        <Route path="cash" element={<Cash />} />
        <Route path="reports" element={<Staff><Reports /></Staff>} />
        <Route path="managers" element={<ProtectedRoute roles={["owner"]}><Managers /></ProtectedRoute>} />
        <Route path="bandaki" element={<ProtectedRoute roles={["owner"]}><Bandaki /></ProtectedRoute>} />
        <Route path="settings" element={<Staff><Settings /></Staff>} />
        <Route path="backups" element={<Staff><Backups /></Staff>} />
      </Route>

      <Route path="*" element={<NotFound />} />
      </Routes>
    </SubscriptionGate>
  );
}
