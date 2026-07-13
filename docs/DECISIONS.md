# StorePlug Product Decisions

## Phase 4C - Store Publication Workflow

### Publication state

Store publication has exactly two states:

- `draft`
- `published`

New stores always begin as `draft`. Unpublishing a store returns it
to `draft`.

No additional approval, rejection, archived, or pending states are
introduced in Phase 4C.

### Separation of concerns

Publication status is independent from:

- Seller account status
- Seller onboarding status
- Store operational status
- Store suspension
- Subscription status
- Product activation

Publishing or unpublishing a store must not automatically change:

- `users.is_active`
- `stores.is_active`
- `stores.is_suspended`
- `stores.subscription_status`
- `stores.plan_name`

Subscription renewal must not automatically publish a store.

Subscription expiry or store suspension must not automatically change
`publication_status`. A published store may remain published while
temporarily unavailable and resume availability when its subscription
or operational state is restored.

### Seller publication authority

A seller may publish their own store only when:

1. Seller onboarding setup is complete.
2. The store is operationally active.
3. The store is not suspended.
4. The subscription is active and unexpired.
5. At least one active product exists.
6. The store has a valid name and slug.

A seller cannot self-publish while on the free trial.

A seller may unpublish their own store while they retain dashboard
access.

### Platform-admin publication authority

A platform admin may publish a store when:

1. Seller onboarding setup is complete.
2. The store is operationally active.
3. The store is not suspended.
4. The store has at least one active product.
5. The subscription is active and unexpired, or the store has a
   deliberately approved and still-valid trial.

Platform admins may unpublish any store.

Platform admins must not silently bypass expired subscriptions,
expired trials, operational suspension, incomplete onboarding, or the
absence of active products.

### Readiness severity

Publication readiness returns blockers and warnings.

Blockers prevent publication:

- Incomplete onboarding
- Operationally inactive store
- Suspended store
- Invalid or expired subscription
- No active products
- Missing required store identity fields

Warnings do not prevent publication:

- Missing logo
- Missing banner
- Missing bio
- Missing category
- Missing WhatsApp number

### Public behavior

Draft stores must return `404 Store not found` from public storefront
and ordering endpoints.

Published stores are publicly accessible only when their operational
and subscription conditions allow access.

A published but temporarily unavailable store may return a generic
unavailable response without changing publication status.

Public ordering must enforce the same publication requirement as the
public storefront.

### Concurrency

Publish and unpublish operations must:

- Lock the store row
- Require the caller's `expected_updated_at`
- Reject stale transitions with HTTP `409`
- Commit the state change and audit event atomically

### Publication history

Every successful publication transition creates one append-only event
containing:

- Store ID
- Actor user ID
- Actor role snapshot
- Action
- Previous publication status
- New publication status
- Optional reason
- Readiness snapshot
- Creation timestamp

Failed or stale publication attempts must not create events.
