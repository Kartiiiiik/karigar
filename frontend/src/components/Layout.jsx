import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  Users,
  Gem,
  Coins,
  ShoppingBag,
  FileBarChart,
  UserCog,
  Settings,
  DatabaseBackup,
  Landmark,
  LogOut,
  Menu,
  X,
} from "lucide-react";
import { useAuthStore } from "../store/auth";
import { useSettingsStore } from "../store/settings";

// role -> which nav items are visible. Karigars get a stripped-down self view.
const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, roles: ["owner", "manager", "karigar"], end: true },
  { to: "/karigars", label: "Karigars", icon: Users, roles: ["owner", "manager"] },
  { to: "/ornaments", label: "Ornaments", icon: ShoppingBag, roles: ["owner", "manager"] },
  { to: "/gold", label: "Gold Ledger", icon: Gem, roles: ["owner", "manager", "karigar"] },
  { to: "/cash", label: "Cash Ledger", icon: Coins, roles: ["owner", "manager", "karigar"] },
  { to: "/reports", label: "Reports", icon: FileBarChart, roles: ["owner", "manager"] },
  { to: "/managers", label: "Managers", icon: UserCog, roles: ["owner"] },
  { to: "/bandaki", label: "Bandaki", icon: Landmark, roles: ["owner"] },
  { to: "/settings", label: "Settings", icon: Settings, roles: ["owner", "manager"] },
  { to: "/backups", label: "Backups", icon: DatabaseBackup, roles: ["owner", "manager"] },
];

function NavItems({ role, onNavigate }) {
  return (
    <nav className="flex flex-col gap-1">
      {NAV.filter((item) => item.roles.includes(role)).map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          onClick={onNavigate}
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
              isActive
                ? "bg-brand-50 text-brand-700"
                : "text-gray-600 hover:bg-gray-100"
            }`
          }
        >
          <item.icon size={18} />
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}

export default function Layout() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();
  const loadSettings = useSettingsStore((s) => s.load);
  const role = user?.role ?? "karigar";

  // Load the shop's calendar preference once when the app shell mounts.
  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  const doLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    // Exactly one viewport tall; the shell never scrolls — only <main> (and
    // inner tables) scroll. Uses dvh so mobile browser chrome is respected.
    <div className="flex h-[100dvh] flex-col overflow-hidden lg:flex-row">
      {/* Mobile top bar */}
      <header className="flex shrink-0 items-center justify-between border-b border-gray-200 bg-white px-4 py-3 lg:hidden">
        <button onClick={() => setOpen(true)} aria-label="Open menu">
          <Menu size={22} />
        </button>
        <span className="flex items-center gap-2 font-semibold text-brand-700">
          <Gem size={18} /> Karigar
        </span>
        <button onClick={doLogout} aria-label="Log out">
          <LogOut size={20} className="text-gray-500" />
        </button>
      </header>

      {/* Sidebar (desktop) / drawer (mobile) — a full-height flex column so the
          footer logout sits at the bottom without overflowing the viewport. */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-gray-200 bg-white p-4 transition-transform lg:static lg:translate-x-0 lg:shrink-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="mb-6 flex shrink-0 items-center justify-between">
          <span className="flex items-center gap-2 text-lg font-bold text-brand-700">
            <Gem size={22} /> Karigar
          </span>
          <button className="lg:hidden" onClick={() => setOpen(false)} aria-label="Close menu">
            <X size={22} />
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          <NavItems role={role} onNavigate={() => setOpen(false)} />
        </div>

        <div className="mt-4 shrink-0 border-t border-gray-100 pt-4">
          <div className="mb-2 rounded-lg bg-gray-50 px-3 py-2 text-sm">
            <p className="font-medium text-gray-800">{user?.full_name || user?.username}</p>
            <p className="text-xs capitalize text-gray-500">{role}</p>
          </div>
          <button onClick={doLogout} className="btn-secondary w-full">
            <LogOut size={16} /> Log out
          </button>
        </div>
      </aside>

      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/30 lg:hidden"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Main content: the only vertically-scrolling region for tall pages. */}
      <main className="min-h-0 min-w-0 flex-1 overflow-y-auto p-4 lg:p-8">
        <Outlet />
      </main>
    </div>
  );
}
