import { Link } from "react-router-dom";
import {
  Gem, Coins, Phone, MapPin, UserPlus, HandCoins, Banknote,
} from "lucide-react";
import { useFetch } from "../hooks/useFetch";
import { useAuthStore } from "../store/auth";
import { DrCrBadge } from "../components/ui";
import { formatGoldBalance, formatCashBalance } from "../lib/format";

// Quick-access action tile. `tone` tints by money direction:
// amber = out/given (Dr), green = in/received (Cr), gray = neutral.
function QuickAction({ to, icon: Icon, label, tone = "gray" }) {
  const tones = {
    amber: "border-amber-200 bg-amber-50 text-amber-800 hover:bg-amber-100",
    green: "border-green-200 bg-green-50 text-green-800 hover:bg-green-100",
    gray: "border-gray-200 bg-white text-gray-700 hover:bg-gray-50",
  };
  return (
    <Link
      to={to}
      className={`flex flex-col items-center justify-center gap-2 rounded-xl border p-4 text-center text-sm font-semibold transition ${tones[tone]}`}
    >
      <Icon size={22} />
      {label}
    </Link>
  );
}

export default function Dashboard() {
  const user = useAuthStore((s) => s.user);
  const isKarigar = user?.role === "karigar";
  return isKarigar ? <KarigarHome user={user} /> : <StaffHome user={user} />;
}

// ---------------------------------------------------------------------------
// Karigar self-view (read-only, scoped to their own data)
// ---------------------------------------------------------------------------
function KarigarHome({ user }) {
  const { data: me } = useFetch("/me/karigar/");
  const { data: gold } = useFetch("/gold-entries/", { page_size: 5, ordering: "-entry_date" });
  const { data: cash } = useFetch("/cash-entries/", { page_size: 5, ordering: "-entry_date" });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Namaste, {user?.full_name || user?.username}</h1>
        <p className="text-sm text-gray-500">Your gold and cash balances with the shop.</p>
      </div>

      {me && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="card">
              <p className="mb-1 flex items-center gap-2 text-sm text-gray-500"><Gem size={16} /> Gold balance (net)</p>
              <DrCrBadge label={formatGoldBalance(me.gold_balance)} />
            </div>
            <div className="card">
              <p className="mb-1 flex items-center gap-2 text-sm text-gray-500"><Coins size={16} /> Cash balance</p>
              <DrCrBadge label={formatCashBalance(me.cash_balance)} />
            </div>
          </div>

          {(me.phone || me.location) && (
            <div className="card text-sm text-gray-600">
              {me.phone && <p className="flex items-center gap-2"><Phone size={14} /> {me.phone}</p>}
              {me.location && <p className="mt-1 flex items-center gap-2"><MapPin size={14} /> {me.location}</p>}
            </div>
          )}
        </>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <RecentList title="Recent gold" items={gold?.results} link="/gold" empty="No gold entries yet." />
        <RecentList title="Recent cash" items={cash?.results} link="/cash" empty="No cash entries yet." isCash />
      </div>
    </div>
  );
}

function RecentList({ title, items, link, empty, isCash }) {
  return (
    <div className="card">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="font-semibold text-gray-900">{title}</h2>
        <Link to={link} className="text-sm text-brand-600">View all</Link>
      </div>
      {!items || items.length === 0 ? (
        <p className="py-6 text-center text-sm text-gray-400">{empty}</p>
      ) : (
        <ul className="divide-y divide-gray-100 text-sm">
          {items.map((e) => (
            <li key={e.id} className="flex items-center justify-between py-2">
              <span className="text-gray-500">{e.entry_date}</span>
              <span className="capitalize">{e.direction === "dr" ? "Given" : "Received"}</span>
              <span className="font-medium">
                {isCash ? `NPR ${Number(e.amount_npr).toLocaleString()}` : `${Number(e.net_weight_g).toFixed(3)} g`}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Owner / Manager home
// ---------------------------------------------------------------------------
function StaffHome({ user }) {
  const isOwner = user?.role === "owner";
  const { data: karigarData } = useFetch("/karigars/", { page_size: 200 });
  const karigars = karigarData?.results ?? [];

  const totalGold = karigars.reduce((s, k) => s + Number(k.gold_balance || 0), 0);
  const totalCash = karigars.reduce((s, k) => s + Number(k.cash_balance || 0), 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Welcome, {user?.full_name || user?.username}</h1>
        <p className="text-sm capitalize text-gray-500">Signed in as {user?.role}</p>
      </div>

      {/* Quick actions */}
      <div>
        <h2 className="mb-2 text-sm font-medium text-gray-500">Quick actions</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <QuickAction to="/gold?action=out" icon={Gem} label="Gold Out" tone="amber" />
          <QuickAction to="/gold?action=in" icon={Gem} label="Gold In" tone="green" />
          <QuickAction to="/cash?action=out" icon={Banknote} label="Cash Out" tone="amber" />
          <QuickAction to="/cash?action=in" icon={Banknote} label="Cash In" tone="green" />
          <QuickAction to="/karigars?action=new" icon={UserPlus} label="Add Karigar" />
          {isOwner && <QuickAction to="/bandaki?action=new" icon={HandCoins} label="Add Bandaki" />}
        </div>
      </div>

      {/* Karigar balances */}
      <div className="card">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="font-semibold text-gray-900">Karigar balances</h2>
          <Link to="/karigars" className="text-sm text-brand-600">Manage</Link>
        </div>
        {karigars.length === 0 ? (
          <p className="py-6 text-center text-sm text-gray-400">No karigars yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="text-left text-xs uppercase text-gray-400">
                <tr><th className="py-2">Name</th><th className="py-2">Gold</th><th className="py-2">Cash</th></tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {karigars.map((k) => (
                  <tr key={k.id}>
                    <td className="py-2">{k.full_name}</td>
                    <td className="py-2"><DrCrBadge label={formatGoldBalance(k.gold_balance)} /></td>
                    <td className="py-2"><DrCrBadge label={formatCashBalance(k.cash_balance)} /></td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t-2 border-gray-200">
                <tr className="font-semibold text-gray-800">
                  <td className="py-2">Totals ({karigars.length})</td>
                  <td className="py-2"><DrCrBadge label={formatGoldBalance(totalGold)} /></td>
                  <td className="py-2"><DrCrBadge label={formatCashBalance(totalCash)} /></td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
