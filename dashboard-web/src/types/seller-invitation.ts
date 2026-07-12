export type SellerInvitationValidationResponse = {
  valid: true;
  invitation_id: string;
  seller_id: string;
  store_id: string;
  full_name: string;
  email: string;
  store_name: string;
  store_slug: string;
  publication_status: "draft";
  expires_at: string;
};

export type SellerInvitationAcceptResponse = {
  seller_id: string;
  store_id: string;
  account_status: "active";
  publication_status: "draft";
  accepted_at: string;
};
