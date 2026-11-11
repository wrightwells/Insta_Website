> Historical record. This document describes an earlier design or implementation;
> use the [current documentation](../../README.md) and [installation guide](../../../INSTALL.md) for current behaviour.

# Questions before development

These are unresolved decisions, not implementation instructions. Proposed answers
allow the draft technical design to be reviewed. Confirmed answers are in [owner-decisions.md](owner-decisions.md); remaining proposals are not owner approval. Source Q-01–Q-10 are included below.

## Product and editorial workflow

| ID / source | Question | Proposed answer | Decision needed |
| --- | --- | --- | --- |
| D-01 / Q-01 | Publication policy | **Confirmed:** automatically publish valid imports; retain validation/error handling. | Answered |
| D-02 / Q-02 | Imported text | **Confirmed:** post captions only; no messages or comments. | Answered |
| D-03 / Q-03 | Media handling | **Confirmed:** embed images/videos when supported; otherwise save permitted media locally. | Policy answered; embed/API proof remains |
| D-04 / Q-04 | Are reviews manually managed, externally imported, or visitor submitted? | Manually managed EN/FR testimonials; no public submission form. | Before reviews development |
| D-05 / Q-06 | Language policy | **Confirmed:** multilingual site interface; posts retain original language without caption translation. English default remains proposed. | Post policy answered; default locale open |
| D-06 / FEED-001, ADM-005 | Should priority override date ordering? | Priority descending, effective display date descending, source date then ID as tie-breakers. | Before feed query contract |
| D-07 / AGT-014 | What happens when a source post disappears? | Request review, preserve valid content until confirmed; no automatic hard deletion. | Before reconciliation policy |
| D-08 / scope | How much history should the first import retrieve, and is carousel display required initially? | Last 90 days within permitted API access; first-image display with ordered-media schema ready for optional carousel UI. | Before import sizing and UI |

## Integrations

| ID / source | Question | Proposed answer | Decision needed |
| --- | --- | --- | --- |
| D-09 / Q-09, AGT-001–005 | Authentication/account type | **Updated 22 October 2026:** already Creator or Business; App ID 1638533241004940 supplied. **Recommended:** Instagram Login with agent-only encrypted tokens. | HTTPS route/audience choice, product/client ID, permissions and API proof remain; no conversion prerequisite |
| D-10 / AGT-006, AGT-008 | What import frequency and old-post reconciliation are required? | Every 6 hours; seven-day look-back plus weekly resumable reconciliation within provider limits. | Before scheduler design is final |

## Infrastructure deployment and operations

| ID / source | Question | Proposed answer | Decision needed |
| --- | --- | --- | --- |
| D-11 / Q-07 | Hosting, stack and mail | **Confirmed:** Docker; owner manages infrastructure including SSL. Django/PostgreSQL remain proposed; SMTP/provider/contact destination open. | Hosting answered; stack/mail details open |
| D-12 / NFR, operations | Who operates the site and receives alerts? What traffic, media volume and recovery targets apply? | Named operator; 10 requests/second, 50 concurrent visitors, RPO 24 hours and RTO 4 hours; source availability target retained. | Before deployment sizing and monitoring |

## Security and privacy

| ID / source | Question | Proposed answer | Decision needed |
| --- | --- | --- | --- |
| D-13 / Q-05, Q-10 | Administrator model | **Confirmed:** one admin, no mandatory MFA; password/session controls retained. | Answered |
| D-14 / Q-08 | What retention, residency, privacy notice and deletion rules apply, including email provider and inbox copies? | No app-DB contact bodies; metadata/logs 30 days, audits 12 months, run detail 90 days, encrypted daily backups 30 days; provider/inbox policy owner-approved. | Before storage/production contact processing |

## Web identity and user experience

| ID / source | Question | Proposed answer | Decision needed |
| --- | --- | --- | --- |
| D-15 / UI, ADM-008, L10N | Site name, logo, colours, fonts, contact destination, timezone and EN/FR copy? Must both locales always be enabled? | Neutral placeholders for design; Europe/London provisional; both locales initially, configurable with at least one enabled. | Before visual implementation/publication |
| D-16 / FEED-003–004 | Embed/local interaction | Embed first; separate visible source link; local image/poster links to source with separate video controls. | Owner media policy answered; exact interaction to demonstrate |

Hardware, firmware and native mobile questions do not apply to this website.
