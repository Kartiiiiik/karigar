import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Controller } from "react-hook-form";
import { Check, ChevronDown } from "lucide-react";

const MAX_POPUP_H = 288; // matches max-h-72
const ITEM_H = 36; // approximate; used only for edge-flip decisions
const MIN_POPUP_W = 160; // keep narrow triggers (w-24) from opening a cramped list
const GAP = 4;
const MARGIN = 8;
const TYPEAHEAD_MS = 600;

/**
 * Styled single-select. Replaces the native `<select>`, whose option list is
 * drawn by the OS and can't be styled — on Windows it renders with the system
 * font, its own highlight colour and a hard black frame, none of which match
 * the app.
 *
 * The value in/out is ALWAYS a string, exactly as a native select reported
 * `e.target.value`, so callers that parse it (`Number(...)`, `=== "true"`) keep
 * working unchanged. `options` is `[{ value, label }]`; include an entry with
 * `value: ""` when "no selection" should be pickable (e.g. "All karigars").
 * `placeholder` shows only when the value matches no option.
 *
 * Focus stays on the trigger while the list is open and the active option is
 * tracked with `aria-activedescendant` — the listbox pattern, which avoids
 * moving focus into the portal.
 */
export default function Select({
  value,
  onChange,
  onBlur,
  options = [],
  placeholder = "Select…",
  disabled = false,
  id,
  name,
  className = "",
  "aria-label": ariaLabel,
  "aria-invalid": ariaInvalid,
}) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [pos, setPos] = useState({ top: 0, left: 0, width: 0, flipped: false });
  const triggerRef = useRef(null);
  const popupRef = useRef(null);
  const typeahead = useRef({ buffer: "", at: 0 });

  // Native selects stringify option values (`value={24}` -> "24"), and callers
  // depend on that. Do the same so comparisons are always string-to-string.
  const items = useMemo(
    () => options.map((o) => ({ value: String(o.value ?? ""), label: o.label })),
    [options],
  );
  const current = value == null ? "" : String(value);
  const selectedIndex = items.findIndex((o) => o.value === current);
  const selected = selectedIndex >= 0 ? items[selectedIndex] : null;

  // Position the popup relative to the trigger, in viewport (fixed) coords so
  // it escapes the modal's overflow clipping. Flip above / clamp to the screen
  // when it would run off an edge.
  const place = () => {
    const el = triggerRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const width = Math.min(
      Math.max(r.width, MIN_POPUP_W),
      window.innerWidth - MARGIN * 2,
    );
    let left = r.left;
    if (left + width > window.innerWidth - MARGIN) {
      left = window.innerWidth - width - MARGIN;
    }
    if (left < MARGIN) left = MARGIN;

    const height = Math.min(MAX_POPUP_H, items.length * ITEM_H + 8);
    let top = r.bottom + GAP;
    let flipped = false;
    if (top + height > window.innerHeight - MARGIN) {
      const above = r.top - height - GAP;
      if (above >= MARGIN) {
        top = above;
        flipped = true;
      } else {
        top = Math.max(MARGIN, window.innerHeight - height - MARGIN);
      }
    }
    setPos({ top, left, width, flipped });
  };

  // On open: start from the selected row (or the top) and place the popup.
  useLayoutEffect(() => {
    if (!open) return;
    setActive(selectedIndex >= 0 ? selectedIndex : 0);
    place();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  // Keep it anchored on scroll / resize, and dismiss on outside click.
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
    window.addEventListener("scroll", reposition, true); // capture: catch scroll on any ancestor
    window.addEventListener("resize", reposition);
    document.addEventListener("mousedown", onDown);
    return () => {
      window.removeEventListener("scroll", reposition, true);
      window.removeEventListener("resize", reposition);
      document.removeEventListener("mousedown", onDown);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, items.length]);

  // Keep the keyboard-active row visible in the scroll area.
  useEffect(() => {
    if (!open || active < 0) return;
    popupRef.current
      ?.querySelector(`[data-index="${active}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [open, active]);

  const commit = (index) => {
    const item = items[index];
    if (!item) return;
    setOpen(false);
    if (item.value !== current) onChange?.(item.value);
  };

  const step = (delta) => {
    if (!items.length) return;
    setActive((i) => {
      const from = i < 0 ? (selectedIndex >= 0 ? selectedIndex : 0) : i;
      return Math.min(items.length - 1, Math.max(0, from + delta));
    });
  };

  /** Native selects jump to the option matching typed letters — keep that, it
   *  matters for the long karigar / customer lists. */
  const jumpTo = (char) => {
    const now = Date.now();
    const t = typeahead.current;
    t.buffer = now - t.at > TYPEAHEAD_MS ? char : t.buffer + char;
    t.at = now;
    const hit = items.findIndex((o) =>
      o.label?.toLowerCase().startsWith(t.buffer.toLowerCase()),
    );
    if (hit < 0) return;
    if (open) setActive(hit);
    else commit(hit);
  };

  const onKeyDown = (e) => {
    if (disabled) return;
    if (e.key === "Escape") {
      if (open) {
        e.stopPropagation(); // don't also close the surrounding modal
        setOpen(false);
      }
      return;
    }
    if (e.key === "Tab") {
      setOpen(false);
      return;
    }
    if (!open && (e.key === "Enter" || e.key === " " || e.key === "ArrowDown" || e.key === "ArrowUp")) {
      e.preventDefault();
      setOpen(true);
      return;
    }
    if (open && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      commit(active);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      step(1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      step(-1);
    } else if (e.key === "Home") {
      e.preventDefault();
      setActive(0);
    } else if (e.key === "End") {
      e.preventDefault();
      setActive(items.length - 1);
    } else if (e.key.length === 1 && !e.metaKey && !e.ctrlKey && !e.altKey) {
      jumpTo(e.key);
    }
  };

  const listId = id ? `${id}-listbox` : undefined;

  return (
    <>
      <button
        type="button"
        id={id}
        name={name}
        ref={triggerRef}
        disabled={disabled}
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-activedescendant={open && active >= 0 && id ? `${id}-opt-${active}` : undefined}
        aria-label={ariaLabel}
        aria-invalid={ariaInvalid}
        onClick={() => setOpen((o) => !o)}
        onKeyDown={onKeyDown}
        onBlur={onBlur}
        className={`input flex items-center justify-between gap-2 text-left disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-400 ${className}`}
      >
        {/* min-w-0 so a long karigar name ellipsizes instead of stretching the row. */}
        <span className={`min-w-0 truncate ${selected ? "" : "text-gray-400"}`}>
          {selected ? selected.label : placeholder}
        </span>
        <ChevronDown className="h-4 w-4 shrink-0 text-gray-400" aria-hidden="true" />
      </button>

      {open &&
        createPortal(
          <div
            ref={popupRef}
            id={listId}
            role="listbox"
            aria-label={ariaLabel}
            style={{
              position: "fixed",
              top: pos.top,
              left: pos.left,
              width: pos.width,
              maxHeight: MAX_POPUP_H,
            }}
            className="z-[60] overflow-y-auto overscroll-contain rounded-lg border border-gray-200 bg-white py-1 shadow-xl"
          >
            {items.length === 0 && (
              <div className="px-3 py-2 text-sm text-gray-400">No options</div>
            )}
            {items.map((o, i) => {
              const isSelected = o.value === current;
              return (
                <button
                  key={`${o.value}-${i}`}
                  type="button"
                  id={id ? `${id}-opt-${i}` : undefined}
                  data-index={i}
                  role="option"
                  aria-selected={isSelected}
                  tabIndex={-1}
                  onClick={() => commit(i)}
                  onMouseEnter={() => setActive(i)}
                  className={[
                    "flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm",
                    i === active ? "bg-brand-50" : "",
                    isSelected ? "font-medium text-brand-700" : "text-gray-700",
                  ].join(" ")}
                >
                  <span className="truncate">{o.label}</span>
                  {isSelected && <Check className="h-4 w-4 shrink-0" aria-hidden="true" />}
                </button>
              );
            })}
          </div>,
          document.body,
        )}
    </>
  );
}

/**
 * react-hook-form binding for `Select`. A custom control can't be `register`ed
 * (there is no native input for RHF to attach a ref to), so it goes through
 * `Controller`. Emits strings just like the native select it replaces.
 */
export function FormSelect({ control, name, rules, defaultValue, ...rest }) {
  return (
    <Controller
      control={control}
      name={name}
      rules={rules}
      defaultValue={defaultValue}
      render={({ field, fieldState }) => (
        <Select
          {...rest}
          value={field.value}
          onChange={field.onChange}
          onBlur={field.onBlur}
          name={field.name}
          aria-invalid={fieldState.invalid || undefined}
        />
      )}
    />
  );
}
