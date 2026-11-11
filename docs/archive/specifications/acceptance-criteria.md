> Historical record. This document describes an earlier design or implementation;
> use the [current documentation](../../README.md) and [installation guide](../../../INSTALL.md) for current behaviour.

# Acceptance criteria

These criteria are a future verification plan updated for [owner decisions](owner-decisions.md). Nothing is marked as executed. Expected defaults require owner confirmation. Each criterion uses the source requirement verbatim through the requirement catalogue.

Environment baseline: synthetic data, no production credentials, test mail sink and separate runtime identities. A real Instagram smoke test requires approved account access.

## AC-001 UI-001

Related requirement: UI-001 — Header and menu.

Preconditions: Staging public routes, configured shared content and synthetic image/video assets are available.

Action: Save a new site identity and open all public routes.

Expected result: All three destinations work on desktop/mobile and identity updates without source edits.

Failure behaviour: Invalid markup rejected and old header retained.

Verification method: Browser E2E.

## AC-002 UI-002

Related requirement: UI-002 — Presentation/body area.

Preconditions: Staging public routes, configured shared content and synthetic image/video assets are available.

Action: Open Feed, Contact and Reviews.

Expected result: Each has its specified body plus shared shell.

Failure behaviour: Unknown route returns localised 404.

Verification method: Browser E2E.

## AC-003 UI-003

Related requirement: UI-003 — Footer.

Preconditions: Staging public routes, configured shared content and synthetic image/video assets are available.

Action: Edit footer and visit each public page.

Expected result: All pages show saved sanitised footer and links.

Failure behaviour: Failed save leaves previous revision.

Verification method: Browser E2E.

## AC-004 UI-004

Related requirement: UI-004 — Responsive behaviour.

Preconditions: Staging public routes, configured shared content and synthetic image/video assets are available.

Action: View pages at 320/768/1440 CSS pixels and 200% zoom.

Expected result: No horizontal page overflow; media remains within column with preserved ratio.

Failure behaviour: Missing media uses bounded fallback.

Verification method: Browser/manual.

## AC-005 UI-005

Related requirement: UI-005 — Accessibility.

Preconditions: Staging public routes, configured shared content and synthetic image/video assets are available.

Action: Navigate forms/media/locale by keyboard and screen reader.

Expected result: Focus and labels exposed; images have alt support; video controls/caption tracks available when provided.

Failure behaviour: Missing optional track does not break controls; essential alt missing blocks publication unless decorative.

Verification method: Accessibility/manual.

## AC-006 FEED-001

Related requirement: FEED-001 — Database-fed list.

Preconditions: Staging database has mixed statuses, dates, 25 eligible items and image/video fixtures; public runtime uses its actual restricted DB role.

Action: Query mixed dated/prioritised published fixtures twice.

Expected result: Stable date/ID ordering and no repeated page entries on unchanged data.

Failure behaviour: Invalid cursor rejected; no unbounded query.

Verification method: DB/browser.

## AC-007 FEED-002

Related requirement: FEED-002 — Instagram-style card.

Preconditions: Staging database has mixed statuses, dates, 25 eligible items and image/video fixtures; public runtime uses its actual restricted DB role.

Action: Render image and video/poster fixtures.

Expected result: Media appears above caption; source is clear without misleading branding.

Failure behaviour: Absent asset shows accessible fallback.

Verification method: Browser E2E.

## AC-008 FEED-003

Related requirement: FEED-003 — Source click-through.

Preconditions: Staging database has mixed statuses, dates, 25 eligible items and image/video fixtures; public runtime uses its actual restricted DB role.

Action: Activate source link beside embed and linked image/poster for local media.

Expected result: Visible source link opens correct Instagram URL in new tab with security attributes; provider embed/video controls remain usable.

Failure behaviour: Unsafe URL rejected; blocked embed shows source link and any available validated local fallback.

Verification method: Browser/security.

## AC-009 FEED-004

Related requirement: FEED-004 — Media types.

Preconditions: Staging database has mixed statuses, dates, 25 eligible items and image/video fixtures; public runtime uses its actual restricted DB role.

Action: Render supported image/video embeds then make embedding unavailable with permitted local fixtures.

Expected result: Official embed preferred; validated local image/video used when embedding unavailable; original caption retained separately.

Failure behaviour: No arbitrary provider HTML executes; unavailable media without usable fallback yields safe link/Error state, never corrupt old content.

Verification method: Browser/integration.

## AC-010 FEED-005

Related requirement: FEED-005 — Text rendering.

Preconditions: Staging database has mixed statuses, dates, 25 eligible items and image/video fixtures; public runtime uses its actual restricted DB role.

Action: Render multiline long caption, safe URL and script payload.

Expected result: Paragraphs preserved, safe links work, script inert; read-more if enabled is keyboard accessible.

Failure behaviour: Unsafe markup cannot execute.

Verification method: Unit/browser security.

## AC-011 FEED-006

Related requirement: FEED-006 — Pagination.

Preconditions: Staging database has mixed statuses, dates, 25 eligible items and image/video fixtures; public runtime uses its actual restricted DB role.

Action: Load 25 eligible items with page size 12.

Expected result: First two pages have 12 items and third 1; max request size capped.

Failure behaviour: Invalid size/cursor rejected, never fetch all records.

Verification method: DB/integration.

## AC-012 FEED-007

Related requirement: FEED-007 — Publication control.

Preconditions: Staging database has mixed statuses, dates, 25 eligible items and image/video fixtures; public runtime uses its actual restricted DB role.

Action: Query all statuses and future/scheduled records, then hide an item.

Expected result: Only eligible Published records visible; valid new imports publish automatically; hidden item/media unavailable on next request.

Failure behaviour: DB identity cannot query excluded base rows.

Verification method: DB/security/browser.

## AC-013 FEED-008

Related requirement: FEED-008 — Empty/error state.

Preconditions: Staging database has mixed statuses, dates, 25 eligible items and image/video fixtures; public runtime uses its actual restricted DB role.

Action: View empty feed then disconnect DB.

Expected result: Configured translated empty message for empty data; generic 503 on DB failure with diagnostic reference.

Failure behaviour: No stack/credentials exposed.

Verification method: Integration/browser.

## AC-014 CON-001

Related requirement: CON-001 — Submission delivery.

Preconditions: Staging contact form uses a test mail adapter; EN/FR are enabled and no real visitor information is used.

Action: Send valid contact fixture to test mail service.

Expected result: Provider accepts configured recipient, controlled From and visitor Reply-To.

Failure behaviour: Reject CR/LF and invalid input; no send.

Verification method: Mail integration.

## AC-015 CON-002

Related requirement: CON-002 — Confirmation.

Preconditions: Staging contact form uses a test mail adapter; EN/FR are enabled and no real visitor information is used.

Action: Submit valid EN then FR messages.

Expected result: Success shown only after acceptance, in active language, without recipient disclosure.

Failure behaviour: Failure or Unknown never shows accepted.

Verification method: Browser/mail.

## AC-016 CON-003

Related requirement: CON-003 — Abuse prevention.

Preconditions: Staging contact form uses a test mail adapter; EN/FR are enabled and no real visitor information is used.

Action: Submit forged origin, bot field and requests beyond limit.

Expected result: Forged/bot requests do not send; exceeded limit returns 429.

Failure behaviour: No provider call on rejected requests.

Verification method: Security/integration.

## AC-017 CON-004

Related requirement: CON-004 — Failure handling.

Preconditions: Staging contact form uses a test mail adapter; EN/FR are enabled and no real visitor information is used.

Action: Simulate mail rejection and ambiguous timeout.

Expected result: Safe Failed/Unknown metadata retained and neutral guidance displayed.

Failure behaviour: No message body/email/phone logged or persisted; no blind duplicate retry.

Verification method: Mail/fault integration.

## AC-018 CON-005

Related requirement: CON-005 — Privacy.

Preconditions: Staging contact form uses a test mail adapter; EN/FR are enabled and no real visitor information is used.

Action: Open contact page in both locales.

Expected result: Visible localised privacy notice or link explains use and retention.

Failure behaviour: Missing required owner text blocks production contact launch.

Verification method: Browser/UAT.

## AC-019 REV-001

Related requirement: REV-001 — Review list.

Preconditions: Staging has two published reviews, one hidden and one future-dated review; authorised admin and visitor contexts are available.

Action: Render approved and unpublished review fixtures.

Expected result: Only approved eligible records show name/text/date and optional rating/source.

Failure behaviour: Missing optional rating/source does not break layout.

Verification method: DB/browser.

## AC-020 REV-002

Related requirement: REV-002 — Management.

Preconditions: Staging has two published reviews, one hidden and one future-dated review; authorised admin and visitor contexts are available.

Action: Create, edit, publish, hide and reorder two reviews.

Expected result: Changes appear in eligible public order with actor audit.

Failure behaviour: Unauthorised/stale edits denied without loss.

Verification method: Browser/DB.

## AC-021 REV-003

Related requirement: REV-003 — Future submission option.

Preconditions: Staging has two published reviews, one hidden and one future-dated review; authorised admin and visitor contexts are available.

Action: Probe public review submission routes.

Expected result: No public review creation or automatic moderation bypass exists.

Failure behaviour: Write attempt denied and no new record.

Verification method: Security/route audit.

## AC-022 ADM-001

Related requirement: ADM-001 — Authentication.

Preconditions: One named Owner and anonymous contexts are available on isolated staging with audit, media and settings fixtures.

Action: Login, expire idle/absolute session, logout and disable account.

Expected result: Password hash only; secure HttpOnly SameSite cookie; expired/revoked sessions rejected.

Failure behaviour: Generic login failure and throttling; anonymous actions denied.

Verification method: Auth integration/security.

## AC-023 ADM-002

Related requirement: ADM-002 — Menu section editor.

Preconditions: One named Owner and anonymous contexts are available on isolated staging with audit, media and settings fixtures.

Action: Save safe header then script/event/iframe/unsafe URL payloads.

Expected result: Safe content persists; dangerous content removed or rejected with feedback.

Failure behaviour: Old valid header remains on rejection; no execution in preview.

Verification method: Unit/browser security.

## AC-024 ADM-003

Related requirement: ADM-003 — Theme editor.

Preconditions: One named Owner and anonymous contexts are available on isolated staging with audit, media and settings fixtures.

Action: Preview/save raster background, valid colours and approved font.

Expected result: Preview and public pages match saved valid theme.

Failure behaviour: Invalid font/colour/contrast/file rejected without changing live theme.

Verification method: Browser/security.

## AC-025 ADM-004

Related requirement: ADM-004 — Database search.

Preconditions: One named Owner and anonymous contexts are available on isolated staging with audit, media and settings fixtures.

Action: Search by caption, source ID, URL, status and date interval.

Expected result: Matching records returned with pagination and bounded page size.

Failure behaviour: Bad range/query rejected; no SQL interpolation.

Verification method: DB/browser.

## AC-026 ADM-005

Related requirement: ADM-005 — Database editing.

Preconditions: One named Owner and anonymous contexts are available on isolated staging with audit, media and settings fixtures.

Action: Edit original-language display override and metadata, then reimport changed source.

Expected result: Original-language override retained; source snapshots auditable; no locale changes or automatic translation of post language.

Failure behaviour: Stale version returns conflict; unsafe URL/media refused.

Verification method: DB/replay/browser.

## AC-027 ADM-006

Related requirement: ADM-006 — Footer editor.

Preconditions: One named Owner and anonymous contexts are available on isolated staging with audit, media and settings fixtures.

Action: Save bilingual footer with safe links and attack payloads.

Expected result: Valid locale footer persists and scripts/events/iframes are inert.

Failure behaviour: Invalid save preserves previous revision.

Verification method: Unit/browser security.

## AC-028 ADM-007

Related requirement: ADM-007 — Contact recipient.

Preconditions: One named Owner and anonymous contexts are available on isolated staging with audit, media and settings fixtures.

Action: Change recipient after reauthentication and test selected activation policy.

Expected result: Valid active revision routes next contact message to new recipient.

Failure behaviour: Invalid address rejected; old recipient remains active.

Verification method: Mail/browser integration.

## AC-029 ADM-008

Related requirement: ADM-008 — Language mode.

Preconditions: One named Owner and anonymous contexts are available on isolated staging with audit, media and settings fixtures.

Action: Set default/enabled locales and edit fixed text resources.

Expected result: Pages use saved translations/default; only enabled choices shown.

Failure behaviour: Cannot disable every locale or default without valid replacement.

Verification method: Unit/browser.

## AC-030 ADM-009

Related requirement: ADM-009 — Audit trail.

Preconditions: One named Owner and anonymous contexts are available on isolated staging with audit, media and settings fixtures.

Action: Edit content/settings and force audit write failure.

Expected result: Successful edits record actor/time/entity/action/safe fields; failed audit rolls back edit.

Failure behaviour: No sensitive field values logged.

Verification method: DB/security.

## AC-031 ADM-010

Related requirement: ADM-010 — Safe media upload.

Preconditions: One named Owner and anonymous contexts are available on isolated staging with audit, media and settings fixtures.

Action: Upload valid raster and fake MIME/executable/oversized/traversal fixtures.

Expected result: Only validated bounded files receive generated private keys outside executable tree.

Failure behaviour: Rejected files never publish; previous asset intact.

Verification method: Media/security.

## AC-032 L10N-001

Related requirement: L10N-001 — Language switch.

Preconditions: Both locales are enabled with complete packaged labels, partial content translations and a fresh browser context.

Action: Switch EN/FR, navigate and revisit, then simulate first visit.

Expected result: Enabled choice persists; first visit uses accepted enabled browser locale or default.

Failure behaviour: Disabled/invalid locale safely falls back.

Verification method: Browser/integration.

## AC-033 L10N-002

Related requirement: L10N-002 — Interface resources.

Preconditions: Both locales are enabled with complete packaged labels, partial content translations and a fresh browser context.

Action: Trigger labels, errors, validation, success and accessibility text in both locales.

Expected result: All fixed strings resolve through translation resources.

Failure behaviour: Missing override falls back to packaged string.

Verification method: Unit/browser.

## AC-034 L10N-003

Related requirement: L10N-003 — Content fields.

Preconditions: Both locales are enabled with complete packaged labels, partial content translations and a fresh browser context.

Action: Blank one locale in site copy/reviews and switch locale with an imported post present.

Expected result: Defined site-copy/review fallback appears; imported caption remains in original language on both locales.

Failure behaviour: Empty both mandatory texts rejected.

Verification method: Unit/browser.

## AC-035 L10N-004

Related requirement: L10N-004 — Imported posts.

Preconditions: Both locales are enabled with complete packaged labels, partial content translations and a fresh browser context.

Action: Import original caption, change site locale, then reimport an edited source caption.

Expected result: Original-source revisions retained; active post text stays in source language across locales; no caption translation generated.

Failure behaviour: No automatic translation or comment/message request; source/display overrides are not overwritten silently.

Verification method: Replay/DB.

## AC-036 L10N-005

Related requirement: L10N-005 — URLs and metadata.

Preconditions: Both locales are enabled with complete packaged labels, partial content translations and a fresh browser context.

Action: Inspect each locale page and sitemap.

Expected result: Correct lang, canonical and alternate language metadata; no admin/draft URLs.

Failure behaviour: Invalid locales do not create duplicate indexed content.

Verification method: HTML/browser.

## AC-037 AGT-001

Related requirement: AGT-001 — Credential entry.

Preconditions: Isolated agent test runtime uses synthetic tokens and controlled API/media fixtures; real account proof uses separately authorised staging access.

Action: Complete authorised Instagram consent and provision/rotate synthetic token through isolated agent-side flow.

Expected result: State/redirect/code validated; account checked; active token encrypted outside web runtime.

Failure behaviour: No password collected; no token in argv/log/website; failed rotation preserves old version.

Verification method: Security/contract.

## AC-038 AGT-002

Related requirement: AGT-002 — Encryption.

Preconditions: Isolated agent test runtime uses synthetic tokens and controlled API/media fixtures; real account proof uses separately authorised staging access.

Action: Inspect secret file, backup, app DB and logs after provisioning.

Expected result: No plaintext credential; decrypt key outside ciphertext and inaccessible to web.

Failure behaviour: Missing key fails closed without leaking value.

Verification method: Filesystem/security.

## AC-039 AGT-003

Related requirement: AGT-003 — Validation.

Preconditions: Isolated agent test runtime uses synthetic tokens and controlled API/media fixtures; real account proof uses separately authorised staging access.

Action: Validate good, expired and wrong-account tokens.

Expected result: Only expected account passes; output shows status/reference only.

Failure behaviour: Invalid material not activated; no raw provider response.

Verification method: Contract/security.

## AC-040 AGT-004

Related requirement: AGT-004 — Restricted retrieval.

Preconditions: Isolated agent test runtime uses synthetic tokens and controlled API/media fixtures; real account proof uses separately authorised staging access.

Action: Attempt retrieval as public/admin and as ingestion identity.

Expected result: Only ingestion runtime decrypts for required API operation in memory.

Failure behaviour: All web reads/decrypt attempts denied.

Verification method: Runtime identity/security.

## AC-041 AGT-005

Related requirement: AGT-005 — No export.

Preconditions: Isolated agent test runtime uses synthetic tokens and controlled API/media fixtures; real account proof uses separately authorised staging access.

Action: Inspect/help/probe every credential operation.

Expected result: No plaintext credential export or print function.

Failure behaviour: Unknown/export requests denied and redacted.

Verification method: Security/manual.

## AC-042 AGT-006

Related requirement: AGT-006 — Schedule.

Preconditions: Isolated agent test runtime uses synthetic tokens and controlled API/media fixtures; real account proof uses separately authorised staging access.

Action: Change test schedule and trigger overlapping runs.

Expected result: Configured timing honoured; one active run per account; skip recorded.

Failure behaviour: Second run never imports concurrently.

Verification method: Scheduler/integration.

## AC-043 AGT-007

Related requirement: AGT-007 — Post retrieval.

Preconditions: Isolated agent test runtime uses synthetic tokens and controlled API/media fixtures; real account proof uses separately authorised staging access.

Action: Read authorised account fixtures/live sample with image/video/caption.

Expected result: Stable source ID, canonical URL, timestamp, original caption, media type and embed/local descriptor normalised without comments/messages.

Failure behaviour: Missing required fields fail item safely; no scraping fallback.

Verification method: Contract/integration.

## AC-044 AGT-008

Related requirement: AGT-008 — Incremental processing.

Preconditions: Isolated agent test runtime uses synthetic tokens and controlled API/media fixtures; real account proof uses separately authorised staging access.

Action: Import, edit recent source, fail one item then rerun.

Expected result: Recent edits detected; failed item retried despite checkpoint advance; unchanged work skipped.

Failure behaviour: No failed item lost behind high-water mark.

Verification method: Replay/fault integration.

## AC-045 AGT-009

Related requirement: AGT-009 — Idempotent upsert.

Preconditions: Isolated agent test runtime uses synthetic tokens and controlled API/media fixtures; real account proof uses separately authorised staging access.

Action: Run identical import twice and attempt concurrent duplicate insert.

Expected result: One record per tuple; second run updates/skips without duplicate.

Failure behaviour: Constraint rejects racing duplicates.

Verification method: DB/replay.

## AC-046 AGT-010

Related requirement: AGT-010 — Media handling.

Preconditions: Isolated agent test runtime uses synthetic tokens and controlled API/media fixtures; real account proof uses separately authorised staging access.

Action: Resolve approved embed then simulate unavailable embed and permitted valid/invalid local downloads.

Expected result: Embed preferred; only validated local fallback promoted when needed; item links presentation descriptor atomically.

Failure behaviour: Bad download leaves previous valid record/media intact.

Verification method: Media/fault integration.

## AC-047 AGT-011

Related requirement: AGT-011 — Default publication policy.

Preconditions: Isolated agent test runtime uses synthetic tokens and controlled API/media fixtures; real account proof uses separately authorised staging access.

Action: Import complete valid new records using selected automatic policy; repeat with malformed media and existing Hidden item.

Expected result: Valid new records publish automatically with publish_at; incomplete new records enter Error/retry; existing Hidden state remains.

Failure behaviour: No approval gate added; failed import cannot reset editorial decisions or corrupt published assets.

Verification method: DB/replay.

## AC-048 AGT-012

Related requirement: AGT-012 — Logging and metrics.

Preconditions: Isolated agent test runtime uses synthetic tokens and controlled API/media fixtures; real account proof uses separately authorised staging access.

Action: Run mixed inserted/updated/skipped/failed fixtures.

Expected result: Start/end/account and accurate counts/status recorded with redacted summary.

Failure behaviour: Crash marks Interrupted on recovery; no secrets in log.

Verification method: Integration/security.

## AC-049 AGT-013

Related requirement: AGT-013 — Retries.

Preconditions: Isolated agent test runtime uses synthetic tokens and controlled API/media fixtures; real account proof uses separately authorised staging access.

Action: Inject transient failures, Retry-After and authentication failure.

Expected result: At most initial+3 attempts within budget; auth stops immediately and alerts.

Failure behaviour: No credential in alert; delayed retry resumes next run.

Verification method: Fault/contract.

## AC-050 AGT-014

Related requirement: AGT-014 — Deletion policy.

Preconditions: Isolated agent test runtime uses synthetic tokens and controlled API/media fixtures; real account proof uses separately authorised staging access.

Action: Simulate missing listing, transient 404 and confirmed unavailability.

Expected result: No hard deletion; configured keep/hide/review applied only on confirmed policy conditions.

Failure behaviour: Single inconclusive response retains valid item and logs uncertainty.

Verification method: Replay/UAT.

## AC-051 SEC-001

Related requirement: SEC-001 — All public and administrative traffic shall use HTTPS. HTTP shall redirect to HTTPS..

Preconditions: Isolated staging runs production-equivalent proxy, role grants and mounts with synthetic secrets and adversarial fixtures.

Action: Request HTTP then HTTPS public/admin routes.

Expected result: HTTP redirects to valid HTTPS; protected traffic encrypted.

Failure behaviour: Bad cert not bypassed; no plaintext auth endpoint.

Verification method: Deployment/security.

## AC-052 SEC-002

Related requirement: SEC-002 — Administrator passwords shall use a modern adaptive hash such as Argon2id or bcrypt with appropriate cost..

Preconditions: Isolated staging runs production-equivalent proxy, role grants and mounts with synthetic secrets and adversarial fixtures.

Action: Create password and inspect persisted record after login.

Expected result: Adaptive Argon2id/bcrypt hash only, tuned approved cost.

Failure behaviour: Plaintext never stored or logged.

Verification method: Auth/security.

## AC-053 SEC-003

Related requirement: SEC-003 — Administrative login shall be rate-limited and protected against credential stuffing. Optional MFA should be supported or planned..

Preconditions: Isolated staging runs production-equivalent proxy, role grants and mounts with synthetic secrets and adversarial fixtures.

Action: Fail logins above limits across multiple web workers using the one configured administrator.

Expected result: Shared account/IP throttles enforced; password/session flow works without mandatory MFA.

Failure behaviour: Generic errors prevent enumeration; no permanent attacker-driven lockout.

Verification method: Security.

## AC-054 SEC-004

Related requirement: SEC-004 — The web application and agent shall use separate least-privilege database credentials..

Preconditions: Isolated staging runs production-equivalent proxy, role grants and mounts with synthetic secrets and adversarial fixtures.

Action: Connect using each runtime identity and try prohibited reads/writes.

Expected result: Each has only stated views/columns/operations; no owner privilege.

Failure behaviour: Forbidden queries denied by DB.

Verification method: DB/security.

## AC-055 SEC-005

Related requirement: SEC-005 — Instagram credentials shall never be present in public web files, source control, client-side code, application logs or browser storage..

Preconditions: Isolated staging runs production-equivalent proxy, role grants and mounts with synthetic secrets and adversarial fixtures.

Action: Scan source/build/client/web mounts with synthetic credential.

Expected result: Credential absent from all website assets/storage/logs.

Failure behaviour: Build/deploy fails on exposed fixture secret.

Verification method: Security/artifact.

## AC-056 SEC-006

Related requirement: SEC-006 — All editable HTML shall be sanitised using an allowlist. Content Security Policy shall block inline scripts unless explicitly required and nonce-controlled..

Preconditions: Isolated staging runs production-equivalent proxy, role grants and mounts with synthetic secrets and adversarial fixtures.

Action: Save markup attacks and inspect CSP in browser.

Expected result: Dangerous HTML removed/rejected; inline script blocked absent approved nonce.

Failure behaviour: No execution in public or preview.

Verification method: Browser/security.

## AC-057 SEC-007

Related requirement: SEC-007 — Forms and state-changing admin actions shall have CSRF protection, input validation and output encoding..

Preconditions: Isolated staging runs production-equivalent proxy, role grants and mounts with synthetic secrets and adversarial fixtures.

Action: Send cross-origin mutations and malicious values.

Expected result: Mutations refused without valid CSRF; values validated/encoded.

Failure behaviour: No DB/provider side effects on rejection.

Verification method: Security.

## AC-058 SEC-008

Related requirement: SEC-008 — Secrets shall be rotated without rebuilding the website. Backup copies containing secrets shall remain encrypted..

Preconditions: Isolated staging runs production-equivalent proxy, role grants and mounts with synthetic secrets and adversarial fixtures.

Action: Rotate synthetic DB/mail/agent secrets and inspect backup.

Expected result: Rotation works without website rebuild; backups encrypted.

Failure behaviour: Failed rotation retains last working version and alerts.

Verification method: Ops/security.

## AC-059 SEC-009

Related requirement: SEC-009 — Administrative and agent events shall be logged without sensitive values. Logs shall have retention and access controls..

Preconditions: Isolated staging runs production-equivalent proxy, role grants and mounts with synthetic secrets and adversarial fixtures.

Action: Trigger admin/agent failures and retention cleanup.

Expected result: Required events redacted, authorised-only, expired logs removed per policy.

Failure behaviour: No passwords/tokens/contact bodies in logs.

Verification method: Security/retention.

## AC-060 SEC-010

Related requirement: SEC-010 — Dependencies shall be pinned, scanned and updated through a controlled process..

Preconditions: Isolated staging runs production-equivalent proxy, role grants and mounts with synthetic secrets and adversarial fixtures.

Action: Build release from clean runner and run scan.

Expected result: Pinned dependencies/digests, recorded licences and controlled update checks.

Failure behaviour: Block unresolved exploitable findings before release.

Verification method: CI/security.

## AC-061 SEC-011

Related requirement: SEC-011 — The solution shall provide a configurable privacy notice, cookie notice where required, and a retention policy for contact information and logs..

Preconditions: Isolated staging runs production-equivalent proxy, role grants and mounts with synthetic secrets and adversarial fixtures.

Action: Review notices/cookies and execute retention job on expired fixtures.

Expected result: Configured privacy text and applicable cookie notice reflect actual use; retention enforced.

Failure behaviour: Missing owner decisions block production processing.

Verification method: UAT/security.

## AC-062 SEC-012

Related requirement: SEC-012 — The implementation shall comply with applicable Instagram/Meta platform terms, API permissions and data-use restrictions..

Preconditions: Isolated staging runs production-equivalent proxy, role grants and mounts with synthetic secrets and adversarial fixtures.

Action: Review current official API contract and authorised read proof.

Expected result: Permitted integration/permissions/media use documented before production import.

Failure behaviour: No unsupported password scraper substituted.

Verification method: Contract/manual.

## AC-063 NFR-001

Related requirement: NFR-001 — Performance.

Preconditions: Integrated staging has 10,000 synthetic items and production-equivalent runtime settings; test scope and target assumptions are recorded.

Action: Load 10k items at 10 req/s and 50 concurrent sessions for 15 min.

Expected result: Proposed p95 server response below 2 seconds; resized/lazy images present.

Failure behaviour: Report failed target and bottleneck; do not claim pass.

Verification method: Performance/browser.

## AC-064 NFR-002

Related requirement: NFR-002 — Availability.

Preconditions: Integrated staging has 10,000 synthetic items and production-equivalent runtime settings; test scope and target assumptions are recorded.

Action: Measure monthly successful checks excluding recorded maintenance.

Expected result: 99.5% availability target tracked with published error budget.

Failure behaviour: Alert on failed checks and investigate gaps.

Verification method: Operations/UAT.

## AC-065 NFR-003

Related requirement: NFR-003 — Scalability.

Preconditions: Integrated staging has 10,000 synthetic items and production-equivalent runtime settings; test scope and target assumptions are recorded.

Action: Seed 10k records and exercise public/admin lists.

Expected result: Bounded pages, indexed plans and no redesign needed at baseline.

Failure behaviour: Unbounded/scan-dominated query fails review.

Verification method: DB/performance.

## AC-066 NFR-004

Related requirement: NFR-004 — Compatibility.

Preconditions: Integrated staging has 10,000 synthetic items and production-equivalent runtime settings; test scope and target assumptions are recorded.

Action: Run core flows on current Chrome/Safari/Firefox/Edge and iOS/Android browsers.

Expected result: Navigation/forms/media/locale work within stated viewport matrix.

Failure behaviour: Document and fix blocking incompatibility before release.

Verification method: Browser/manual.

## AC-067 NFR-005

Related requirement: NFR-005 — Accessibility.

Preconditions: Integrated staging has 10,000 synthetic items and production-equivalent runtime settings; test scope and target assumptions are recorded.

Action: Audit public and core admin flows automatically and manually.

Expected result: No known AA failure in defined flows; keyboard and contrast review recorded.

Failure behaviour: Unresolved failures recorded rather than claiming compliance.

Verification method: Accessibility/manual.

## AC-068 NFR-006

Related requirement: NFR-006 — Maintainability.

Preconditions: Integrated staging has 10,000 synthetic items and production-equivalent runtime settings; test scope and target assumptions are recorded.

Action: Rebuild and initialise staging from locked revision and documented settings.

Expected result: Reproducible container artifacts/schema and documented Compose topology; application config externalised; owner-managed HTTPS boundary documented.

Failure behaviour: Missing config fails validation without secret exposure.

Verification method: CI/migration.

## AC-069 NFR-007

Related requirement: NFR-007 — Backup.

Preconditions: Integrated staging has 10,000 synthetic items and production-equivalent runtime settings; test scope and target assumptions are recorded.

Action: Restore encrypted snapshot and media manifest in isolated staging.

Expected result: References/checksums valid, publish rules intact, agreed RPO/RTO demonstrated.

Failure behaviour: Failed restore alerts and release evidence remains incomplete.

Verification method: Restore drill.

## AC-070 NFR-008

Related requirement: NFR-008 — Observability.

Preconditions: Integrated staging has 10,000 synthetic items and production-equivalent runtime settings; test scope and target assumptions are recorded.

Action: Inject repeated imports/mail failures and fail readiness.

Expected result: Structured redacted events, run records and threshold alerts observed.

Failure behaviour: Public health reveals no diagnostics or secrets.

Verification method: Fault/operations.

## AC-071 NFR-009

Related requirement: NFR-009 — SEO.

Preconditions: Integrated staging has 10,000 synthetic items and production-equivalent runtime settings; test scope and target assumptions are recorded.

Action: Set titles/descriptions and inspect HTML/sitemap.

Expected result: Configured metadata, canonicals/social tags present; admin excluded.

Failure behaviour: Unsafe metadata escaped; draft URLs omitted.

Verification method: HTML/integration.

## AC-072 DATA-001

Related requirement: DATA-001 — Combination of source_platform, source_account_id and source_post_id shall be unique..

Preconditions: Real staging PostgreSQL/media services use the proposed schema, actual runtime roles and synthetic ownership/status/date fixtures.

Action: Insert duplicate source platform/account/post tuple.

Expected result: Database rejects duplicate; upsert resolves existing ID.

Failure behaviour: No duplicate visible even under concurrent insert.

Verification method: DB/concurrency.

## AC-073 DATA-002

Related requirement: DATA-002 — Database timestamps shall be stored in UTC and rendered in the configured site timezone..

Preconditions: Real staging PostgreSQL/media services use the proposed schema, actual runtime roles and synthetic ownership/status/date fixtures.

Action: Store/display dates across DST boundary.

Expected result: UTC stored; selected locale/date shown in configured IANA timezone.

Failure behaviour: Invalid/ambiguous local input requires explicit resolution.

Verification method: Unit/DB/browser.

## AC-074 DATA-003

Related requirement: DATA-003 — Public queries shall exclude non-published statuses at the query layer, not only in templates..

Preconditions: Real staging PostgreSQL/media services use the proposed schema, actual runtime roles and synthetic ownership/status/date fixtures.

Action: Issue public-role queries against statuses and base tables.

Expected result: Hidden/draft/error/archived/future records excluded at query layer.

Failure behaviour: Direct base-table reads denied.

Verification method: DB/security.

## AC-075 DATA-004

Related requirement: DATA-004 — Media paths shall not accept user-controlled traversal sequences or executable extensions..

Preconditions: Real staging PostgreSQL/media services use the proposed schema, actual runtime roles and synthetic ownership/status/date fixtures.

Action: Submit traversal, encoded separators and executable extensions.

Expected result: No write outside controlled non-executable storage.

Failure behaviour: Reject input; no executable content served.

Verification method: Security/filesystem.

## AC-076 DATA-005

Related requirement: DATA-005 — HTML-capable fields shall store sanitised content or a safe structured representation..

Preconditions: Real staging PostgreSQL/media services use the proposed schema, actual runtime roles and synthetic ownership/status/date fixtures.

Action: Save/reload malicious markup via every entry point.

Expected result: Only allowlisted safe representation stored/rendered.

Failure behaviour: Rejected unsafe content cannot bypass through preview/import.

Verification method: Unit/security.

## AC-077 DATA-006

Related requirement: DATA-006 — Database migrations shall be versioned and reversible where practical..

Preconditions: Real staging PostgreSQL/media services use the proposed schema, actual runtime roles and synthetic ownership/status/date fixtures.

Action: Apply migrations and test planned reverse/forward recovery.

Expected result: Schema changes recorded; practical reverse paths demonstrated.

Failure behaviour: Irreversible change has restore/forward-fix plan before release.

Verification method: Migration/drill.

## AC-078 OPS-001

Related requirement: OPS-001 — Use separate development, test/staging and production environments..

Preconditions: Owner-selected staging topology, encrypted backup location and authorised operator are available; production is not modified.

Action: Inspect Docker dev/staging/production configuration, networks, volumes and scoped secrets.

Expected result: Isolated data/services/secrets; no production credentials in test.

Failure behaviour: Cross-environment access denied.

Verification method: Deployment/security.

## AC-079 OPS-002

Related requirement: OPS-002 — Run the public web application, database and agent under separate service identities or containers..

Preconditions: Owner-selected staging topology, encrypted backup location and authorised operator are available; production is not modified.

Action: Inspect web/database/agent process users or containers.

Expected result: Separate identities and least privileges; non-root application roles.

Failure behaviour: Web cannot act as agent or DB owner.

Verification method: Runtime/security.

## AC-080 OPS-003

Related requirement: OPS-003 — Mount public media as non-executable and avoid sharing the agent credential directory with the web container..

Preconditions: Owner-selected staging topology, encrypted backup location and authorised operator are available; production is not modified.

Action: Read agent directory as web and request uploaded executable.

Expected result: Credential read denied; media never executes.

Failure behaviour: Reject unsafe file; no shared secret mount.

Verification method: Runtime/security.

## AC-081 OPS-004

Related requirement: OPS-004 — Use environment variables or a secrets manager for database/mail credentials, but do not expose secrets through client-side build variables..

Preconditions: Owner-selected staging topology, encrypted backup location and authorised operator are available; production is not modified.

Action: Inspect environment scopes and built browser assets.

Expected result: DB/mail secrets only in needed containers; no client build secret or agent token in web; owner-managed SSL boundary documented.

Failure behaviour: Release check blocks synthetic leaked secret.

Verification method: Artifact/security.

## AC-082 OPS-005

Related requirement: OPS-005 — Run database migrations as an explicit deployment step with rollback planning..

Preconditions: Owner-selected staging topology, encrypted backup location and authorised operator are available; production is not modified.

Action: Deploy compatible migration then induce failure.

Expected result: Single migration actor; rollback plan available; unready version not routed.

Failure behaviour: No worker auto-migration/racing schema edits.

Verification method: Deployment/migration.

## AC-083 OPS-006

Related requirement: OPS-006 — Configure scheduler overlap protection so a new agent run does not start while a previous run is active..

Preconditions: Owner-selected staging topology, encrypted backup location and authorised operator are available; production is not modified.

Action: Trigger two jobs and kill current run.

Expected result: Only one import active; interrupted run resumes from durable state.

Failure behaviour: Second process exits safe skip; no duplicate updates.

Verification method: Scheduler/fault.

## AC-084 OPS-007

Related requirement: OPS-007 — Monitor disk usage because downloaded video can grow quickly; configure retention and media optimisation..

Preconditions: Owner-selected staging topology, encrypted backup location and authorised operator are available; production is not modified.

Action: Approach configured quota and run reference-aware cleanup.

Expected result: Warnings before exhaustion; derivatives bounded; referenced valid media retained.

Failure behaviour: Stop download without corrupting live data.

Verification method: Storage/fault.

## AC-085 OPS-008

Related requirement: OPS-008 — Document manual credential rotation, forced agent run, import pause, item republish and disaster recovery procedures..

Preconditions: Owner-selected staging topology, encrypted backup location and authorised operator are available; production is not modified.

Action: Operator follows each runbook in staging.

Expected result: Credential rotation, forced run, pause, republish and disaster recovery demonstrated.

Failure behaviour: Unsafe/incomplete procedure fails handoff.

Verification method: Manual/drill.

## AC-086 CONTACT-001

Related requirement: CONTACT-001 — Contact field contract.

Preconditions: Staging form, shared limiter and test mail sink are available with a controllable provider response.

Action: Submit boundary lengths, bad email, empty/valid phone and repeated key.

Expected result: Source field limits enforced server-side; duplicate send prevented; processing button disabled.

Failure behaviour: Field errors localised; no send on invalid input.

Verification method: Unit/browser/mail.

## AC-087 DATA-007

Related requirement: DATA-007 — Entity coverage.

Preconditions: Real staging PostgreSQL/media services use the proposed schema, actual runtime roles and synthetic ownership/status/date fixtures.

Action: Compare model inventory/fields with source entity table.

Expected result: All eight source entities and named fields represented or explicitly mapped to safer reference/revision fields.

Failure behaviour: Missing source field blocks schema acceptance.

Verification method: Schema review/DB.
