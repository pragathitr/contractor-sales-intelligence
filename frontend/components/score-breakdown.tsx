"use client";

import { ScoreBreakdown as ScoreBreakdownType } from "@/lib/types";
import { priorityLabel, round } from "@/lib/format";

interface Props {
  scores: ScoreBreakdownType[];
  provisional: boolean;
  showTechnical: boolean;
}

const SCORE_TITLES: Record<string, string> = {
  lead_priority: "Lead Priority",
  account_fit: "Account Fit",
  opportunity: "Opportunity",
};

function subcomponentLabel(key: string): string {
  return key
    .split("_")
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(" ");
}

export function ScoreBreakdownPanel({ scores, provisional, showTechnical }: Props) {
  const leadPriority = scores.find((s) => s.score_type === "lead_priority");
  const accountFit = scores.find((s) => s.score_type === "account_fit");
  const opportunity = scores.find((s) => s.score_type === "opportunity");

  if (!leadPriority) {
    return <p className="text-sm text-slate-500">No score is available for this contractor yet.</p>;
  }

  if (!showTechnical) {
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <span className="text-lg font-semibold">
            Priority: {priorityLabel(leadPriority.total)} · {round(leadPriority.total)}
          </span>
          {provisional && (
            <span className="rounded-full bg-orange-100 px-2 py-0.5 text-xs font-medium text-orange-800 dark:bg-orange-900/40 dark:text-orange-300">
              Provisional
            </span>
          )}
        </div>
        <p className="text-sm text-slate-600 dark:text-slate-400">
          Based on {round(leadPriority.coverage)}% of available signals across account fit and opportunity.
        </p>
        {accountFit && <p className="text-sm text-slate-600 dark:text-slate-400">Account Fit: {round(accountFit.total)}</p>}
        {opportunity && (
          <p className="text-sm text-slate-600 dark:text-slate-400">Opportunity: {round(opportunity.total)}</p>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="font-mono text-sm">
          Lead Priority {round(leadPriority.total, 2)} · {leadPriority.formula_version}
        </p>
        <p className="font-mono text-xs text-slate-500">coverage {round(leadPriority.coverage, 2)}%</p>
      </div>

      {[accountFit, opportunity].filter(Boolean).map((score) => (
        <div key={score!.score_type}>
          <p className="mb-2 font-mono text-sm font-semibold">
            {SCORE_TITLES[score!.score_type]} {round(score!.total, 2)} · {score!.formula_version} (coverage{" "}
            {round(score!.coverage, 2)}%)
          </p>
          <table className="w-full border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-left text-slate-500 dark:border-slate-700">
                <th className="py-1 pr-2">Subcomponent</th>
                <th className="py-1 pr-2">Points</th>
                <th className="py-1 pr-2">Max</th>
                <th className="py-1">Available</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(score!.breakdown).map(([key, value]) => {
                const v = value as { points: number | null; max_points: number; available: boolean };
                return (
                  <tr key={key} className="border-b border-slate-100 dark:border-slate-800">
                    <td className="py-1 pr-2 font-mono">{subcomponentLabel(key)}</td>
                    <td className="py-1 pr-2 font-mono">{v.points ?? "—"}</td>
                    <td className="py-1 pr-2 font-mono">{v.max_points}</td>
                    <td className="py-1 font-mono">{v.available ? "yes" : "unavailable"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}
