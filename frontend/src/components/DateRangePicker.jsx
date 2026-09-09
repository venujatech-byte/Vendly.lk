import { useEffect, useMemo, useRef, useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight, X } from "lucide-react";
import "./DateRangePicker.css";

// Formats a Date object to "YYYY-MM-DD" local time string safely without UTC shifts.
function toISODateString(date) {
  if (!date || isNaN(date.getTime())) return "";
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

// Parses "YYYY-MM-DD" string to local Date object (at midnight).
function parseISODateString(str) {
  if (!str || typeof str !== "string") return null;
  const parts = str.split("-");
  if (parts.length !== 3) return null;
  const y = parseInt(parts[0], 10);
  const m = parseInt(parts[1], 10) - 1;
  const d = parseInt(parts[2], 10);
  if (isNaN(y) || isNaN(m) || isNaN(d)) return null;
  return new Date(y, m, d);
}

// Formats date for display, e.g. "15 May" or "15 May 2024"
function formatDisplayDate(isoString, includeYear = true) {
  const date = parseISODateString(isoString);
  if (!date) return "";
  const day = date.getDate();
  const monthNames = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
  ];
  const month = monthNames[date.getMonth()];
  if (!includeYear) return `${day} ${month}`;
  return `${day} ${month} ${date.getFullYear()}`;
}

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

const WEEKDAY_NAMES = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];

// Preset calculations relative to today
function getPresets() {
  const now = new Date();
  const todayIso = toISODateString(now);

  const yesterdayDate = new Date(now);
  yesterdayDate.setDate(yesterdayDate.getDate() - 1);
  const yesterdayIso = toISODateString(yesterdayDate);

  const last7DaysDate = new Date(now);
  last7DaysDate.setDate(last7DaysDate.getDate() - 6);
  const last7DaysIso = toISODateString(last7DaysDate);

  const last30DaysDate = new Date(now);
  last30DaysDate.setDate(last30DaysDate.getDate() - 29);
  const last30DaysIso = toISODateString(last30DaysDate);

  const last6MonthsDate = new Date(now);
  last6MonthsDate.setMonth(last6MonthsDate.getMonth() - 6);
  const last6MonthsIso = toISODateString(last6MonthsDate);

  const lastYearDate = new Date(now);
  lastYearDate.setFullYear(lastYearDate.getFullYear() - 1);
  const lastYearIso = toISODateString(lastYearDate);

  return [
    { label: "Today", start: todayIso, end: todayIso },
    { label: "Yesterday", start: yesterdayIso, end: yesterdayIso },
    { label: "Last 7 days", start: last7DaysIso, end: todayIso },
    { label: "Last 30 days", start: last30DaysIso, end: todayIso },
    { label: "Last 6 months", start: last6MonthsIso, end: todayIso },
    { label: "Last year", start: lastYearIso, end: todayIso },
    { label: "All time", start: "", end: "" },
  ];
}

// Builds the 35 or 42 grid cells for a specific month (including muted previous & next month dates)
function generateMonthDays(year, month) {
  const firstDayOfMonth = new Date(year, month, 1);
  const startDayOfWeek = firstDayOfMonth.getDay(); // 0 = Sunday

  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const daysInPrevMonth = new Date(year, month, 0).getDate();

  const days = [];

  // Previous month trailing days
  for (let i = startDayOfWeek - 1; i >= 0; i--) {
    const prevDate = new Date(year, month - 1, daysInPrevMonth - i);
    days.push({
      date: prevDate,
      iso: toISODateString(prevDate),
      dayNumber: prevDate.getDate(),
      isCurrentMonth: false,
    });
  }

  // Current month days
  for (let d = 1; d <= daysInMonth; d++) {
    const currDate = new Date(year, month, d);
    days.push({
      date: currDate,
      iso: toISODateString(currDate),
      dayNumber: d,
      isCurrentMonth: true,
    });
  }

  // Next month leading days to complete grid to 35 or 42 cells (multiple of 7)
  const remaining = (7 - (days.length % 7)) % 7;
  for (let d = 1; d <= remaining; d++) {
    const nextDate = new Date(year, month + 1, d);
    days.push({
      date: nextDate,
      iso: toISODateString(nextDate),
      dayNumber: d,
      isCurrentMonth: false,
    });
  }

  return days;
}

export default function DateRangePicker({
  startDate = "",
  endDate = "",
  onChange,
  placeholder = "Select date range",
  align = "left",
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [tempStart, setTempStart] = useState(startDate);
  const [tempEnd, setTempEnd] = useState(endDate);
  const [hoverDate, setHoverDate] = useState(null);

  // Left calendar view month/year
  const [leftViewDate, setLeftViewDate] = useState(() => {
    const initial = parseISODateString(startDate) || new Date();
    return new Date(initial.getFullYear(), initial.getMonth(), 1);
  });

  const pickerRef = useRef(null);

  // Synchronize internal state when props change externally
  useEffect(() => {
    setTempStart(startDate);
    setTempEnd(endDate);
  }, [startDate, endDate]);

  // When opening, make sure the calendar view reflects the selected range or today
  useEffect(() => {
    if (isOpen) {
      setTempStart(startDate);
      setTempEnd(endDate);
      const initial = parseISODateString(startDate) || new Date();
      setLeftViewDate(new Date(initial.getFullYear(), initial.getMonth(), 1));
    }
  }, [isOpen, startDate, endDate]);

  // Right calendar view is always 1 month after leftViewDate
  const rightViewDate = useMemo(() => {
    return new Date(leftViewDate.getFullYear(), leftViewDate.getMonth() + 1, 1);
  }, [leftViewDate]);

  // Close on outside click
  useEffect(() => {
    function handleClickOutside(event) {
      if (pickerRef.current && !pickerRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen]);

  // Close on Escape key
  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }
    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown);
    }
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  const presets = useMemo(() => getPresets(), []);

  // Determine active preset
  const activePreset = useMemo(() => {
    return presets.find(
      (p) => p.start === tempStart && p.end === tempEnd
    );
  }, [presets, tempStart, tempEnd]);

  // Navigate left calendar
  function prevMonth() {
    setLeftViewDate((curr) => new Date(curr.getFullYear(), curr.getMonth() - 1, 1));
  }

  function nextMonth() {
    setLeftViewDate((curr) => new Date(curr.getFullYear(), curr.getMonth() + 1, 1));
  }

  // Handle preset selection
  function handleSelectPreset(preset) {
    setTempStart(preset.start);
    setTempEnd(preset.end);

    if (preset.start) {
      const pDate = parseISODateString(preset.start);
      if (pDate) {
        setLeftViewDate(new Date(pDate.getFullYear(), pDate.getMonth(), 1));
      }
    }
  }

  // Day click logic
  function handleDayClick(dayIso) {
    if (!tempStart || (tempStart && tempEnd)) {
      // Start a new selection
      setTempStart(dayIso);
      setTempEnd("");
    } else if (tempStart && !tempEnd) {
      // Complete selection
      if (dayIso < tempStart) {
        setTempStart(dayIso);
        setTempEnd(tempStart);
      } else {
        setTempEnd(dayIso);
      }
    }
  }

  // Apply selected date range
  function handleApply() {
    onChange?.({
      startDate: tempStart,
      endDate: tempEnd,
    });
    setIsOpen(false);
  }

  // Cancel and revert
  function handleCancel() {
    setTempStart(startDate);
    setTempEnd(endDate);
    setIsOpen(false);
  }

  // Clear date range via the trigger X button
  function handleClear(e) {
    e.stopPropagation();
    onChange?.({ startDate: "", endDate: "" });
    setTempStart("");
    setTempEnd("");
  }

  // Check if date is in range or hovered range
  function getDayStatus(iso) {
    const isStart = iso === tempStart;
    const isEnd = iso === tempEnd;

    let inRange = false;
    if (tempStart && tempEnd) {
      inRange = iso > tempStart && iso < tempEnd;
    } else if (tempStart && !tempEnd && hoverDate) {
      const start = tempStart < hoverDate ? tempStart : hoverDate;
      const end = tempStart < hoverDate ? hoverDate : tempStart;
      inRange = iso > start && iso < end;
    }

    const isHoverEnd = !tempEnd && hoverDate && iso === hoverDate && iso !== tempStart;

    return { isStart, isEnd, inRange, isHoverEnd };
  }

  const leftMonthDays = useMemo(() => {
    return generateMonthDays(leftViewDate.getFullYear(), leftViewDate.getMonth());
  }, [leftViewDate]);

  const rightMonthDays = useMemo(() => {
    return generateMonthDays(rightViewDate.getFullYear(), rightViewDate.getMonth());
  }, [rightViewDate]);

  // Compute trigger button label
  const triggerLabel = useMemo(() => {
    if (startDate && endDate) {
      const p = presets.find((item) => item.start === startDate && item.end === endDate);
      if (p && p.label !== "All time") {
        return `${formatDisplayDate(startDate, false)} - ${formatDisplayDate(endDate, false)}`;
      }
      return `${formatDisplayDate(startDate)} - ${formatDisplayDate(endDate)}`;
    }
    if (startDate) return `From ${formatDisplayDate(startDate)}`;
    if (endDate) return `Until ${formatDisplayDate(endDate)}`;
    return placeholder;
  }, [startDate, endDate, presets, placeholder]);

  return (
    <div
      className={`date-range-picker ${isOpen ? "is-open" : ""}`}
      ref={pickerRef}
    >
      {/* Trigger Button */}
      <button
        type="button"
        className={`date-range-picker__trigger ${startDate || endDate ? "has-value" : ""}`}
        onClick={() => setIsOpen((prev) => !prev)}
        aria-haspopup="dialog"
        aria-expanded={isOpen}
      >
        <CalendarDays className="date-range-picker__trigger-icon" size={16} aria-hidden="true" />
        <span className="date-range-picker__trigger-label">{triggerLabel}</span>
        {(startDate || endDate) && (
          <span
            role="button"
            tabIndex={0}
            className="date-range-picker__trigger-clear"
            onClick={handleClear}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                handleClear(e);
              }
            }}
            title="Clear date range"
            aria-label="Clear date range"
          >
            <X size={14} />
          </span>
        )}
      </button>

      {/* Popover Backdrop on Mobile */}
      {isOpen && (
        <div
          className="date-range-picker__backdrop"
          onClick={handleCancel}
          aria-hidden="true"
        />
      )}

      {/* Popover Card */}
      {isOpen && (
        <div
          className={`date-range-picker__popover date-range-picker__popover--${align}`}
          role="dialog"
          aria-label="Date range selector"
        >
          {/* Mobile Bottom-Sheet Header */}
          <div className="date-range-picker__mobile-header">
            <div className="date-range-picker__drag-handle" />
            <div className="date-range-picker__mobile-title-bar">
              <span className="date-range-picker__mobile-title">Select Date Range</span>
              <button
                type="button"
                className="date-range-picker__mobile-close"
                onClick={handleCancel}
                aria-label="Close date range picker"
              >
                <X size={18} />
              </button>
            </div>
          </div>

          <div className="date-range-picker__body">
            {/* Sidebar Presets */}
            <aside className="date-range-picker__presets" aria-label="Date range shortcuts">
              {presets.map((preset) => {
                const isActive = activePreset?.label === preset.label;
                return (
                  <button
                    key={preset.label}
                    type="button"
                    className={`date-range-picker__preset-btn ${isActive ? "is-active" : ""}`}
                    onClick={() => handleSelectPreset(preset)}
                  >
                    {preset.label}
                  </button>
                );
              })}
            </aside>

            {/* Calendars Container */}
            <div className="date-range-picker__calendars">
              {/* Left Calendar */}
              <div className="date-range-picker__calendar">
                <header className="date-range-picker__calendar-header">
                  <button
                    type="button"
                    className="date-range-picker__nav-btn"
                    onClick={prevMonth}
                    aria-label="Previous month"
                  >
                    <ChevronLeft size={16} />
                  </button>
                  <span className="date-range-picker__month-title">
                    {MONTH_NAMES[leftViewDate.getMonth()]} {leftViewDate.getFullYear()}
                  </span>
                  <button
                    type="button"
                    className="date-range-picker__nav-btn date-range-picker__nav-btn--mobile-only"
                    onClick={nextMonth}
                    aria-label="Next month"
                  >
                    <ChevronRight size={16} />
                  </button>
                  <div className="date-range-picker__nav-spacer date-range-picker__nav-spacer--desktop-only" />
                </header>

                <div className="date-range-picker__weekdays">
                  {WEEKDAY_NAMES.map((w) => (
                    <span key={w} className="date-range-picker__weekday">
                      {w}
                    </span>
                  ))}
                </div>

                <div
                  className="date-range-picker__grid"
                  onMouseLeave={() => setHoverDate(null)}
                >
                  {leftMonthDays.map((cell) => {
                    const { isStart, isEnd, inRange, isHoverEnd } = getDayStatus(cell.iso);
                    return (
                      <div
                        key={cell.iso}
                        className={`date-range-picker__cell-wrap ${
                          inRange ? "is-in-range" : ""
                        } ${isStart ? "is-range-start" : ""} ${
                          isEnd || isHoverEnd ? "is-range-end" : ""
                        }`}
                      >
                        <button
                          type="button"
                          className={`date-range-picker__day-btn ${
                            !cell.isCurrentMonth ? "is-muted" : ""
                          } ${isStart ? "is-start" : ""} ${
                            isEnd ? "is-end" : ""
                          } ${isHoverEnd ? "is-hover-end" : ""}`}
                          onClick={() => handleDayClick(cell.iso)}
                          onMouseEnter={() => {
                            if (tempStart && !tempEnd) {
                              setHoverDate(cell.iso);
                            }
                          }}
                        >
                          {cell.dayNumber}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Right Calendar */}
              <div className="date-range-picker__calendar">
                <header className="date-range-picker__calendar-header">
                  <button
                    type="button"
                    className="date-range-picker__nav-btn date-range-picker__nav-btn--mobile-only"
                    onClick={prevMonth}
                    aria-label="Previous month"
                  >
                    <ChevronLeft size={16} />
                  </button>
                  <div className="date-range-picker__nav-spacer date-range-picker__nav-spacer--desktop-only" />
                  <span className="date-range-picker__month-title">
                    {MONTH_NAMES[rightViewDate.getMonth()]} {rightViewDate.getFullYear()}
                  </span>
                  <button
                    type="button"
                    className="date-range-picker__nav-btn"
                    onClick={nextMonth}
                    aria-label="Next month"
                  >
                    <ChevronRight size={16} />
                  </button>
                </header>

                <div className="date-range-picker__weekdays">
                  {WEEKDAY_NAMES.map((w) => (
                    <span key={w} className="date-range-picker__weekday">
                      {w}
                    </span>
                  ))}
                </div>

                <div
                  className="date-range-picker__grid"
                  onMouseLeave={() => setHoverDate(null)}
                >
                  {rightMonthDays.map((cell) => {
                    const { isStart, isEnd, inRange, isHoverEnd } = getDayStatus(cell.iso);
                    return (
                      <div
                        key={cell.iso}
                        className={`date-range-picker__cell-wrap ${
                          inRange ? "is-in-range" : ""
                        } ${isStart ? "is-range-start" : ""} ${
                          isEnd || isHoverEnd ? "is-range-end" : ""
                        }`}
                      >
                        <button
                          type="button"
                          className={`date-range-picker__day-btn ${
                            !cell.isCurrentMonth ? "is-muted" : ""
                          } ${isStart ? "is-start" : ""} ${
                            isEnd ? "is-end" : ""
                          } ${isHoverEnd ? "is-hover-end" : ""}`}
                          onClick={() => handleDayClick(cell.iso)}
                          onMouseEnter={() => {
                            if (tempStart && !tempEnd) {
                              setHoverDate(cell.iso);
                            }
                          }}
                        >
                          {cell.dayNumber}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>

          {/* Footer Action Bar */}
          <footer className="date-range-picker__footer">
            <div className="date-range-picker__badges">
              <span className="date-range-picker__badge">
                {tempStart ? formatDisplayDate(tempStart, false) : "Start date"}
              </span>
              <span className="date-range-picker__badge-sep">—</span>
              <span className="date-range-picker__badge">
                {tempEnd ? formatDisplayDate(tempEnd, false) : "End date"}
              </span>
            </div>

            <div className="date-range-picker__actions">
              <button
                type="button"
                className="date-range-picker__btn-cancel"
                onClick={handleCancel}
              >
                Cancel
              </button>
              <button
                type="button"
                className="date-range-picker__btn-apply"
                onClick={handleApply}
              >
                Apply
              </button>
            </div>
          </footer>
        </div>
      )}
    </div>
  );
}
