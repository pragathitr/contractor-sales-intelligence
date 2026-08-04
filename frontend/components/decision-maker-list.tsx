"use client";

import { DecisionMakerFinding } from "@/lib/types";

const CONFIDENCE_COLOR: Record<string, string> = {
  high: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  medium: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  low: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

interface Props {
  items: DecisionMakerFinding[];
  showTechnical: boolean;
}

export function DecisionMakerList({ items, showTechnical }: Props) {
  if (items.length === 0) {
    return (
      <div>
        <h4 className="mb-1 text-sm font-semibold">Decision-makers</h4>
        <p className="text-sm text-slate-500">
          No verified owner, GM, or purchasing contact was found in public sources — outreach may need to start
          through a generic business line.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h4 className="mb-2 text-sm font-semibold">Decision-makers</h4>
      <ul className="space-y-3">
        {items.map((dm, i) => (
          <li key={i} className="rounded-md border border-slate-200 p-3 text-sm dark:border-slate-800">
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="font-semibold text-slate-900 dark:text-slate-100">{dm.name}</span>
              {dm.title && <span className="text-slate-500">{dm.title}</span>}
            </div>
            <div className="mt-1 flex flex-wrap gap-3 text-slate-700 dark:text-slate-300">
              {dm.business_phone && (
                <a href={`tel:${dm.business_phone}`} className="underline decoration-dotted">
                  {dm.business_phone}
                </a>
              )}
              {dm.business_email && (
                <a href={`mailto:${dm.business_email}`} className="underline decoration-dotted">
                  {dm.business_email}
                </a>
              )}
              {!dm.business_phone && !dm.business_email && <span className="text-slate-400">No direct contact found</span>}
            </div>
            {dm.evidence.length > 0 && (
              <ul className="mt-2 space-y-1 border-t border-slate-100 pt-2 dark:border-slate-800">
                {dm.evidence.map((e, j) => (
                  <li key={j} className="text-xs">
                    <a href={e.source_url} target="_blank" rel="noreferrer" className="text-blue-600 underline dark:text-blue-400">
                      {e.source_title ?? e.source_url}
                    </a>{" "}
                    <span
                      className={`ml-1 rounded-full px-1.5 py-0.5 font-medium ${CONFIDENCE_COLOR[e.confidence]}`}
                    >
                      {showTechnical ? `confidence: ${e.confidence}` : e.confidence === "high" ? "Verified" : "Needs checking"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
