export type SellerAccountStatus =
  | "invited"
  | "active"
  | "suspended";

export type SellerSetupStatus =
  | "pending"
  | "completed"
  | "cancelled";

export type SellerInvitationStatus =
  | "active"
  | "expired"
  | "accepted"
  | "revoked"
  | "none";

export type AdminSellerStoreSummary = {
  id: string;
  name: string;
  slug: string;
  publication_status: string;
  is_active: boolean;
  is_suspended: boolean;
  plan_name: string;
  subscription_status: string;
  monthly_fee: string | number;
  trial_ends_at: string | null;
  subscription_ends_at: string | null;
  created_at: string;
};

export type AdminSellerInvitationSummary = {
  id: string;
  store_id: string;
  status:
    | "active"
    | "expired"
    | "accepted"
    | "revoked";
  expires_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  created_at: string;
};

export type AdminSellerListItem = {
  seller_id: string;
  full_name: string;
  email: string;
  phone_number: string | null;
  account_status: SellerAccountStatus;
  setup_status: SellerSetupStatus;
  invitation_status: SellerInvitationStatus;
  latest_invitation:
    | AdminSellerInvitationSummary
    | null;
  store_count: number;
  stores: AdminSellerStoreSummary[];
  created_at: string;
  updated_at: string;
};

export type AdminSellerListResponse = {
  items: AdminSellerListItem[];
  next_cursor: string | null;
  has_more: boolean;
};

export type AdminSellerCreateResponse = {
  seller_id: string;
  store_id: string;
  invitation_id: string;
  full_name: string;
  email: string;
  phone_number: string | null;
  store_name: string;
  store_slug: string;
  account_status: "invited";
  publication_status: "draft";
  plan_name: string;
  subscription_status: "trial";
  monthly_fee: string | number;
  trial_ends_at: string;
  invitation_expires_at: string;
  invitation_url: string;
};

export type AdminSellerAccountEventSummary = {
  id: string;
  action: "suspend" | "reactivate";
  previous_account_status:
    | "active"
    | "suspended";
  new_account_status:
    | "active"
    | "suspended";
  reason: string | null;
  actor_user_id: string | null;
  actor_email: string | null;
  created_at: string;
};

export type AdminSellerDetailResponse = {
  seller_id: string;
  full_name: string;
  email: string;
  phone_number: string | null;

  account_status: SellerAccountStatus;
  setup_status: SellerSetupStatus;
  invitation_status: SellerInvitationStatus;

  is_active: boolean;
  is_verified: boolean;
  has_password: boolean;

  latest_invitation:
    | AdminSellerInvitationSummary
    | null;

  invitation_count: number;
  invitations: AdminSellerInvitationSummary[];

  store_count: number;
  stores: AdminSellerStoreSummary[];

  account_event_count: number;
  account_events:
    AdminSellerAccountEventSummary[];

  created_at: string;
  updated_at: string;
};

export type AdminSellerAccountActionResponse = {
  seller_id: string;
  event_id: string;
  account_status: "active" | "suspended";
  is_active: boolean;
  is_verified: boolean;
  updated_at: string;
};

export type AdminSellerInvitationRegenerateResponse = {
  seller_id: string;
  store_id: string;
  invitation_id: string;
  invitation_expires_at: string;
  invitation_url: string;
};

export type AdminSellerOnboardingCancelResponse = {
  seller_id: string;
  invitation_id: string;
  onboarding_status: "cancelled";
  revoked_at: string;
};
