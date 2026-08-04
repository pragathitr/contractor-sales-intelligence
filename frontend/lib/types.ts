export type Confidence = "high" | "medium" | "low";
export type Status = "pending" | "completed" | "failed";
export type PriorityLabel = "high" | "medium" | "low";

export interface EvidenceItem {
  source_url: string;
  source_title: string | null;
  evidence: string;
  published_at: string | null;
  confidence: Confidence;
}

export interface DecisionMakerFinding {
  name: string;
  title: string | null;
  business_email: string | null;
  business_phone: string | null;
  evidence: EvidenceItem[];
}

export interface ResearchOutput {
  company_identity_confirmed: boolean;
  decision_makers: DecisionMakerFinding[];
  services: EvidenceItem[];
  service_territories: EvidenceItem[];
  recent_projects: EvidenceItem[];
  growth_signals: EvidenceItem[];
  product_demand_signals: EvidenceItem[];
  public_contacts: EvidenceItem[];
  risks_and_unknowns: string[];
  overall_confidence: Confidence;
  researched_at: string;
}

export interface WhyThisLead {
  text: string;
  basis: "observed" | "inferred";
}

export interface ProductFit {
  category: string;
  reason: string;
  confidence: Confidence;
  supporting_source_ids: number[];
}

export interface InsightOutput {
  account_summary: string;
  why_this_lead: WhyThisLead[];
  potential_product_fit: ProductFit[];
  why_contact_now: string[];
  decision_makers: string[];
  outreach_angle: string;
  discovery_questions: string[];
  risks_and_unknowns: string[];
  recommended_next_action: string;
  ai_priority_label: PriorityLabel;
  ai_priority_rationale: string;
  insight_confidence: Confidence;
  created_at: string;
  version: number;
}

export interface ScoreBreakdown {
  score_type: string;
  total: number;
  coverage: number;
  breakdown: Record<string, { points: number | null; max_points: number; available: boolean } | Record<string, unknown>>;
  formula_version: string;
  scored_at: string;
}

export interface LeadListItem {
  contractor_id: number;
  name: string;
  lead_priority: number | null;
  account_fit: number | null;
  lead_priority_coverage: number | null;
  certification_tier: string | null;
  rating: number | null;
  review_count: number | null;
  distance_miles: number | null;
  years_in_business: number | null;
  research_status: Status;
  insight_status: Status;
  outreach_angle: string | null;
  provisional: boolean;
}

export interface LeadListResponse {
  items: LeadListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface ContractorDetail {
  id: number;
  gaf_contractor_id: string;
  name: string;
  phone: string | null;
  address: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  zip_code: string | null;
  profile_url: string | null;
  website_url: string | null;
  external_reviews_url: string | null;
  rating: number | null;
  review_count: number | null;
  certification_tier: string | null;
  distinctions: string[] | null;
  about_text: string | null;
  business_start_year: number | null;
  years_in_business: number | null;
  last_scraped_at: string | null;
  distance_miles: number | null;
}

export interface LeadDetailResponse {
  contractor: ContractorDetail;
  scores: ScoreBreakdown[];
  research: ResearchOutput | null;
  research_status: Status;
  research_error: string | null;
  insight: InsightOutput | null;
  insight_status: Status;
  insight_error: string | null;
  provisional: boolean;
}
