> Historical record. This document describes an earlier design or implementation;
> use the [current documentation](../../README.md) and [installation guide](../../../INSTALL.md) for current behaviour.

# Requirement traceability

Design coverage only, amended by [owner decisions](owner-decisions.md): no application has been implemented or tested. “Proposed” means the design covers the requirement, with decisions and live provider verification still open. Acceptance IDs are separate from the source AC-01–16; the mapping below retains those source checks.

| Original requirement | Requirement ID | Component | Interface/data dependency | Work package | Acceptance | Test type | Design coverage |
| --- | --- | --- | --- | --- | --- | --- | --- |
| UI-001 — Header and menu | UI-001 | Public/admin | Header settings and navigation | WP-04/06 | AC-001 | Browser E2E | Proposed; Required navigation must survive custom markup |
| UI-002 — Presentation/body area | UI-002 | Public web | Page templates | WP-04 | AC-002 | Browser E2E | Proposed; Shared shell cannot replace page body |
| UI-003 — Footer | UI-003 | Public/admin | Footer setting revisions | WP-04/06 | AC-003 | Browser E2E | Proposed; Locale-specific footer support |
| UI-004 — Responsive behaviour | UI-004 | Public web | Responsive CSS and asset dimensions | WP-04 | AC-004 | Browser/manual | Proposed; Source has no exact viewport matrix; these are proposed |
| UI-005 — Accessibility | UI-005 | Public web/admin | Accessible components and alt text | WP-04/06 | AC-005 | Accessibility/manual | Proposed; Human AA audit supplements automation |
| FEED-001 — Database-fed list | FEED-001 | Public web | Published item view and ordering index | WP-02/04 | AC-006 | DB/browser | Proposed; Priority precedence requires D-06 confirmation |
| FEED-002 — Instagram-style card | FEED-002 | Public web | Card component and eligible media | WP-04 | AC-007 | Browser E2E | Proposed; No protected brand assets assumed |
| FEED-003 — Source click-through | FEED-003 | Public web | Canonical source link | WP-04 | AC-008 | Browser/security | Proposed; Owner media amendment: embed controls retain provider behaviour and a separate source link; local media keeps source-linked poster/image. |
| FEED-004 — Media types | FEED-004 | Media/public | Media types and ordered records | WP-05 | AC-009 | Browser/integration | Proposed; Owner confirms embed-first image/video presentation, with permitted validated local-media fallback. |
| FEED-005 — Text rendering | FEED-005 | Public web | Safe caption rendering | WP-04 | AC-010 | Unit/browser security | Proposed; Imported source remains plain text |
| FEED-006 — Pagination | FEED-006 | Public web | Page-size setting and cursor | WP-02/04 | AC-011 | DB/integration | Proposed; Proposed public maximum 48 |
| FEED-007 — Publication control | FEED-007 | Public web/media | Published views and publish_at | WP-02/04/05 | AC-012 | DB/security/browser | Proposed; New valid imports auto-publish; publication filters and failure protection remain mandatory. |
| FEED-008 — Empty/error state | FEED-008 | Public web | Empty message setting and DB errors | WP-04 | AC-013 | Integration/browser | Proposed; Empty and unavailable are distinct |
| CON-001 — Submission delivery | CON-001 | Contact | Mail adapter and recipient revision | WP-07 | AC-014 | Mail integration | Proposed; Provider choice pending D-11 |
| CON-002 — Confirmation | CON-002 | Contact | Localised contact response | WP-07 | AC-015 | Browser/mail | Proposed; Acceptance differs from inbox delivery |
| CON-003 — Abuse prevention | CON-003 | Contact | CSRF shared counters and honeypot | WP-07 | AC-016 | Security/integration | Proposed; Rate defaults proposed in §12 |
| CON-004 — Failure handling | CON-004 | Contact | Delivery event states | WP-07 | AC-017 | Mail/fault integration | Proposed; Exactly-once not guaranteed for SMTP |
| CON-005 — Privacy | CON-005 | Contact | Privacy notice resource | WP-07 | AC-018 | Browser/UAT | Proposed; Owner must approve policy |
| REV-001 — Review list | REV-001 | Public reviews | Published review view | WP-04 | AC-019 | DB/browser | Proposed; Rating scale proposed 1–5 |
| REV-002 — Management | REV-002 | Admin/reviews | Review service and revisions | WP-06 | AC-020 | Browser/DB | Proposed; No public submission path |
| REV-003 — Future submission option | REV-003 | Public/admin | Route inventory and scope | WP-04/06 | AC-021 | Security/route audit | Proposed; Source requires deferring public submission |
| ADM-001 — Authentication | ADM-001 | Admin auth | Session/user store | WP-03 | AC-022 | Auth integration/security | Proposed; Owner confirms one named admin and no mandatory MFA. |
| ADM-002 — Menu section editor | ADM-002 | Admin/settings | Header sanitisation | WP-06 | AC-023 | Unit/browser security | Proposed; Controlled markup required |
| ADM-003 — Theme editor | ADM-003 | Admin/media | Theme revision and preview | WP-05/06 | AC-024 | Browser/security | Proposed; Approved assets/colours await owner |
| ADM-004 — Database search | ADM-004 | Admin/content | Indexed item search | WP-06 | AC-025 | DB/browser | Proposed; Search must include original and translated text |
| ADM-005 — Database editing | ADM-005 | Admin/content | Overrides/source revisions/version | WP-06 | AC-026 | DB/replay/browser | Proposed; Post text remains in original language; no EN/FR caption substitutions required. Other metadata/site translations remain supported. |
| ADM-006 — Footer editor | ADM-006 | Admin/settings | Footer sanitisation | WP-06 | AC-027 | Unit/browser security | Proposed; Same policy as header |
| ADM-007 — Contact recipient | ADM-007 | Admin/settings/contact | Recipient validation/revision | WP-06/07 | AC-028 | Mail/browser integration | Proposed; Test-confirmation workflow proposed |
| ADM-008 — Language mode | ADM-008 | Admin/settings | Locale configuration and label overrides | WP-06 | AC-029 | Unit/browser | Proposed; Confirm always-on EN/FR conflict |
| ADM-009 — Audit trail | ADM-009 | Admin/audit | Transactional audit/revision | WP-03/06 | AC-030 | DB/security | Proposed; Append-only app grants |
| ADM-010 — Safe media upload | ADM-010 | Media/admin | Private upload validation | WP-05 | AC-031 | Media/security | Proposed; No SVG backgrounds by default |
| L10N-001 — Language switch | L10N-001 | Public web | Locale routes/preference | WP-04 | AC-032 | Browser/integration | Proposed; 30-day preference proposed |
| L10N-002 — Interface resources | L10N-002 | Public/admin | Packaged resources and override keys | WP-04/06 | AC-033 | Unit/browser | Proposed; No automatic caption translation |
| L10N-003 — Content fields | L10N-003 | Content/settings/reviews | Locale fields and fallback | WP-06 | AC-034 | Unit/browser | Proposed; Site copy/reviews may use locale fallback; imported posts always use original-language caption. |
| L10N-004 — Imported posts | L10N-004 | Agent/admin | Original caption and manual overrides | WP-06/08 | AC-035 | Replay/DB | Proposed; Owner supersedes optional translated post display: retain source-language caption on every locale; no post translation feature required. |
| L10N-005 — URLs and metadata | L10N-005 | Public web | Locale metadata and sitemap | WP-04 | AC-036 | HTML/browser | Proposed; Localised URLs selected as proposal |
| AGT-001 — Credential entry | AGT-001 | Agent secrets | Local provisioning contract | WP-08 | AC-037 | Security/contract | Proposed; Current account is personal; recommend Creator conversion and Instagram Login OAuth, not a stored password. Conversion is unapproved. |
| AGT-002 — Encryption | AGT-002 | Agent secrets | Separate key/store | WP-08 | AC-038 | Filesystem/security | Proposed; Agent-only encrypted API tokens and separately protected key; website receives no reusable authorisation. |
| AGT-003 — Validation | AGT-003 | Agent adapter | Authentication probe | WP-01/08 | AC-039 | Contract/security | Proposed; Verify account eligibility and token read access; personal account cannot use the proposed professional route. |
| AGT-004 — Restricted retrieval | AGT-004 | Agent secrets | Runtime secret access | WP-08 | AC-040 | Runtime identity/security | Proposed; Agent runtime alone uses tokens; isolated provisioning callback may exchange OAuth code outside web app. |
| AGT-005 — No export | AGT-005 | Agent secrets | Command/route inventory | WP-08 | AC-041 | Security/manual | Proposed; No admin credential-return endpoint |
| AGT-006 — Schedule | AGT-006 | Agent scheduler | Timer and shared lock | WP-08 | AC-042 | Scheduler/integration | Proposed; Six-hour default proposed |
| AGT-007 — Post retrieval | AGT-007 | Agent adapter | Source schema and verified API | WP-01/08 | AC-043 | Contract/integration | Proposed; Owner confirms post captions only; no comment/message retrieval or corresponding permissions. |
| AGT-008 — Incremental processing | AGT-008 | Agent import | Checkpoint/look-back/failure ledger | WP-08 | AC-044 | Replay/fault integration | Proposed; Weekly historic reconciliation proposed |
| AGT-009 — Idempotent upsert | AGT-009 | Agent DB | Unique source tuple/upsert | WP-08 | AC-045 | DB/replay | Proposed; Transaction handles race |
| AGT-010 — Media handling | AGT-010 | Agent media | Staged stream/type/size | WP-05/08 | AC-046 | Media/fault integration | Proposed; Owner confirms official embed first, otherwise permitted source media downloaded and validated locally. |
| AGT-011 — Default publication policy | AGT-011 | Agent publication | Validated configured import policy | WP-08 | AC-047 | DB/replay | Proposed; Owner selects automatic publication as initial default; Draft may remain a configurable alternative but is not the selected workflow. |
| AGT-012 — Logging and metrics | AGT-012 | Agent operations | Run/counter/error schema | WP-08 | AC-048 | Integration/security | Proposed; Counters defined per completed item |
| AGT-013 — Retries | AGT-013 | Agent operations | Retry/auth alert policy | WP-08/09 | AC-049 | Fault/contract | Proposed; Threshold contradiction resolved explicitly |
| AGT-014 — Deletion policy | AGT-014 | Agent/admin | Independent source availability | WP-08 | AC-050 | Replay/UAT | Proposed; D-07 default request review |
| SEC-001 — All public and administrative traffic shall use HTTPS. HTTP shall redirect to HTTPS. | SEC-001 | Proxy/web | TLS routing | WP-03/09 | AC-051 | Deployment/security | Proposed; Domain/TLS owner selected |
| SEC-002 — Administrator passwords shall use a modern adaptive hash such as Argon2id or bcrypt with appropriate cost. | SEC-002 | Admin auth | Password hash config | WP-03 | AC-052 | Auth/security | Proposed; Proposed Argon2id requires dependency |
| SEC-003 — Administrative login shall be rate-limited and protected against credential stuffing. Optional MFA should be supported or planned. | SEC-003 | Admin auth | Shared throttles and MFA extension | WP-03 | AC-053 | Security | Proposed; Single admin, password/session authentication and shared throttles; owner does not require MFA. |
| SEC-004 — The web application and agent shall use separate least-privilege database credentials. | SEC-004 | DB/runtime | Separate public/admin/agent grants | WP-02 | AC-054 | DB/security | Proposed; Do not rely only on ORM filtering |
| SEC-005 — Instagram credentials shall never be present in public web files, source control, client-side code, application logs or browser storage. | SEC-005 | Agent/web builds | Secret mounts/artifact contents | WP-08/09 | AC-055 | Security/artifact | Proposed; Agent secrets never in source |
| SEC-006 — All editable HTML shall be sanitised using an allowlist. Content Security Policy shall block inline scripts unless explicitly required and nonce-controlled. | SEC-006 | Admin/public | Allowlist/CSP | WP-06 | AC-056 | Browser/security | Proposed; Do not trust staff HTML |
| SEC-007 — Forms and state-changing admin actions shall have CSRF protection, input validation and output encoding. | SEC-007 | All web forms | CSRF/encoding/validation | WP-03/07 | AC-057 | Security | Proposed; Same policy covers admin |
| SEC-008 — Secrets shall be rotated without rebuilding the website. Backup copies containing secrets shall remain encrypted. | SEC-008 | Operator/secrets | Rotation/backup encryption | WP-08/09 | AC-058 | Ops/security | Proposed; Separate keys/privileges |
| SEC-009 — Administrative and agent events shall be logged without sensitive values. Logs shall have retention and access controls. | SEC-009 | Operations/audit | Safe logs/retention/access | WP-03/09 | AC-059 | Security/retention | Proposed; Final periods pending D-14 |
| SEC-010 — Dependencies shall be pinned, scanned and updated through a controlled process. | SEC-010 | CI/dependencies | Lockfile/SBOM/scanning | WP-09 | AC-060 | CI/security | Proposed; Patch versions chosen at setup |
| SEC-011 — The solution shall provide a configurable privacy notice, cookie notice where required, and a retention policy for contact information and logs. | SEC-011 | Privacy/settings | Notice/retention resources | WP-06/09 | AC-061 | UAT/security | Proposed; Legal/privacy review needed |
| SEC-012 — The implementation shall comply with applicable Instagram/Meta platform terms, API permissions and data-use restrictions. | SEC-012 | Agent integration | Approved permission/terms decision | WP-01/08 | AC-062 | Contract/manual | Proposed; Current Meta docs inaccessible during design |
| NFR-001 — Performance | NFR-001 | Public web | Load benchmark | WP-09 | AC-063 | Performance/browser | Proposed; Load/percentile are proposed normal-load definition |
| NFR-002 — Availability | NFR-002 | Operations | External uptime monitor | WP-09 | AC-064 | Operations/UAT | Proposed; Target is not implementation evidence |
| NFR-003 — Scalability | NFR-003 | DB/public | 10k fixture and pagination/indexes | WP-02/09 | AC-065 | DB/performance | Proposed; Index multilingual search explicitly |
| NFR-004 — Compatibility | NFR-004 | Public/admin UI | Browser matrix | WP-04/10 | AC-066 | Browser/manual | Proposed; Native applications excluded |
| NFR-005 — Accessibility | NFR-005 | Public/admin UI | WCAG 2.2 AA review | WP-04/10 | AC-067 | Accessibility/manual | Proposed; Source says aim; verification scope explicit |
| NFR-006 — Maintainability | NFR-006 | Repository/deployment | External config/migrations/reproducibility | WP-02/09 | AC-068 | CI/migration | Proposed; Provide Docker/Compose application deployment contract; owner supplies TLS reverse proxy. |
| NFR-007 — Backup | NFR-007 | Operations | Consistent database/media backup | WP-09 | AC-069 | Restore drill | Proposed; Schedule/targets proposed |
| NFR-008 — Observability | NFR-008 | Operations | Health/logs/agent/mail alerts | WP-09 | AC-070 | Fault/operations | Proposed; Alert destination owner selected |
| NFR-009 — SEO | NFR-009 | Public web | SEO settings and sitemap | WP-04/06 | AC-071 | HTML/integration | Proposed; Locale metadata from L10N-005 |
| DATA-001 — Combination of source_platform, source_account_id and source_post_id shall be unique. | DATA-001 | DB/agent | Unique source key | WP-02/08 | AC-072 | DB/concurrency | Proposed; Single account now; key preserves future identity |
| DATA-002 — Database timestamps shall be stored in UTC and rendered in the configured site timezone. | DATA-002 | DB/public/admin | UTC and site timezone | WP-02/04 | AC-073 | Unit/DB/browser | Proposed; Europe/London provisional |
| DATA-003 — Public queries shall exclude non-published statuses at the query layer, not only in templates. | DATA-003 | DB/public | Published query view | WP-02 | AC-074 | DB/security | Proposed; Independent of templates |
| DATA-004 — Media paths shall not accept user-controlled traversal sequences or executable extensions. | DATA-004 | Media | Generated storage keys | WP-05 | AC-075 | Security/filesystem | Proposed; Do not accept path from client |
| DATA-005 — HTML-capable fields shall store sanitised content or a safe structured representation. | DATA-005 | Settings/content | Sanitised markup storage | WP-06 | AC-076 | Unit/security | Proposed; Original captions plain text |
| DATA-006 — Database migrations shall be versioned and reversible where practical. | DATA-006 | DB/deployment | Versioned migrations | WP-02/09 | AC-077 | Migration/drill | Proposed; No destructive automatic rollback |
| OPS-001 — Use separate development, test/staging and production environments. | OPS-001 | Deployment | Environment separation | WP-09 | AC-078 | Deployment/security | Proposed; Docker deployment confirmed; environment and persistent-state separation still required. |
| OPS-002 — Run the public web application, database and agent under separate service identities or containers. | OPS-002 | Deployment | Runtime identities | WP-09 | AC-079 | Runtime/security | Proposed; Separate container/runtime identities remain required within Docker topology. |
| OPS-003 — Mount public media as non-executable and avoid sharing the agent credential directory with the web container. | OPS-003 | Media/agent | Mount/execute policy | WP-05/09 | AC-080 | Runtime/security | Proposed; Public delivery gated by publication |
| OPS-004 — Use environment variables or a secrets manager for database/mail credentials, but do not expose secrets through client-side build variables. | OPS-004 | Secrets/deployment | Runtime secret injection | WP-09 | AC-081 | Artifact/security | Proposed; Container-scoped runtime secrets; owner handles infrastructure and SSL. |
| OPS-005 — Run database migrations as an explicit deployment step with rollback planning. | OPS-005 | DB/deployment | Explicit migration step | WP-09 | AC-082 | Deployment/migration | Proposed; Document explicit container migration step; do not provision owner host infrastructure. |
| OPS-006 — Configure scheduler overlap protection so a new agent run does not start while a previous run is active. | OPS-006 | Agent scheduler | Overlap protection | WP-08 | AC-083 | Scheduler/fault | Proposed; DB lock shared across hosts |
| OPS-007 — Monitor disk usage because downloaded video can grow quickly; configure retention and media optimisation. | OPS-007 | Media/operations | Quota/retention/optimisation | WP-05/09 | AC-084 | Storage/fault | Proposed; Video policy and budget pending |
| OPS-008 — Document manual credential rotation, forced agent run, import pause, item republish and disaster recovery procedures. | OPS-008 | Operations/docs | Rotation/import/pause/republish/restore runbooks | WP-09/10 | AC-085 | Manual/drill | Proposed; Named operator required |
| CONTACT-001 — Contact field contract | CONTACT-001 | Contact | Form field contract | WP-07 | AC-086 | Unit/browser/mail | Proposed; Phone intentionally optional |
| DATA-007 — Entity coverage | DATA-007 | DB/domain | Source entity contract §12 | WP-02 | AC-087 | Schema review/DB | Proposed; Additions support source preservation and ownership |

## Source acceptance criteria coverage

| Original acceptance check | Requirements | Detailed acceptance criteria |
| --- | --- | --- |
| AC-01 | UI-001, UI-004 | AC-001, AC-004 |
| AC-02 | FEED-002, FEED-004 | AC-007, AC-009 |
| AC-03 | FEED-003 | AC-008 |
| AC-04 | FEED-007 | AC-012 |
| AC-05 | CON-001, CONTACT-001 | AC-014, AC-086 |
| AC-06 | ADM-001, SEC-004 | AC-022, AC-054 |
| AC-07 | ADM-002, ADM-006, SEC-006 | AC-023, AC-027, AC-056 |
| AC-08 | ADM-003 | AC-024 |
| AC-09 | ADM-004, ADM-005, REV-002 | AC-025, AC-026, AC-020 |
| AC-10 | ADM-007 | AC-028 |
| AC-11 | L10N-001, L10N-002, L10N-003, ADM-008 | AC-032, AC-033, AC-034, AC-029 |
| AC-12 | AGT-002, AGT-004, SEC-005 | AC-038, AC-040, AC-055 |
| AC-13 | AGT-009 | AC-045 |
| AC-14 | AGT-010, AGT-013 | AC-046, AC-049 |
| AC-15 | ADM-001, L10N-005, NFR-009 | AC-022, AC-036, AC-071 |
| AC-16 | NFR-007 | AC-069 |

## Coverage statement

87 source requirements/contracts are catalogued and mapped one-to-one to detailed acceptance criteria. All 50 numbered functional requirements and 12 security requirements are included. All 16 source acceptance checks are mapped. No numbered functional requirement has been omitted. This confirms documentation coverage only; open owner decisions and authorised live integration validation remain pending.
