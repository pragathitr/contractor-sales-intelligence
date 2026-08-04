"use client";

import { useEffect, useState } from "react";
import { fetchLeadDetail } from "@/lib/api";
import { LeadDetailResponse } from "@/lib/types";
import { certificationLabel, distinctionLabel } from "@/lib/format";
import { ScoreBreakdownPanel } from "@/components/score-breakdown";
import { SourceList } from "@/components/source-list";
import { DecisionMakerList } from "@/components/decision-maker-list";
import { StatusBadge } from "@/components/lead-table";

interface Props {
  contractorId: number | null;
  onClose: () => void;
}

const PRIORITY_COLOR: Record<string, string> = {
  high: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300",
  medium: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  low: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
};

export function LeadDetailDrawer({ contractorId, onClose }: Props) {
  const [detail, setDetail] = useState<LeadDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showTechnical, setShowTechnical] = useState(false);

  useEffect(() => {
    if (contractorId === null) return;
    let cancelled = false;
    fetchLeadDetail(contractorId)
      .then((res) => {
        if (cancelled) return;
        setDetail(res);
        setError(null);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [contractorId]);

  if (contractorId === null) return null;

  // Derived rather than effect-set: avoids an extra render pass and keeps
  // "loading" correct even mid-flight when contractorId changes again
  // before the previous fetch resolves.
  const isStale = detail?.contractor.id !== contractorId;
  const loading = isStale && !error;
  const displayError = isStale ? null : error;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <div
        className="h-full w-full max-w-2xl overflow-y-auto bg-white p-6 shadow-xl dark:bg-slate-900"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <button onClick={onClose} className="text-sm text-slate-500 hover:text-slate-800 dark:hover:text-slate-200">
            ← Close
          </button>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={showTechnical} onChange={(e) => setShowTechnical(e.target.checked)} />
            Show scoring detail
          </label>
        </div>

        {loading && <p className="text-sm text-slate-500">Loading contractor detail...</p>}
        {displayError && <p className="text-sm text-red-600">Failed to load contractor: {displayError}</p>}

        {detail && !isStale && (
          <div className="space-y-8">
            <header>
              <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-100">{detail.contractor.name}</h2>
              <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
                {detail.contractor.city ?? "—"}, {detail.contractor.state ?? "—"} ·{" "}
                {detail.contractor.distance_miles !== null ? `${detail.contractor.distance_miles} mi away` : "distance unknown"}
                {detail.contractor.phone && <> · {detail.contractor.phone}</>}
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium dark:bg-slate-800">
                  {certificationLabel(detail.contractor.certification_tier)}
                </span>
                {(detail.contractor.distinctions ?? []).map((d, i) => (
                  <span key={i} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium dark:bg-slate-800">
                    {distinctionLabel(d)}
                  </span>
                ))}
                {detail.contractor.website_url && (
                  <a
                    href={detail.contractor.website_url}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 underline dark:bg-blue-900/30 dark:text-blue-300"
                  >
                    Website
                  </a>
                )}
                {detail.contractor.profile_url && (
                  <a
                    href={detail.contractor.profile_url}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700 underline dark:bg-blue-900/30 dark:text-blue-300"
                  >
                    GAF profile
                  </a>
                )}
              </div>
            </header>

            <section>
              <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">Score</h3>
              <ScoreBreakdownPanel scores={detail.scores} provisional={detail.provisional} showTechnical={showTechnical} />
            </section>

            {detail.contractor.about_text && (
              <section>
                <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">About</h3>
                <p className="text-sm text-slate-700 dark:text-slate-300">{detail.contractor.about_text}</p>
              </section>
            )}

            <section>
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Research</h3>
                <StatusBadge status={detail.research_status} />
              </div>

              {detail.research_status === "pending" && (
                <p className="text-sm text-slate-500">Research has not run for this contractor yet.</p>
              )}
              {detail.research_status === "failed" && (
                <p className="text-sm text-red-600">Research failed: {detail.research_error ?? "unknown error"}</p>
              )}
              {detail.research && (
                <div className="space-y-4">
                  <p className="text-xs text-slate-500">
                    Last researched {new Date(detail.research.researched_at).toLocaleString()} · overall confidence{" "}
                    {detail.research.overall_confidence}
                  </p>
                  <DecisionMakerList items={detail.research.decision_makers} showTechnical={showTechnical} />
                  <SourceList title="Services" items={detail.research.services} showTechnical={showTechnical} />
                  <SourceList title="Service territories" items={detail.research.service_territories} showTechnical={showTechnical} />
                  <SourceList title="Recent projects (18 months)" items={detail.research.recent_projects} showTechnical={showTechnical} />
                  <SourceList title="Growth signals" items={detail.research.growth_signals} showTechnical={showTechnical} />
                  <SourceList title="Public contacts" items={detail.research.public_contacts} showTechnical={showTechnical} />
                  {detail.research.risks_and_unknowns.length > 0 && (
                    <div>
                      <h4 className="mb-1 text-sm font-semibold">Risks and unknowns</h4>
                      <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600 dark:text-slate-400">
                        {detail.research.risks_and_unknowns.map((r, i) => (
                          <li key={i}>{r}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </section>

            <section>
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">AI account-planning insight</h3>
                <StatusBadge status={detail.insight_status} />
              </div>

              {detail.insight_status === "pending" && (
                <p className="text-sm text-slate-500">Insight generation has not run for this contractor yet.</p>
              )}
              {detail.insight_status === "failed" && (
                <p className="text-sm text-red-600">Insight generation failed: {detail.insight_error ?? "unknown error"}</p>
              )}

              {detail.insight && (
                <div className="space-y-4">
                  <div className="flex items-center gap-2">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${PRIORITY_COLOR[detail.insight.ai_priority_label]}`}>
                      AI priority: {detail.insight.ai_priority_label}
                    </span>
                    <span className="text-xs text-slate-500">separate from official score · confidence {detail.insight.insight_confidence}</span>
                  </div>

                  <p className="text-sm text-slate-700 dark:text-slate-300">{detail.insight.account_summary}</p>

                  <div>
                    <h4 className="mb-1 text-sm font-semibold">Why this lead</h4>
                    <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600 dark:text-slate-400">
                      {detail.insight.why_this_lead.map((w, i) => (
                        <li key={i}>
                          {w.text} <span className="text-xs text-slate-400">({showTechnical ? `basis: ${w.basis}` : w.basis === "observed" ? "We found this" : "We think this"})</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div>
                    <h4 className="mb-1 text-sm font-semibold">Potential product fit</h4>
                    <ul className="space-y-1 text-sm text-slate-600 dark:text-slate-400">
                      {detail.insight.potential_product_fit.map((p, i) => (
                        <li key={i}>
                          <span className="font-medium text-slate-800 dark:text-slate-200">{p.category}</span> — {p.reason}{" "}
                          <span className="text-xs text-slate-400">(confidence: {p.confidence})</span>
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div>
                    <h4 className="mb-1 text-sm font-semibold">Why contact now</h4>
                    <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600 dark:text-slate-400">
                      {detail.insight.why_contact_now.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  </div>

                  <div>
                    <h4 className="mb-1 text-sm font-semibold">Decision-makers</h4>
                    <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600 dark:text-slate-400">
                      {detail.insight.decision_makers.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  </div>

                  <div>
                    <h4 className="mb-1 text-sm font-semibold">Outreach angle</h4>
                    <p className="text-sm text-slate-700 dark:text-slate-300">{detail.insight.outreach_angle}</p>
                  </div>

                  <div>
                    <h4 className="mb-1 text-sm font-semibold">Discovery questions</h4>
                    <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600 dark:text-slate-400">
                      {detail.insight.discovery_questions.map((q, i) => (
                        <li key={i}>{q}</li>
                      ))}
                    </ul>
                  </div>

                  <div>
                    <h4 className="mb-1 text-sm font-semibold">Risks and unknowns</h4>
                    <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600 dark:text-slate-400">
                      {detail.insight.risks_and_unknowns.map((r, i) => (
                        <li key={i}>{r}</li>
                      ))}
                    </ul>
                  </div>

                  <div className="rounded-md bg-slate-50 p-3 dark:bg-slate-800">
                    <h4 className="mb-1 text-sm font-semibold">Recommended next action</h4>
                    <p className="text-sm text-slate-700 dark:text-slate-300">{detail.insight.recommended_next_action}</p>
                  </div>
                </div>
              )}
            </section>

            {detail.contractor.last_scraped_at && (
              <p className="text-xs text-slate-400">
                Contractor data last scraped {new Date(detail.contractor.last_scraped_at).toLocaleString()}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
