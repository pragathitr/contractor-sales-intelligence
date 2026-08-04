import { LeadDetailResponse, LeadListResponse } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface LeadListParams {
  search?: string;
  certification?: string;
  minimum_rating?: number;
  sort?: "lead_priority" | "account_fit";
  limit?: number;
  offset?: number;
}

export async function fetchLeads(params: LeadListParams): Promise<LeadListResponse> {
  const query = new URLSearchParams();
  if (params.search) query.set("search", params.search);
  if (params.certification) query.set("certification", params.certification);
  if (params.minimum_rating !== undefined) query.set("minimum_rating", String(params.minimum_rating));
  if (params.sort) query.set("sort", params.sort);
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.offset !== undefined) query.set("offset", String(params.offset));

  const res = await fetch(`${API_BASE}/api/leads?${query.toString()}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch leads: ${res.status}`);
  return res.json();
}

export async function fetchLeadDetail(contractorId: number): Promise<LeadDetailResponse> {
  const res = await fetch(`${API_BASE}/api/leads/${contractorId}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to fetch lead detail: ${res.status}`);
  return res.json();
}
