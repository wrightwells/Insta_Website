> Historical record. This document describes an earlier design or implementation;
> use the [current documentation](../../README.md) and [installation guide](../../../INSTALL.md) for current behaviour.

## Current owner amendment — November 2026

The owner approved the working `instagrapi` prototype and requested its integration
into website settings, replacing Meta OAuth/developer tokens. The owner page now
supports encrypted account configuration, verification/MFA and loading recent
posts into the public feed. Images are downloaded; video posts use cover images.
Valid new posts publish automatically; owner overrides and hidden status survive
re-imports. This explicitly supersedes the authentication recommendations and
no-unofficial-integration selection below. No scheduled polling is enabled.
See [current connection](../../instagram-connection.md) and [operator setup](../../instagram-operator-access.md).

---

# Owner decisions and specification amendments

Recorded 19 October 2026 from the owner's answers. These decisions amend the
original functional specification and supersede conflicting proposed defaults in
version 0.1 of the technical design. The source DOCX is retained unchanged.
Local development began on 20 October 2026. Account integration remains unresolved;
see the current [Instagram connection guide](../../instagram-connection.md). No conversion,
Meta consent or credential provisioning has been performed by this project.

| Area | Confirmed decision | Design consequence |
| --- | --- | --- |
| Instagram account | Owner confirmed on 20 October 2026: already Creator or Business; no Meta developer app exists yet | No conversion is needed; App ID 1638533241004940 supplied on 22 October; verify product/account access and HTTPS routing before integration proof |
| Publication | Imports publish automatically | Default policy is automatic publication after input/media validation, with no approval queue for valid new posts; administrator may still hide/edit them |
| Imported text | Post captions only; no messages | No DM or comment ingestion; request no messaging/comment-management permissions |
| Media | Embed image/video if possible; otherwise save locally | Prefer supported official embeds; download permitted source assets when embedding is unavailable, validate and serve from managed storage |
| Deployment | Docker; owner manages infrastructure including SSL | Provide container/Compose deployment design and persistent volumes; consume an owner-managed HTTPS reverse proxy with explicitly trusted proxy headers |
| Site language | Multilingual site; posts stay in original language | Translate site interface/configurable site copy; preserve original caption for every locale; no post translation requirement or language-dependent caption substitution |
| Administration | One admin; MFA not required | One owner account with password/session authentication; no Editor-role or MFA feature required initially |

## Authentication recommendation

Owner update on 20 October 2026: the account is already **Creator or Business**,
and subsequently supplied App ID **1638533241004940** on 22 October 2026.
The selected product and API access still need verification. This supersedes the earlier
personal-account/conversion prerequisite. Recommend the **Instagram API with
Instagram Login** authorisation flow for the existing professional account. Meta's official API collection describes
this route as supporting professional accounts and not requiring a linked
Facebook Page. [Meta Instagram Login API collection](https://www.postman.com/meta/instagram/folder/6raa77c/instagram-api-with-instagram-login).

No account conversion is required. The professional-account category is confirmed;
Meta app setup, actual permissions and API access still need verification. A personal
account is not a supported target of the proposed professional API. The official
Facebook Login collection also explicitly excludes consumer accounts.
[Meta API limitations](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api?entity=request-23987686-15c537cd-a773-4b40-a87c-27829e49a439).

Use only the account/media read permissions needed for captions and media; verify
`instagram_business_basic` against the selected API version and actual app setup.
Do not request posting, messages, comment management or insights simply because a
sample collection lists them. Establish and test token refresh/expiry handling
before implementation; do not assume indefinite token validity.

The owner completes consent on Instagram's own page. The operator exchanges and
stores resulting tokens through an agent-only provisioning process. For OAuth,
validate state, exact redirect URI, one-use codes and short-lived provisioning
state; keep the client secret and code exchange on the agent side. If a callback
is required, use an operator-only temporary endpoint isolated from the website;
its hostname/TLS routing is supplied by the owner. Do not route reusable tokens
through the public or administration application. Provisioning encrypts tokens;
the agent uses them in memory and refreshes/rotates them as supported. The website
never receives the Instagram password, access token or app secret.

If the account stays personal, a manual post-URL/embed workflow or an owner-uploaded
export can be considered as a separately agreed alternative. Neither provides the
currently requested scheduled discovery of new posts. An embed displays a known
post; it does not discover a personal account's feed or provide caption ingestion.
No unofficial password/session scraping has been selected.

## Embed and local fallback contract

Store original captions and canonical post URLs in the database regardless of
media presentation. A supported embed is built only from a validated source URL
through a trusted adapter. Never execute arbitrary HTML returned from a provider
or entered by the administrator. Allow only the required official embed script
and frame origins in CSP; header/footer editors remain unable to add scripts or
iframes. Confirm exact provider requirements in an integration proof.

Track media presentation separately: embed, local image, local video, or source
link only. Validated embed descriptors can satisfy publication readiness without
a local binary. When an embed is unavailable and permitted source media can be
retrieved, stage and validate the local fallback before switching presentation.
Do not treat a visitor's blocked script or consent choice as permission to bypass
source restrictions. Some cross-origin embed failures cannot be detected reliably
in the browser: always retain a visible source link; offer any already validated
local fallback. Do not claim every unavailable/deleted post can be downloaded.
A new item with neither usable embed nor valid local media remains in Error/retry
rather than publishing a broken card. Existing good content survives failures.

Official embeds may display provider-controlled captions or other metadata beyond
the custom card's control. The ingestion agent still collects no messages or
comments. Test whether the selected embed presentation meets the owner's desired
caption/media layout before implementation. Site locale never translates or
rewrites the stored original caption.

Embeds contact a third party from the visitor's browser, so update privacy/cookie
text and consent behaviour as required by the final deployment. External embed
availability is outside site control; locally hosted fallbacks retain the
non-executable, publication-gated storage rules.

## Remaining decisions

- App ID 1638533241004940 is supplied. On 23 October 2026 the owner selected MySite at the verified Tailscale hostname root, replacing its Box Storage route; access remains tailnet-only. See [current deployment](../decisions/2026-10-23-tailnet-root.md). See [registration inputs](../../instagram-connection.md). Verify Instagram Login product/client ID, API version, permissions and account access; the isolated OAuth callback remains unimplemented.
- Which SMTP/transactional email service and contact destination will be supplied? These can be deployment settings; secrets are provided outside chat/source control.
- How should Reviews be populated? Manual administration remains a proposal; the owner's answer concerned language only.
- Visual identity, default locale, timezone, retention and initial import range remain proposed in the question register.

The Python/Django/PostgreSQL stack remains a recommendation: Docker hosting does
not imply the owner selected an application language or database framework.
