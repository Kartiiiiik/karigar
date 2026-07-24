import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  Calendar,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";
import {
  BS_MONTHS,
  adToBsParts,
  bsMonthStartWeekday,
  bsToApi,
  daysInBsMonth,
  formatDate,
} from "../lib/date";

const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];
const POPUP_W = 256; // matches w-64
const POPUP_H = 340; // approximate; used only for edge-flip decisions
const GAP = 4;
const MARGIN = 8;

/**
 * Calendar-aware date input. The value in/out is ALWAYS an AD `YYYY-MM-DD`
 * string (the API contract). In AD mode we use the native date picker; in BS
 * mode we render a full Bikram Sambat calendar popup (day grid, month/year
 * navigation) and convert the picked BS date to AD under the hood.
 */
export default function DateInput({ value, onChange, calendar = "AD", id, disabled = false }) {
  if (calendar !== "BS") {
    return (
      <input
        id={id}
        className="input"
        type="date"
        value={value || ""}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }
  return <BsCalendarInput value={value} onChange={onChange} id={id} disabled={disabled} />;
}

function BsCalendarInput({ value, onChange, id, disabled }) {
  const selected = adToBsParts(value); // { year, month (0-based), day } | null
  const today = adToBsParts(new Date());
  const [open, setOpen] = useState(false);
  const [view, setView] = useState(() => {
    const base = selected ?? today;
    return { year: base.year, month: base.month };
  });
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const triggerRef = useRef(null);
  const popupRef = useRef(null);

  // Position the popup relative to the trigger, in viewport (fixed) coords so
  // it escapes the modal's overflow clipping. Flip above / clamp to the screen
  // when it would run off an edge.
  const place = () => {
    const el = triggerRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    let left = r.left;
    if (left + POPUP_W > window.innerWidth - MARGIN) {
      left = window.innerWidth - POPUP_W - MARGIN;
    }
    if (left < MARGIN) left = MARGIN;
    let top = r.bottom + GAP;
    if (top + POPUP_H > window.innerHeight - MARGIN) {
      const above = r.top - POPUP_H - GAP;
      top = above >= MARGIN ? above : Math.max(MARGIN, window.innerHeight - POPUP_H - MARGIN);
    }
    setPos({ top, left });
  };

  // When the popup opens: jump to the selected month (or today) and place it.
  useLayoutEffect(() => {
    if (!open) return;
    const base = adToBsParts(value) ?? today;
    setView({ year: base.year, month: base.month });
    place();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Keep it anchored on scroll / resize, and dismiss on outside click or Escape.
  useEffect(() => {
    if (!open) return;
    const reposition = () => place();
    const onDown = (e) => {
      if (
        !triggerRef.current?.contains(e.target) &&
        !popupRef.current?.contains(e.target)
      ) {
        setOpen(false);
      }
    };
    const onKey = (e) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("scroll", reposition, true); // capture: catch scroll on any ancestor
    window.addEventListener("resize", reposition);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("scroll", reposition, true);
      window.removeEventListener("resize", reposition);
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const shiftMonth = (delta) =>
    setView((v) => {
      let m = v.month + delta;
      let y = v.year;
      if (m < 0) {
        m = 11;
        y -= 1;
      } else if (m > 11) {
        m = 0;
        y += 1;
      }
      return { year: y, month: m };
    });
  const shiftYear = (delta) => setView((v) => ({ ...v, year: v.year + delta }));

  const pick = (day) => {
    onChange(bsToApi(view.year, view.month, day));
    setOpen(false);
  };

  const days = daysInBsMonth(view.year, view.month);
  const lead = bsMonthStartWeekday(view.year, view.month);
  const cells = [
    ...Array(lead).fill(null),
    ...Array.from({ length: days }, (_, i) => i + 1),
  ];

  const sameCell = (parts, d) =>
    parts &&
    parts.year === view.year &&
    parts.month === view.month &&
    parts.day === d;

  return (
    <>
      <button
        type="button"
        id={id}
        ref={triggerRef}
        disabled={disabled}
        className="input flex w-full items-center justify-between text-left disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-400"
        onClick={() => setOpen((o) => !o)}
      >
        <span className={value ? "" : "text-gray-400"}>
          {value ? formatDate(value, "BS", { format: "DMY_TEXT" }) : "Select date…"}
        </span>
        <Calendar className="h-4 w-4 shrink-0 text-gray-400" />
      </button>

      {open &&
        createPortal(
          <div
            ref={popupRef}
            style={{ position: "fixed", top: pos.top, left: pos.left, width: POPUP_W }}
            className="z-[60] rounded-lg border border-gray-200 bg-white p-3 shadow-xl"
          >
            {/* Month / year navigation */}
            <div className="mb-2 flex items-center justify-between">
              <div className="flex gap-1">
                <NavBtn onClick={() => shiftYear(-1)} label="Previous year">
                  <ChevronsLeft className="h-4 w-4" />
                </NavBtn>
                <NavBtn onClick={() => shiftMonth(-1)} label="Previous month">
                  <ChevronLeft className="h-4 w-4" />
                </NavBtn>
              </div>
              <div className="text-sm font-medium text-gray-800">
                {BS_MONTHS[view.month]} {view.year}
              </div>
              <div className="flex gap-1">
                <NavBtn onClick={() => shiftMonth(1)} label="Next month">
                  <ChevronRight className="h-4 w-4" />
                </NavBtn>
                <NavBtn onClick={() => shiftYear(1)} label="Next year">
                  <ChevronsRight className="h-4 w-4" />
                </NavBtn>
              </div>
            </div>

            {/* Weekday headers */}
            <div className="mb-1 grid grid-cols-7 gap-1 text-center text-xs font-medium text-gray-400">
              {WEEKDAYS.map((w) => (
                <div key={w}>{w}</div>
              ))}
            </div>

            {/* Day grid */}
            <div className="grid grid-cols-7 gap-1">
              {cells.map((d, i) =>
                d === null ? (
                  <div key={`blank-${i}`} />
                ) : (
                  <button
                    key={d}
                    type="button"
                    onClick={() => pick(d)}
                    className={[
                      "h-8 rounded-md text-sm",
                      sameCell(selected, d)
                        ? "bg-brand-600 font-semibold text-white"
                        : sameCell(today, d)
                          ? "text-gray-800 ring-1 ring-brand-500 hover:bg-gray-100"
                          : "text-gray-700 hover:bg-gray-100",
                    ].join(" ")}
                  >
                    {d}
                  </button>
                ),
              )}
            </div>

            {/* Quick jump to today */}
            <div className="mt-2 flex justify-end">
              <button
                type="button"
                className="text-xs font-medium text-brand-600 hover:underline"
                onClick={() => {
                  onChange(bsToApi(today.year, today.month, today.day));
                  setOpen(false);
                }}
              >
                Today
              </button>
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}

function NavBtn({ onClick, label, children }) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      className="rounded p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
    >
      {children}
    </button>
  );
}
