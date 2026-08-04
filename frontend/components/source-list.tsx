"use client";

import { EvidenceItem } from "@/lib/types";

interface Props {
  title: string;
  items: EvidenceItem[];
  showTechnical: boolean;
}

const CONFIDENCE_COLOR: Record<string, string> = {
  high: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  medium: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  low: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

export function SourceList({ title, items, showTechnical }: Props) {
  if (items.length === 0) {
    return (
      <div>
        <h4 className="mb-1 text-sm font-semibold">{title}</h4>
        <p className="text-sm text-slate-500">None found in available public sources.</p>
      </div>
    );
  }

  return (
    <div>
      <h4 className="mb-2 text-sm font-semibold">{title}</h4>
      <ul className="space-y-2">
        {items.map((item, i) => (
          <li key={i} className="rounded-md border border-slate-200 p-2 text-sm dark:border-slate-800">
            <p className="text-slate-700 dark:text-slate-300">{item.evidence}</p>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
              <a href={item.source_url} target="_blank" rel="noreferrer" className="text-blue-600 underline dark:text-blue-400">
                {item.source_title ?? item.source_url}
              </a>
              <span className={`rounded-full px-2 py-0.5 font-medium ${CONFIDENCE_COLOR[item.confidence]}`}>
                {showTechnical ? `confidence: ${item.confidence}` : item.confidence === "high" ? "Verified" : "Needs checking"}
              </span>
              {item.published_at && <span className="text-slate-400">{item.published_at}</span>}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
