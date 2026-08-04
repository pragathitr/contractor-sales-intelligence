"use client";

import { LeadListItem } from "@/lib/types";
import { certificationLabel, priorityLabel, round, statusLabel } from "@/lib/format";

interface Props {
  items: LeadListItem[];
  onSelect: (contractorId: number) => void;
}

function StatusBadge({ status }: { status: string }) {
  const color =
    status === "completed"
      ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
      : status === "failed"
        ? "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300"
        : "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300";
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${color}`}>{statusLabel(status)}</span>;
}

export function LeadTable({ items, onSelect }: Props) {
  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 p-12 text-center text-slate-500 dark:border-slate-700">
        No leads match the current filters.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
      <table className="w-full min-w-[900px] text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500 dark:bg-slate-900 dark:text-slate-400">
          <tr>
            <th className="px-4 py-3">Contractor</th>
            <th className="px-4 py-3">Priority</th>
            <th className="px-4 py-3">Account Fit</th>
            <th className="px-4 py-3">Certification</th>
            <th className="px-4 py-3">Rating</th>
            <th className="px-4 py-3">Distance</th>
            <th className="px-4 py-3">Experience</th>
            <th className="px-4 py-3">Research</th>
            <th className="px-4 py-3">Outreach angle</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
          {items.map((item) => (
            <tr
              key={item.contractor_id}
              onClick={() => onSelect(item.contractor_id)}
              className="cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/60"
            >
              <td className="px-4 py-3 font-medium text-slate-900 dark:text-slate-100">{item.name}</td>
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <span className="font-semibold">{priorityLabel(item.lead_priority)}</span>
                  <span className="text-slate-400">{round(item.lead_priority)}</span>
                  {item.provisional && (
                    <span className="rounded-full bg-orange-100 px-2 py-0.5 text-xs font-medium text-orange-800 dark:bg-orange-900/40 dark:text-orange-300">
                      Provisional
                    </span>
                  )}
                </div>
              </td>
              <td className="px-4 py-3">{round(item.account_fit)}</td>
              <td className="px-4 py-3">{certificationLabel(item.certification_tier)}</td>
              <td className="px-4 py-3">
                {item.rating ?? "—"} {item.review_count !== null && <span className="text-slate-400">({item.review_count})</span>}
              </td>
              <td className="px-4 py-3">{item.distance_miles !== null ? `${item.distance_miles} mi` : "—"}</td>
              <td className="px-4 py-3">{item.years_in_business !== null ? `${item.years_in_business} yrs` : "—"}</td>
              <td className="px-4 py-3">
                <StatusBadge status={item.research_status} />
              </td>
              <td className="max-w-[260px] truncate px-4 py-3 text-slate-600 dark:text-slate-400">
                {item.outreach_angle ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export { StatusBadge };
