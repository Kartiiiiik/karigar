import { Construction } from "lucide-react";

// Temporary page for routes whose feature ships in a later milestone.
export default function Placeholder({ title, milestone }) {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
      <div className="card flex items-center gap-3 text-gray-600">
        <Construction size={20} className="text-brand-600" />
        <span className="text-sm">
          This section arrives in {milestone}.
        </span>
      </div>
    </div>
  );
}
