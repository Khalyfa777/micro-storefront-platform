# StorePlug Roadmap

## Current phase

### Phase 4C - Store Publication and Readiness Workflow

Status: In progress

#### 4C1 ? Contract and decision foundation

- Lock publication state machine
- Lock seller and platform-admin authority
- Lock readiness blockers and warnings
- Document public storefront and ordering behavior
- Document concurrency and audit requirements

#### 4C2 ? Backend publication foundation

- Add store publication event model
- Add Alembic migration
- Add publication schemas
- Add shared readiness service
- Add atomic publication transition service

#### 4C3 ? API and security enforcement

- Add seller readiness endpoint
- Add seller publish and unpublish endpoints
- Add platform-admin readiness endpoint
- Add platform-admin publish and unpublish endpoints
- Add publication history endpoint
- Enforce publication status in public ordering
- Preserve draft-store concealment

#### 4C4 ? Backend verification

- Add readiness tests
- Add publication lifecycle tests
- Add stale-update tests
- Add PostgreSQL concurrency tests
- Verify no account, store-operational, or subscription state cascade

#### 4C5 ? Seller dashboard

- Add publication status card
- Add readiness checklist
- Add publish confirmation
- Add unpublish confirmation
- Add public storefront link only when published
- Support desktop and mobile layouts

#### 4C6 ? Platform-admin workspace

- Add publication state to store summaries
- Add admin readiness review
- Add publish and unpublish actions
- Add reason capture
- Add publication timeline

#### 4C7 ? Final regression

- Backend default suite
- PostgreSQL integration suite
- Alembic verification
- Dashboard lint and build
- Storefront build
- Desktop smoke test
- Mobile smoke test
- Merge-readiness audit

## Deployment

No Phase 4C deployment will occur until local implementation,
automated verification, desktop review, and mobile review are complete.
