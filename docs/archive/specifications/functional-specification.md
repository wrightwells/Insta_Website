> Historical record. This document describes an earlier design or implementation;
> use the [current documentation](../../README.md) and [installation guide](../../../INSTALL.md) for current behaviour.

> Owner amendments: [owner-decisions.md](owner-decisions.md) supersede conflicting draft defaults. The original text below is preserved.

<!-- Extracted from the unchanged source DOCX. Paragraph and table order preserved. -->

FUNCTIONAL SPECIFICATION

Instagram-Based Website Framework

Database-fed presentation site with secure administration and scheduled Instagram ingestion agent

| Document field | Value |
| --- | --- |
| Version | 1.0 |
| Status | Draft for review |
| Date | 23 July 2026 |
| Prepared for | Website based on Instagram project |
| Primary language | English, with French language mode |




1. Document Control

| Version | Date | Author | Change |
| --- | --- | --- | --- |
| 1.0 | 23 Jul 2026 | OpenAI / project team | Initial functional specification based on supplied outline |

1.1 Purpose

This document defines the functional and non-functional requirements for a reusable website framework that presents content sourced from an Instagram account. It describes the public website, contact and reviews pages, protected configuration interface, database, scheduled ingestion agent, security boundaries, localisation, and acceptance criteria.

1.2 Intended Audience

Product owner and project stakeholders

Web and backend developers

Agent/automation developer

System administrator and security reviewer

Test and quality assurance personnel

1.3 Terminology

| Term | Definition |
| --- | --- |
| Presentation item | A website record representing an Instagram post, including media, text and source URL. |
| Agent | A separate scheduled service that authenticates to Instagram and imports eligible post data. |
| Configuration page | A hidden, password-protected administration interface for site configuration and database editing. |
| Public site | The pages visible without authentication: Feed, Contact and Reviews. |
| Locale | The active site language, initially English (EN) or French (FR). |

2. Executive Summary

The solution will be a responsive website framework with three public navigation destinations: Main Feed, Contact and Reviews. The central presentation area on the Main Feed will display database-driven entries in a layout inspired by an Instagram post: image or video first, text beneath, and a media click-through to the original Instagram post URL. A protected configuration page will allow authorised administrators to edit shared page sections, visual appearance, database entries, contact routing and site language.

A separate agent process, deployed outside the public web file structure, will manage encrypted Instagram credentials and run on a schedule. It will retrieve posts and associated text, normalise them into the website database and retain processing status. The web application must not have access to plaintext Instagram credentials.

3. Scope

3.1 In Scope

Responsive reusable website shell with header/menu, presentation area and footer.

Public Main Feed, Contact and Reviews pages.

Database-driven image/video presentation cards and source links.

Password-protected configuration page with role-restricted access.

Editable header and footer HTML or controlled markup.

Theme configuration for background image, colours and fonts.

Database search and editing of presentation entries.

Configurable contact form delivery address.

English/French site-wide language switching.

Separate scheduled agent for secure Instagram credential storage, retrieval and post ingestion.

Operational logging, error handling, backups and basic audit history.

3.2 Out of Scope for Initial Release

Publishing, liking, commenting or direct messaging on Instagram.

Full social network features such as user profiles, follows or public accounts.

Online payment or e-commerce capabilities.

Advanced analytics beyond basic operational metrics.

Automatic translation of imported Instagram post text unless separately approved.

Multi-tenant administration or management of multiple unrelated sites in one instance.

3.3 Assumptions and Decisions Requiring Confirmation

| Ref | Assumption / proposed decision |
| --- | --- |
| A-01 | “Reviews” is a public page containing manually managed testimonials or reviews. Its detailed submission workflow is not yet defined. |
| A-02 | The Instagram source is one authorised account in the initial release. |
| A-03 | The site will store media locally or in managed object storage rather than hotlinking Instagram media URLs that may expire. |
| A-04 | The contact form sends an email and stores minimal delivery/audit status; long-term storage of contact messages is optional. |
| A-05 | Administrators edit sanitised HTML or restricted rich text. Arbitrary executable scripts are prohibited. |
| A-06 | French translations for fixed interface text are maintained in translation resources. Imported post text remains as originally published unless a translated field is entered manually. |
| A-07 | Instagram integration must use a method permitted by Instagram/Meta terms and available APIs. Browser automation is not assumed as the preferred production approach. |

4. Solution Overview and Architecture

The solution is divided into a public web application, an administration/configuration interface, a shared database and media store, and an isolated scheduled ingestion agent. The security boundary is designed so that the public web process can read published content but cannot retrieve Instagram credentials.

| Component | Primary responsibilities | Trust boundary |
| --- | --- | --- |
| Public web application | Render pages, read published items, submit contact form, switch locale. | Internet-facing; no Instagram credentials. |
| Configuration interface | Authenticate administrators; edit theme, content, settings and database records. | Restricted route and authenticated session. |
| Application database | Store presentation items, translations, settings, reviews, users and audit events. | Private network / least-privilege database accounts. |
| Media storage | Store downloaded images/video thumbnails or media files. | Not executable; validated upload types. |
| Instagram agent | Secure credential operations, scheduled retrieval, normalisation and import. | Separate runtime and filesystem from web root. |
| Scheduler | Invoke ingestion job according to configured timetable and retry policy. | Operating system scheduler or orchestration platform. |

4.1 Logical Data Flow

An administrator stores or updates Instagram credentials through the agent credential command or secured agent interface.

The agent encrypts credentials and stores only encrypted data or a reference to an external secrets manager.

The scheduler invokes the ingestion job.

The agent decrypts/retrieves credentials in memory, authenticates, reads eligible posts and extracts media metadata, caption/comment text and canonical post URL.

The agent downloads or copies permitted media into managed storage, then upserts normalised records into the database.

The public web application queries only records marked Published and renders them in the presentation feed.

An administrator may search, edit, hide, publish or override imported records from the protected configuration page.

5. Information Architecture and User Experience

5.1 Site Tree

| Level | Route (illustrative) | Page |
| --- | --- | --- |
| Public | / | Main Feed |
| Public | /contact | Contact |
| Public | /reviews | Reviews |
| Protected, unlinked | /manage-{configured-slug} | Configuration / Administration |
| System | /health | Health endpoint, restricted or minimal response |

5.2 Shared Page Framework

UI-001 — Header and menu [Must]

Every public page shall display a top section containing the site identity and navigation links for Main Feed, Contact and Reviews. The header content shall be configurable without editing application source files.

UI-002 — Presentation/body area [Must]

The middle section shall hold page-specific content. On the Main Feed this area shall contain presentation cards; on Contact it shall contain the contact form; on Reviews it shall contain review content.

UI-003 — Footer [Must]

Every public page shall display a footer for links, legal details, contact details or other configured information. Footer content shall be editable by an administrator.

UI-004 — Responsive behaviour [Must]

The layout shall adapt to desktop, tablet and mobile widths without horizontal scrolling. Media shall preserve aspect ratio and remain within the content column.

UI-005 — Accessibility [Must]

Navigation, forms, media controls and language selection shall be keyboard accessible. Images shall support alternative text and videos shall expose controls and captions where available.

6. Main Feed Functional Requirements

FEED-001 — Database-fed list [Must]

The Main Feed shall retrieve presentation entries from the database, ordered by configured display date and then source publication date, newest first by default.

FEED-002 — Instagram-style card [Must]

Each entry shall display an image, image carousel, video or video thumbnail in the upper area and post text/caption beneath it. The visual treatment may resemble an Instagram post but must not falsely imply endorsement or reproduce protected branding in a misleading way.

FEED-003 — Source click-through [Must]

Clicking or activating the primary media shall open the stored canonical Instagram post URL. The link shall open in a new tab and use appropriate rel security attributes.

FEED-004 — Media types [Must]

The system shall support at minimum a single image, a single video and a video thumbnail. Carousel support may be implemented as multiple media records linked to one post.

FEED-005 — Text rendering [Must]

Post text shall preserve paragraphs and safe links while escaping or sanitising unsafe HTML. Long text may be collapsed with a “Read more” control.

FEED-006 — Pagination [Must]

The feed shall use pagination or incremental loading to avoid loading the complete database on first request. Page size shall be configurable, with a proposed default of 12 entries.

FEED-007 — Publication control [Must]

Only entries with status Published and a publish date not in the future shall be visible publicly. Hidden, Draft, Error and Archived records shall not appear.

FEED-008 — Empty/error state [Must]

When no content is available, the page shall show a configurable message. Data retrieval failure shall show a user-safe message and write detailed diagnostics to application logs.

7. Contact Page Functional Requirements

| Field | Type | Required | Validation |
| --- | --- | --- | --- |
| Topic | Text or select | Yes | 1–150 characters; optional configured choices. |
| Body | Multiline text | Yes | 10–5,000 characters by default. |
| Email | Email | Yes | Valid email format; maximum 254 characters. |
| Phone number | Telephone | No | International-friendly characters; 7–30 characters when supplied. |
| Submit | Button | — | Disabled while request is processing; prevents duplicate submission. |

CON-001 — Submission delivery [Must]

A valid submission shall be sent to the configured recipient email address. The sender address shall be a domain-controlled application mailbox; the visitor email shall be placed in Reply-To.

CON-002 — Confirmation [Must]

After successful submission, the user shall receive an on-page success message in the active language. The form shall not expose the destination email address unless it is intentionally included in site content.

CON-003 — Abuse prevention [Must]

The contact endpoint shall include rate limiting, CSRF protection where relevant, bot protection such as a honeypot or challenge, and server-side validation.

CON-004 — Failure handling [Must]

If email delivery fails, the system shall retain a non-sensitive failure event and display a neutral retry message. It shall not claim success before delivery is accepted by the mail service.

CON-005 — Privacy [Must]

The contact page shall link to or display a privacy notice explaining how submitted data is used and retained.

8. Reviews Page Functional Requirements

REV-001 — Review list [Must]

The Reviews page shall display administrator-approved review records including reviewer display name, review text, optional rating, optional source, and publication date.

REV-002 — Management [Must]

Administrators shall be able to create, edit, publish, hide and reorder reviews through the configuration interface.

REV-003 — Future submission option [Must]

A public review submission form is not required for the initial release. If added later, submissions shall enter a moderation queue and never publish automatically.

9. Protected Configuration Page

The configuration page shall not appear in the public menu or sitemap. Hiding the route is not a security control; access must require authentication and authorisation. The route slug should be configurable, but security shall rely on strong credentials, session controls and optional network restrictions or multi-factor authentication.

ADM-001 — Authentication [Must]

The page shall require an administrator account with securely hashed password. Sessions shall use secure, HttpOnly and SameSite cookies and shall expire after configurable inactivity.

ADM-002 — Menu section editor [Must]

An administrator shall be able to edit the shared menu/header markup. The implementation shall use a sanitised rich-text/HTML editor or a controlled component editor. Scripts, event-handler attributes, iframes and unsafe URLs shall be removed or rejected.

ADM-003 — Theme editor [Must]

An administrator shall be able to select or upload a background image and configure background colours, text colours, accent colours and approved fonts. A preview shall be available before saving where practical.

ADM-004 — Database search [Must]

An administrator shall be able to search presentation entries by caption text, source post ID, source URL, status and date range. Results shall be paginated.

ADM-005 — Database editing [Must]

An administrator shall be able to edit display text, alternative text, source URL, media reference, language-specific text, display date, sort priority and publication status. Original imported values should be retained or auditable.

ADM-006 — Footer editor [Must]

An administrator shall be able to edit footer/bottom-page markup and add links. The same sanitisation policy as the header editor shall apply.

ADM-007 — Contact recipient [Must]

An administrator shall be able to change the destination email address used by the contact form. The system shall validate format and may require confirmation or test delivery before activation.

ADM-008 — Language mode [Must]

An administrator shall be able to enable or disable the English and French locales, set the default language, and edit fixed text translations. Public users shall be able to switch between enabled languages.

ADM-009 — Audit trail [Must]

Configuration changes and content edits shall record administrator, timestamp, entity, operation and a safe summary of changed fields.

ADM-010 — Safe media upload [Must]

Uploaded backgrounds and replacement media shall be validated by actual file type, restricted in size, renamed by the application and stored outside executable paths.

10. English and French Localisation

L10N-001 — Language switch [Must]

A visible EN/FR switch shall be available on all public pages. The choice shall persist using a cookie or user preference and may fall back to browser language on first visit.

L10N-002 — Interface resources [Must]

Navigation labels, form labels, validation messages, success/error messages, accessibility text and fixed page headings shall be sourced from translation resources rather than hard-coded in templates.

L10N-003 — Content fields [Must]

Configurable content, reviews, header and footer content shall support separate English and French values. A fallback rule shall be applied when one translation is blank.

L10N-004 — Imported posts [Must]

The original Instagram caption shall be retained unchanged. The administrator may add a separate English or French display translation. Automatic translation is optional and outside initial scope.

L10N-005 — URLs and metadata [Must]

Each locale shall expose appropriate page language metadata. Localised URLs are optional; if used, canonical and alternate-language metadata shall prevent duplicate indexing.

11. Instagram Ingestion Agent

The agent shall execute as a separate service account and runtime outside the public website file structure. It shall be granted only the database and media-storage permissions necessary to import data. The website shall not call an endpoint that returns Instagram credentials.

11.1 Function 1 — Add Secure Login Details

AGT-001 — Credential entry [Must]

The agent shall provide an administrative command or secured interface to add or update credentials for the configured Instagram account.

AGT-002 — Encryption [Must]

Credentials shall be encrypted at rest using an operating-system secret store, secrets manager or an encryption key held separately from the encrypted credential record. Plaintext credentials shall not be written to logs, command history or database audit fields.

AGT-003 — Validation [Must]

The credential entry process shall validate that authentication can be completed, without displaying the password or reusable session material.

11.2 Function 2 — Retrieve Secure Login Details

AGT-004 — Restricted retrieval [Must]

Only the ingestion runtime identity shall be able to decrypt or retrieve credentials. Retrieval shall occur just in time and values shall remain in memory only for the required operation.

AGT-005 — No export [Must]

The agent shall not offer a function that prints or exports plaintext credentials. “Retrieve” means supplying them internally to the authentication operation.

11.3 Function 3 — Scheduled Import Job

AGT-006 — Schedule [Must]

The import job shall be invokable by the operating system scheduler or orchestration platform. The frequency shall be configurable; a proposed default is every 6 hours.

AGT-007 — Post retrieval [Must]

The job shall retrieve new and recently changed posts from the authorised Instagram account using an approved integration method. It shall capture a stable source post identifier, canonical URL, publication timestamp, caption/comment text, media type and media references.

AGT-008 — Incremental processing [Must]

The job shall store a high-water mark or per-post import state and avoid unnecessary reprocessing. A controlled look-back window shall detect edits to recent posts.

AGT-009 — Idempotent upsert [Must]

Running the job multiple times for the same source post shall update the existing record rather than creating duplicates.

AGT-010 — Media handling [Must]

Where permitted, the job shall download media or thumbnails into controlled storage, verify file type and size, and link media records to the presentation item. Failed downloads shall not corrupt an existing valid record.

AGT-011 — Default publication policy [Must]

New imported posts shall either publish automatically or enter Draft according to a configuration setting. The recommended secure editorial default is Draft until the owner approves automatic publication.

AGT-012 — Logging and metrics [Must]

Each run shall record start/end time, account identifier, number read, inserted, updated, skipped and failed, plus a redacted error summary.

AGT-013 — Retries [Must]

Transient failures shall use bounded retries with backoff. Authentication failure shall stop the run and create a high-priority operational alert without revealing credentials.

AGT-014 — Deletion policy [Must]

If a source post is deleted or becomes unavailable, the agent shall mark it Source unavailable and apply a configured action: keep published, hide automatically or request review. Hard deletion shall not be automatic by default.

12. Data Requirements

| Entity | Key fields |
| --- | --- |
| users | id, username/email, password_hash, role, enabled, last_login_at, created_at, updated_at |
| site_settings | key, value/type or JSON, locale, updated_by, updated_at |
| presentation_items | id, source_platform, source_account_id, source_post_id, source_url, source_published_at, display_date, status, sort_priority, original_text, text_en, text_fr, alt_text_en, alt_text_fr, import_hash, created_at, updated_at |
| media_assets | id, presentation_item_id, type, storage_path, thumbnail_path, mime_type, width, height, duration, sequence, checksum, created_at |
| reviews | id, reviewer_name, rating, source, source_url, text_en, text_fr, status, sort_priority, published_at |
| contact_delivery_events | id, submitted_at, delivery_status, recipient_version/reference, provider_message_id, error_code; avoid storing body unless required |
| agent_runs | id, started_at, finished_at, status, read_count, insert_count, update_count, skip_count, failure_count, redacted_error |
| audit_events | id, user_id, action, entity_type, entity_id, changed_fields_summary, timestamp, source_ip or session reference |

12.1 Data Rules

Combination of source_platform, source_account_id and source_post_id shall be unique.

Database timestamps shall be stored in UTC and rendered in the configured site timezone.

Public queries shall exclude non-published statuses at the query layer, not only in templates.

Media paths shall not accept user-controlled traversal sequences or executable extensions.

HTML-capable fields shall store sanitised content or a safe structured representation.

Database migrations shall be versioned and reversible where practical.

13. Security and Privacy Requirements

| ID | Requirement |
| --- | --- |
| SEC-001 | All public and administrative traffic shall use HTTPS. HTTP shall redirect to HTTPS. |
| SEC-002 | Administrator passwords shall use a modern adaptive hash such as Argon2id or bcrypt with appropriate cost. |
| SEC-003 | Administrative login shall be rate-limited and protected against credential stuffing. Optional MFA should be supported or planned. |
| SEC-004 | The web application and agent shall use separate least-privilege database credentials. |
| SEC-005 | Instagram credentials shall never be present in public web files, source control, client-side code, application logs or browser storage. |
| SEC-006 | All editable HTML shall be sanitised using an allowlist. Content Security Policy shall block inline scripts unless explicitly required and nonce-controlled. |
| SEC-007 | Forms and state-changing admin actions shall have CSRF protection, input validation and output encoding. |
| SEC-008 | Secrets shall be rotated without rebuilding the website. Backup copies containing secrets shall remain encrypted. |
| SEC-009 | Administrative and agent events shall be logged without sensitive values. Logs shall have retention and access controls. |
| SEC-010 | Dependencies shall be pinned, scanned and updated through a controlled process. |
| SEC-011 | The solution shall provide a configurable privacy notice, cookie notice where required, and a retention policy for contact information and logs. |
| SEC-012 | The implementation shall comply with applicable Instagram/Meta platform terms, API permissions and data-use restrictions. |

14. Non-Functional Requirements

| Category | Target / requirement |
| --- | --- |
| Performance | Initial public page response should be under 2 seconds at the server under normal expected load, excluding unusually large media; images shall be resized and lazily loaded. |
| Availability | Target 99.5% monthly availability for the public site, excluding planned maintenance, unless a different service level is agreed. |
| Scalability | The application shall support at least 10,000 presentation records without requiring a redesign; all list queries shall be indexed and paginated. |
| Compatibility | Current major versions of Chrome, Safari, Firefox and Edge; responsive support for common iOS and Android browsers. |
| Accessibility | Aim for WCAG 2.2 AA for public pages and core administration flows. |
| Maintainability | Configuration shall be externalised; code, database migrations and agent shall be version controlled; environments shall be reproducible. |
| Backup | Database and managed media shall be backed up on a documented schedule. Restore procedures shall be tested. |
| Observability | Health checks, structured application logs, agent run records and alerting for repeated import or email delivery failures. |
| SEO | Public pages shall have configurable titles/descriptions, canonical URLs, social preview metadata and a sitemap excluding the protected configuration route. |

15. Core User and System Workflows

15.1 Visitor Views a Post

Visitor opens Main Feed.

System determines locale and retrieves the first page of Published presentation items.

System renders media, caption and accessible controls.

Visitor activates the media.

System opens the canonical Instagram URL in a new browser tab.

15.2 Visitor Sends a Contact Request

Visitor opens Contact and completes Topic, Body, Email and optional Phone number.

Client and server validate input and abuse controls.

Server sends the message to the currently configured recipient with the visitor email as Reply-To.

System records delivery outcome without exposing sensitive configuration.

Visitor receives localised confirmation or retry guidance.

15.3 Administrator Edits an Imported Item

Administrator authenticates and opens database search.

Administrator locates an item by text, date, status or source identifier.

Administrator edits display text/translation, media metadata, source URL or publication status.

System validates and saves the change.

System records an audit event and the public feed reflects the saved Published version.

15.4 Scheduled Agent Import

Scheduler launches the agent with a dedicated service identity.

Agent retrieves credentials internally and authenticates.

Agent reads new/recent posts and normalises fields.

Agent validates/stores media and performs idempotent database upserts.

Agent records metrics and exits with a meaningful status code.

Monitoring alerts only when configured thresholds or repeated failures are reached.

16. Acceptance Criteria

| Ref | Acceptance criterion |
| --- | --- |
| AC-01 | The public header contains working links to Main Feed, Contact and Reviews on desktop and mobile. |
| AC-02 | At least one image item and one video/thumbnail item can be read from the database and displayed as cards with text below. |
| AC-03 | Activating feed media opens the correct stored Instagram post URL in a new tab. |
| AC-04 | Only Published items are visible publicly; changing an item to Hidden removes it from the feed. |
| AC-05 | The contact form enforces required fields, rejects invalid input and delivers to the configured address. |
| AC-06 | A user without valid credentials cannot access any configuration function or underlying admin API. |
| AC-07 | An authorised administrator can edit header and footer content, and unsafe script content is rejected or removed. |
| AC-08 | An administrator can change theme background, colours and approved font and see the change on public pages. |
| AC-09 | An administrator can search and edit presentation records and review records. |
| AC-10 | An administrator can change and validate the contact destination email address. |
| AC-11 | Switching EN/FR changes all fixed interface labels and uses the correct configured content translation/fallback. |
| AC-12 | The agent stores credentials encrypted and no plaintext credential appears in web files, logs or the application database. |
| AC-13 | Two agent runs against the same source posts do not create duplicate presentation records. |
| AC-14 | Agent failures are logged with redacted details and do not remove previously valid published content. |
| AC-15 | The protected route is excluded from public navigation and sitemap, and authentication/session controls pass security testing. |
| AC-16 | Backup and restore of database and media are demonstrated in a test environment. |

17. Deployment and Operations

Use separate development, test/staging and production environments.

Run the public web application, database and agent under separate service identities or containers.

Mount public media as non-executable and avoid sharing the agent credential directory with the web container.

Use environment variables or a secrets manager for database/mail credentials, but do not expose secrets through client-side build variables.

Run database migrations as an explicit deployment step with rollback planning.

Configure scheduler overlap protection so a new agent run does not start while a previous run is active.

Monitor disk usage because downloaded video can grow quickly; configure retention and media optimisation.

Document manual credential rotation, forced agent run, import pause, item republish and disaster recovery procedures.

18. Open Questions

| ID | Question | Impact |
| --- | --- | --- |
| Q-01 | Should newly imported posts publish automatically or require approval? | Defines editorial workflow and agent default status. |
| Q-02 | Does “comment text details” mean the post caption only, selected comments, or all public comments? | Affects permissions, schema, privacy and import volume. |
| Q-03 | Should imported video be stored locally, embedded, or represented by a thumbnail linked to Instagram? | Affects storage, bandwidth and platform compliance. |
| Q-04 | Will Reviews be manually authored, imported from another service, or submitted by visitors? | Determines page and moderation requirements. |
| Q-05 | Should administrators have one shared account or named individual accounts? | Named accounts are required for meaningful audit history. |
| Q-06 | Is automatic translation of Instagram text required? | Adds external service, cost and quality considerations. |
| Q-07 | What hosting platform, technology stack and email provider will be used? | Required for detailed technical design and deployment specification. |
| Q-08 | What retention period applies to contact submissions, logs and removed Instagram posts? | Required for privacy policy and storage design. |
| Q-09 | Is Instagram Graph API eligibility available for the account type? | Determines supported and compliant ingestion approach. |
| Q-10 | Is multi-factor authentication mandatory for the configuration page? | Recommended for production administration. |

Appendix A — Outline-to-Specification Traceability

| Original outline item | Covered by |
| --- | --- |
| Top menu: Main Feed, Contact, Reviews | Sections 5 and 16 |
| Contact: topic, body, email, phone and submit | Section 7 |
| Database-fed Instagram-style presentation section | Sections 6 and 12 |
| Media links to Instagram post URL | FEED-003 |
| Hidden/password-protected config page | Section 9 and Section 13 |
| Edit menu HTML | ADM-002 |
| Change background, colours and fonts | ADM-003 |
| Search/edit database entries | ADM-004 and ADM-005 |
| Edit bottom/footer HTML and links | ADM-006 |
| Edit contact form posting email address | ADM-007 |
| Switch site text between English and French | Section 10 |
| Agent: add credentials | Section 11.1 |
| Agent: retrieve credentials internally | Section 11.2 |
| Agent: scheduled post/text import | Section 11.3 |
| Agent outside web file structure | Section 4 and Section 11 |
