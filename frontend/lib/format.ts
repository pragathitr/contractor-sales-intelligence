const CERTIFICATION_LABELS: Record<string, string> = {
  master_elite: "Master Elite",
  certified_plus: "Certified Plus",
  certified: "Certified",
  other_verified: "Other verified",
};

export function certificationLabel(tier: string | null): string {
  if (!tier) return "Unknown";
  return CERTIFICATION_LABELS[tier] ?? tier;
}

export function distinctionLabel(key: string): string {
  return key === "presidents_club" ? "President's Club" : "Other distinction";
}

export function statusLabel(status: string): string {
  return { pending: "Pending", completed: "Complete", failed: "Failed" }[status] ?? status;
}

export function priorityLabel(total: number | null): string {
  if (total === null) return "Unscored";
  if (total >= 70) return "High";
  if (total >= 40) return "Medium";
  return "Low";
}

export function round(n: number | null | undefined, digits = 0): string {
  if (n === null || n === undefined) return "—";
  return n.toFixed(digits);
}
