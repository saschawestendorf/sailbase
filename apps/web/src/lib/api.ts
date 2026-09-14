/**
 * Server-side API access.
 *
 * The browser never talks to the backend directly: `/api/*` is proxied by a route handler
 * (see src/app/api/[...path]/route.ts). That keeps the backend URL a runtime server setting,
 * so the same container image works in every environment.
 */

export const API_BASE_URL =
  process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

type Query = Record<string, string | number | boolean | string[] | undefined | null>;

export function toQuery(params: Query): string {
  const sp = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => v && sp.append(key, String(v)));
    else sp.set(key, String(value));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit & { revalidate?: number } = {},
): Promise<T> {
  const { revalidate, ...rest } = init;
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...rest,
      headers: { "Content-Type": "application/json", ...(rest.headers ?? {}) },
      cache: revalidate === undefined ? "no-store" : undefined,
      next: revalidate === undefined ? undefined : { revalidate },
    });
  } catch {
    throw new ApiError(503, "Der Buchungsdienst ist gerade nicht erreichbar.");
  }
  if (!res.ok) {
    let detail = `Fehler ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (Array.isArray(body?.detail) && body.detail[0]?.msg) detail = body.detail[0].msg;
    } catch {
      /* keep the generic message */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ----------------------------------------------------------------- domain types

export type Region = {
  id: string;
  slug: string;
  name: string;
  country: string;
  description: string;
};

export type Base = {
  id: string;
  name: string;
  city: string;
  lat: number | null;
  lon: number | null;
  region: Region;
};

export type BoatClass = {
  id: string;
  slug: string;
  name: string;
  min_length_m: number;
  max_length_m: number;
};

export type Boat = {
  id: string;
  slug: string;
  name: string;
  manufacturer: string;
  model: string;
  year_built: number | null;
  year_refit: number | null;
  listing_mode: string;
  length_m: number;
  beam_m: number | null;
  draft_m: number | null;
  sail_area_m2: number | null;
  engine_hp: number | null;
  cabins: number;
  berths: number;
  max_persons: number;
  heads: number;
  headroom_cm: number | null;
  max_berth_length_cm: number | null;
  character: string[];
  required_license: number;
  required_experience_nm: number;
  features: string[];
  description: string;
  images: string[];
  min_days: number;
  max_days: number;
  allowed_nights: number[];
  min_lead_days: number;
  turnaround_days: number;
  changeover_weekdays: number[];
  handover_options: string[];
  one_way_enabled: boolean;
  one_way_base_ids: string[];
  one_way_fee_cents: number;
  deposit_cents: number;
  cleaning_fee_cents: number;
  region_restrictions: string;
  base: Base;
  boat_class: BoatClass;
  charterer: { id: string; name: string; slug: string; rating: number | null };
  rating_overall: number | null;
  rating_count: number;
};

export type PricingPolicy = {
  mode: string;
  currency: string;
  reference_price_cents: number;
  floor_price_cents: number;
  ceiling_price_cents: number;
  target_price_cents: number | null;
  strategy: string;
  max_dead_gap_days: number | null;
};

export type BoatImage = {
  id: string;
  url: string;
  origin: "model" | "owner" | "guest";
  caption: string;
  charter_month: string;
  taken_on: string | null;
  credit: string;
  created_at: string;
};

export type RatingSummary = {
  count: number;
  overall: number | null;
  model: number | null;
  condition: number | null;
  service: number | null;
  details: Record<string, number | null>;
};

export type Review = {
  id: string;
  boat_id: string;
  author_name: string;
  charter_month: string;
  rating_model: number | null;
  rating_condition: number | null;
  rating_service: number | null;
  rating_care: number | null;
  rating_cleanliness: number | null;
  rating_accuracy: number | null;
  rating_equipment: number | null;
  rating_organisation: number | null;
  rating_handover: number | null;
  overall: number | null;
  title: string;
  body: string;
  published_at: string | null;
  photos: string[];
};

export type ReviewEligibility = {
  may_review: boolean;
  reason: string;
  existing: Review | null;
};

export type BoatDetail = Boat & {
  pricing: PricingPolicy | null;
  model_version_id: string | null;
  variant_ids: string[];
  spec_overrides: Record<string, number | null>;
  spec_sources: Record<string, string>;
  unknown_specs: string[];
  gallery: BoatImage[];
  ratings: RatingSummary | null;
  model_info: Record<string, string | number | null>;
};

// ------------------------------------------------------------- master catalog

export type Manufacturer = { id: string; slug: string; name: string; country: string };

export type Variant = {
  id: string;
  kind: "layout" | "keel" | "rig" | "engine";
  code: string;
  name: string;
  is_default: boolean;
  draft_m: number | null;
  sail_area_m2: number | null;
  engine_hp: number | null;
  cabins: number | null;
  berths: number | null;
  heads: number | null;
  max_persons: number | null;
  headroom_cm: number | null;
  max_berth_length_cm: number | null;
  adds_features: string[];
};

export type ModelVersion = {
  id: string;
  name: string;
  year_from: number | null;
  year_to: number | null;
  length_m: number;
  beam_m: number | null;
  draft_m: number | null;
  displacement_kg: number | null;
  sail_area_m2: number | null;
  engine_hp: number | null;
  headroom_cm: number | null;
  max_berth_length_cm: number | null;
  cabins: number | null;
  berths: number | null;
  heads: number | null;
  max_persons: number | null;
  water_tank_l: number | null;
  fuel_tank_l: number | null;
  character: string[];
  standard_features: string[];
  description: string;
  model_images: string[];
  source: string;
  source_url: string;
  verified_on: string | null;
  revision: number;
  caveat: string;
  variants: Variant[];
};

export type CatalogModel = {
  id: string;
  slug: string;
  name: string;
  designer: string;
  hull_type: string;
  manufacturer: Manufacturer;
};

export type CatalogModelDetail = CatalogModel & { versions: ModelVersion[] };

export type ResolvedSpec = {
  values: Record<string, number | null>;
  features: string[];
  character: string[];
  sources: Record<string, string>;
  unknown: string[];
};

// --------------------------------------------------------- revenue simulation

export type MonthPoint = {
  month: number;
  label: string;
  available_days: number;
  booked_days: number;
  occupancy: number;
  avg_price_cents: number;
  revenue_cents: number;
  revpabd_cents: number;
};

export type SimulationRun = {
  label: string;
  available_days: number;
  booked_days: number;
  occupancy: number;
  revenue_cents: number;
  revpabd_cents: number;
  avg_price_cents: number;
  months: MonthPoint[];
};

export type Simulation = {
  dynamic: SimulationRun;
  static: SimulationRun;
  uplift_cents: number;
  uplift_percent: number;
  assumptions: Record<string, unknown>;
};

export type ChartererStats = {
  boats: number;
  bookings_confirmed: number;
  bookings_pending: number;
  bookings_settled: number;
  charter_nights: number;
  revenue_cents: number;
  static_revenue_cents: number;
  dynamic_uplift_cents: number;
  avg_price_per_night_cents: number;
  commission_cents: number;
  service_cost_cents: number;
  payouts_pending_cents: number;
  occupancy_next_90d: number;
  gaps_next_90d: {
    boat_id: string;
    boat_name: string;
    start_date: string;
    end_date: string;
    nights: number;
    sellable: boolean;
  }[];
};

export type FactorLine = { key: string; label: string; multiplier: number; detail: string };
export type FeeLine = { key: string; label: string; amount_cents: number; detail: string };

export type Breakdown = {
  currency: string;
  nights: number;
  reference_per_day_cents: number;
  raw_per_day_cents: number;
  per_day_cents: number;
  charter_cents: number;
  fees_cents: number;
  total_cents: number;
  clamped: string | null;
  day_factors: FactorLine[];
  stay_factors: FactorLine[];
  fee_lines: FeeLine[];
  occupancy?: number;
  gap?: Record<string, unknown>;
};

export type Offer = {
  start_date: string;
  end_date: string;
  nights: number;
  per_day_cents: number;
  total_cents: number;
  breakdown: Breakdown;
  gap: Record<string, unknown>;
  note: string;
  pickup_base_id: string | null;
  dropoff_base_id: string | null;
};

export type SearchHit = {
  boat: Boat;
  available: boolean;
  unavailable_reason: string;
  total_cents: number | null;
  per_day_cents: number | null;
  offers: Offer[];
  fit_score: number;
  fit_reasons: string[];
  blockers: string[];
  breakdown: Breakdown | Record<string, never>;
};

export type SearchResult = { count: number; hits: SearchHit[] };

export type CalendarDay = {
  date: string;
  available: boolean;
  per_day_cents: number | null;
  total_cents: number | null;
  reason: string;
};

export type CalendarResult = { boat_id: string; nights: number; days: CalendarDay[] };

export type Quote = {
  id: string;
  boat_id: string;
  start_date: string;
  end_date: string;
  persons: number;
  pickup_base_id: string | null;
  dropoff_base_id: string | null;
  currency: string;
  total_cents: number;
  deposit_cents: number;
  breakdown: Breakdown;
  expires_at: string;
};

export type Payment = {
  id: string;
  provider: string;
  purpose: string;
  amount_cents: number;
  currency: string;
  status: string;
  due_at: string | null;
  checkout_url: string;
};

export type Booking = {
  id: string;
  reference: string;
  boat_id: string;
  customer_email: string;
  customer_name: string;
  persons: number;
  start_date: string;
  end_date: string;
  pickup_base_id: string | null;
  dropoff_base_id: string | null;
  status: string;
  currency: string;
  total_cents: number;
  deposit_cents: number;
  security_deposit_cents: number;
  balance_due_at: string | null;
  price_breakdown: Breakdown;
  hold_expires_at: string | null;
  created_at: string;
  payments: Payment[];
  boat: Boat | null;
};

export type BookingCreated = { booking: Booking; checkout_url: string };

export type ChecklistItem = {
  key: string;
  label: string;
  required: boolean;
  photo_required: boolean;
  done: boolean;
  issue: boolean;
  note: string;
  photos: string[];
};

export type ServiceOrder = {
  id: string;
  booking_id: string;
  boat_id: string;
  partner_id: string | null;
  order_type: string;
  status: string;
  scheduled_for: string | null;
  checklist: ChecklistItem[];
  photos: string[];
  notes: string;
  price_cents: number;
  completed_at: string | null;
  partner: { id: string; name: string; phone: string } | null;
  boat_name: string | null;
  base_name: string | null;
  booking_reference: string | null;
  booking_start: string | null;
  booking_end: string | null;
  customer_name: string | null;
};

export type Damage = {
  id: string;
  booking_id: string;
  title: string;
  description: string;
  photos: string[];
  estimated_cents: number;
  withheld_cents: number;
  status: string;
  created_at: string;
};

export type Payout = {
  id: string;
  booking_id: string;
  gross_cents: number;
  commission_cents: number;
  service_cost_cents: number;
  damage_withheld_cents: number;
  net_cents: number;
  status: string;
  paid_at: string | null;
};

export type Partner = {
  id: string;
  name: string;
  phone: string;
  base_ids: string[];
  services: string[];
  prices: Record<string, number>;
  rating: number | null;
};

export type BookingOps = {
  orders: ServiceOrder[];
  damages: Damage[];
  payout: Payout | null;
  contract: { version?: string; text_md?: string; hash?: string };
  contract_accepted_customer_at: string | null;
  contract_accepted_charterer_at: string | null;
  handover_confirmed_customer_at: string | null;
  return_confirmed_customer_at: string | null;
  crew_list: { name: string; role?: string }[];
  documents: { type: string; name: string; url: string }[];
};

// ------------------------------------------------------------------- endpoints

export const getRegions = () => apiFetch<Region[]>("/regions", { revalidate: 300 });
export const getBases = () => apiFetch<Base[]>("/bases", { revalidate: 300 });
export const getBoatClasses = () => apiFetch<BoatClass[]>("/boat-classes", { revalidate: 300 });
export const getBoat = (slug: string) => apiFetch<BoatDetail>(`/boats/${encodeURIComponent(slug)}`);

export const getCalendar = (slug: string, params: Query) =>
  apiFetch<CalendarResult>(`/boats/${encodeURIComponent(slug)}/calendar${toQuery(params)}`);

export const searchBoats = (params: Query) =>
  apiFetch<SearchResult>(`/search${toQuery(params)}`);

export const getBooking = (reference: string, email: string) =>
  apiFetch<Booking>(`/bookings/${encodeURIComponent(reference)}${toQuery({ email })}`);

export const getBookingOps = (reference: string, email: string) =>
  apiFetch<BookingOps>(`/bookings/${encodeURIComponent(reference)}/ops${toQuery({ email })}`);

export const getBoatReviews = (slug: string) =>
  apiFetch<{ summary: RatingSummary; reviews: Review[] }>(
    `/boats/${encodeURIComponent(slug)}/reviews`,
  );

export const getReviewEligibility = (reference: string, email: string) =>
  apiFetch<ReviewEligibility>(
    `/bookings/${encodeURIComponent(reference)}/review${toQuery({ email })}`,
  );

// --- catalog
export const getCatalogModels = (params: Query = {}) =>
  apiFetch<CatalogModel[]>(`/catalog/models${toQuery(params)}`, { revalidate: 300 });

export const getCatalogModel = (id: string) =>
  apiFetch<CatalogModelDetail>(`/catalog/models/${encodeURIComponent(id)}`, { revalidate: 300 });

export const getManufacturers = () =>
  apiFetch<Manufacturer[]>("/catalog/manufacturers", { revalidate: 300 });

// --- authenticated calls made from server components
export function authed(token: string): RequestInit {
  return { headers: { Authorization: `Bearer ${token}` } };
}

export const getMyBoats = (token: string) =>
  apiFetch<BoatDetail[]>("/charterer/boats", authed(token));

export const getMyStats = (token: string) =>
  apiFetch<ChartererStats>("/charterer/stats", authed(token));

export const getMyBookings = (token: string) =>
  apiFetch<Booking[]>("/charterer/bookings", authed(token));

export const getMyOrders = (token: string) =>
  apiFetch<ServiceOrder[]>("/charterer/orders", authed(token));

export const getPartners = (token: string, baseId?: string) =>
  apiFetch<Partner[]>(`/charterer/partners${toQuery({ base_id: baseId })}`, authed(token));

export const getChartererBookingOps = (token: string, bookingId: string) =>
  apiFetch<BookingOps>(`/charterer/bookings/${encodeURIComponent(bookingId)}/ops`, authed(token));

export const getChartererPayments = (token: string, bookingId: string) =>
  apiFetch<Payment[]>(
    `/charterer/bookings/${encodeURIComponent(bookingId)}/payments`,
    authed(token),
  );
