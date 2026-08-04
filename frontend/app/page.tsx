"use client";

import { useEffect, useState } from "react";
import { fetchLeads, LeadListParams } from "@/lib/api";
import { LeadListItem } from "@/lib/types";
import { LeadFilters } from "@/components/lead-filters";
import { LeadTable } from "@/components/lead-table";
import { LeadDetailDrawer } from "@/components/lead-detail-drawer";

export default function Home() {
  const [params, setParams] = useState<LeadListParams>({ sort: "lead_priority", limit: 100 });
  const [items, setItems] = useState<LeadListItem[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchLeads(params)
      .then((res) => {
        if (cancelled) return;
        setItems(res.items);
        setTotal(res.total);
        setError(null);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [params]);

  return (
    <div className="mx-auto w-full max-w-7xl flex-1 px-6 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">Roofing Sales Intelligence</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400">
          Contractors within 25 miles of ZIP 10013, ranked by deterministic Lead Priority.
        </p>
      </header>

      <div className="mb-4">
        <LeadFilters value={params} onChange={setParams} />
      </div>

      {loading && <p className="text-sm text-slate-500">Loading leads...</p>}
      {error && (
        <p className="rounded-md bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-300">
          Failed to load leads: {error}. Is the backend running at {process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}?
        </p>
      )}
      {!loading && !error && total === 0 && (
        <div className="rounded-lg border border-dashed border-slate-300 p-12 text-center text-slate-500 dark:border-slate-700">
          No contractors have been ingested yet. Run a fixture seed or an ingestion pass to populate the dashboard.
        </div>
      )}
      {!loading && !error && total !== null && total > 0 && (
        <>
          <p className="mb-2 text-xs text-slate-500">{total} leads</p>
          <LeadTable items={items} onSelect={setSelectedId} />
        </>
      )}

      <LeadDetailDrawer contractorId={selectedId} onClose={() => setSelectedId(null)} />
    </div>
  );
}
