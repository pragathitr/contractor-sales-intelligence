"use client";

import { LeadListParams } from "@/lib/api";

const CERTIFICATION_OPTIONS = [
  { value: "", label: "All certifications" },
  { value: "master_elite", label: "Master Elite" },
  { value: "certified_plus", label: "Certified Plus" },
  { value: "certified", label: "Certified" },
  { value: "other_verified", label: "Other verified" },
];

const RATING_OPTIONS = [0, 4.0, 4.5, 4.8];

interface Props {
  value: LeadListParams;
  onChange: (next: LeadListParams) => void;
}

export function LeadFilters({ value, onChange }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
      <input
        type="text"
        placeholder="Search contractor name..."
        defaultValue={value.search}
        onChange={(e) => onChange({ ...value, search: e.target.value })}
        className="min-w-[220px] flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800"
      />

      <select
        value={value.certification ?? ""}
        onChange={(e) => onChange({ ...value, certification: e.target.value || undefined })}
        className="rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800"
      >
        {CERTIFICATION_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>

      <select
        value={value.minimum_rating ?? 0}
        onChange={(e) => onChange({ ...value, minimum_rating: Number(e.target.value) || undefined })}
        className="rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800"
      >
        {RATING_OPTIONS.map((r) => (
          <option key={r} value={r}>
            {r === 0 ? "Any rating" : `${r}+ stars`}
          </option>
        ))}
      </select>

      <select
        value={value.sort ?? "lead_priority"}
        onChange={(e) => onChange({ ...value, sort: e.target.value as LeadListParams["sort"] })}
        className="rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800"
      >
        <option value="lead_priority">Sort: Lead Priority</option>
        <option value="account_fit">Sort: Account Fit</option>
      </select>
    </div>
  );
}
