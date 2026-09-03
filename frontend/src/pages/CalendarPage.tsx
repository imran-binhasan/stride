import React, { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { CalendarView, Project } from "../types";
import { api } from "../services/api";

interface CalendarPageProps {
  project: Project;
}

export const CalendarPage: React.FC<CalendarPageProps> = ({ project }) => {
  const [currentMonth, setCurrentMonth] = useState(new Date().getMonth() + 1);
  const [currentYear, setCurrentYear] = useState(new Date().getFullYear());
  const [calendar, setCalendar] = useState<CalendarView | null>(null);

  // Refetch whenever the project or the selected month/year changes.
  useEffect(() => {
    let cancelled = false;
    api
      .getCalendar(project.id, currentMonth, currentYear)
      .then((cal) => {
        if (!cancelled) setCalendar(cal);
      })
      .catch((e) => console.error("Failed to load calendar:", e));
    return () => {
      cancelled = true;
    };
  }, [project.id, currentMonth, currentYear]);

  const monthNames = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
  ];

  const handlePrevMonth = () => {
    if (currentMonth === 1) {
      setCurrentMonth(12);
      setCurrentYear(currentYear - 1);
    } else {
      setCurrentMonth(currentMonth - 1);
    }
  };

  const handleNextMonth = () => {
    if (currentMonth === 12) {
      setCurrentMonth(1);
      setCurrentYear(currentYear + 1);
    } else {
      setCurrentMonth(currentMonth + 1);
    }
  };

  // Generate 35 calendar grid days for the month
  const firstDayIndex = new Date(currentYear, currentMonth - 1, 1).getDay();
  const daysInMonth = new Date(currentYear, currentMonth, 0).getDate();

  const days = [];
  for (let i = 0; i < firstDayIndex; i++) {
    days.push({ dayNumber: null, dateStr: null });
  }
  for (let d = 1; d <= daysInMonth; d++) {
    const monthStr = currentMonth.toString().padStart(2, "0");
    const dayStr = d.toString().padStart(2, "0");
    days.push({
      dayNumber: d,
      dateStr: `${currentYear}-${monthStr}-${dayStr}`,
    });
  }

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-950 p-6 select-none overflow-y-auto">
      {/* Calendar Header */}
      <div className="flex items-center justify-between mb-6 shrink-0">
        <div>
          <h1 className="text-lg font-bold text-white tracking-tight">Project Calendar</h1>
          <p className="text-xs text-slate-400">Scheduled milestones, sprint targets, and due dates</p>
        </div>

        {/* Month Navigation */}
        <div className="flex items-center gap-3 bg-slate-900 border border-slate-800 rounded-xl p-1.5 shadow-sm">
          <button
            onClick={handlePrevMonth}
            className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-xs font-bold text-white px-2">
            {monthNames[currentMonth - 1]} {currentYear}
          </span>
          <button
            onClick={handleNextMonth}
            className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Weekday Headers */}
      <div className="grid grid-cols-7 gap-2 mb-2 text-center text-xs font-bold text-slate-500 uppercase tracking-wider">
        <span>Sun</span>
        <span>Mon</span>
        <span>Tue</span>
        <span>Wed</span>
        <span>Thu</span>
        <span>Fri</span>
        <span>Sat</span>
      </div>

      {/* Calendar Grid */}
      <div className="grid grid-cols-7 gap-2 flex-1 auto-rows-fr">
        {days.map((day, idx) => {
          const events = calendar?.events.filter((e) => e.due_date === day.dateStr) || [];
          return (
            <div
              key={idx}
              className={`min-h-[110px] p-2.5 rounded-xl border flex flex-col justify-between transition-colors ${
                day.dayNumber
                  ? "bg-slate-900/40 border-slate-800 hover:border-slate-700"
                  : "bg-slate-950/40 border-transparent opacity-30"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-400">{day.dayNumber || ""}</span>
                {events.length > 0 && (
                  <span className="w-1.5 h-1.5 rounded-full bg-sky-400" />
                )}
              </div>

              {/* Task Items */}
              <div className="space-y-1.5 my-1 overflow-y-auto max-h-24">
                {events.map((ev) => (
                  <div
                    key={ev.id}
                    className="p-1.5 rounded-md bg-slate-800/80 border border-slate-700/60 text-[11px] space-y-0.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[10px] font-bold text-sky-400">{ev.short_id}</span>
                      <span
                        className="w-2 h-2 rounded-full"
                        style={{ backgroundColor: ev.status_color }}
                      />
                    </div>
                    <p className="text-slate-200 font-medium truncate">{ev.title}</p>
                  </div>
                ))}
              </div>

              <div className="text-[10px] text-slate-600 font-mono">
                {events.length > 0 ? `${events.length} target` : ""}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
