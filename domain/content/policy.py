"""Editable policy defaults, safe placeholders and plain-text section rendering."""
import re
from datetime import date

DEFAULT_POLICY_EMAIL = "email@site.eu"
DEFAULT_POLICY_DATE = date(2026, 11, 11)
DEFAULT_POLICY_BODY = """This policy covers {site_name}, an owner-operated website and its Instagram account-access tool. {operator_name}'s contact for privacy questions and data-deletion requests is {contact_email}.

## Current service

The website is currently a private development preview, accessible through the owner's Tailscale network. Instagram account authorization is being configured. Automatic Instagram importing is not enabled. This policy describes current processing and the limited account access being set up; it does not claim a completed Instagram connection.

## Instagram account information

When the account owner authorizes the integration, the operator tool uses an Instagram Login access token to verify the authorized account's Instagram user ID and username, and to read a small sample of its posts, including captions, post IDs, media types, timestamps and post links. This access is used to verify the connection and prepare the owner's posts for display on {site_name}. The requested permission is instagram_business_basic.

The current verification tool stores the account ID, username, API version, verification times, sample count and access token in an encrypted record. It does not retain or print the sample captions or complete API responses. A successful token refresh also records the expiry reported by Instagram. Tokens and their encryption key are stored separately outside the website containers.

The integration does not request access to private messages or comment management and does not publish posts back to Instagram. Instagram passwords are entered only on Instagram's own service, never into {site_name}.

## Website content and visitors

The website stores content entered by the operator, including captions, images, published reviews and site settings. When Instagram importing is implemented, this policy will be updated to describe its storage and publication behavior before that feature is enabled.

The website uses a language-preference cookie lasting up to 30 days. The local owner portal uses authentication and security cookies for administration. There are currently no advertising or analytics scripts, Instagram embeds, or visitor account registration. When email delivery is enabled, the contact form sends your email address, mobile number and message to the site’s configured contact mailbox so the operator can respond. The website does not store the contents of enquiries. The mail provider and recipient mailbox process and retain the delivered email according to their settings.

Hosting, proxy and application components may process technical request information, such as network addresses, request paths, timestamps and errors, to deliver the service and investigate faults or misuse. Local application security records include administrative activity and sign-in protections. Automatic deletion periods for preview infrastructure logs have not yet been configured.

The contact form uses a security cookie, signed submission identifiers and pseudonymous rate counters to prevent forgery, duplicate sends and abuse. These records contain delivery state and timestamps, not enquiry text or contact details. Security cleanup removes expired rate counters and delivery records older than seven days when the operator runs the cleanup command.

## Sharing and external services

The operator tool communicates with Meta/Instagram to verify authorized access and refresh tokens. Tailscale provides private website access. Opening an Instagram post link takes you to Instagram, which applies its own privacy practices. Emailing the contact address uses your email provider and the operator's Outlook mailbox. {site_name} does not sell account data or use it for advertising.

## Retention and access removal

The operator keeps the account-access record while the authorized integration is in use, until it is replaced or removed. Website content remains stored until the operator removes it. A fixed automatic retention schedule for imported content and backups has not been established, and automated importing remains disabled.

The account owner can revoke the app's access through Instagram's Apps and websites settings. Revocation prevents future authorized access but does not itself erase copies already stored by {site_name}.

## Request access, correction or deletion

Email {contact_email} with the subject “{site_name} privacy request” or “{site_name} data deletion”. Identify the Instagram username or website content concerned and describe the request. Do not include passwords, tokens or app secrets.

The operator will review the request, verify authority where needed, and arrange access, correction or deletion of the relevant {site_name}-held information. Deletion can include the stored account-access record and associated website content. Any information that must be retained will be explained in the response. Removing {site_name} data does not delete the original posts or account on Instagram.

## Policy changes

This page will be updated when the service's data processing changes, including changes to contact delivery, automatic importing or embeds. The date above identifies this version."""

def default_policy_date():
    return DEFAULT_POLICY_DATE


POLICY_FIELDS = ("title", "site_name", "operator_name", "contact_address", "updated_on", "body")


def policy_context(policy, *, contact_email=None):
    if contact_email is None:
        contact_email = getattr(policy, "contact_email", DEFAULT_POLICY_EMAIL)
    values = {"site_name": policy.site_name, "operator_name": policy.operator_name or "The site operator",
        "contact_email": contact_email, "contact_address": policy.contact_address}
    def expand(text):
        return re.sub(r"\{(site_name|operator_name|contact_email|contact_address)\}", lambda match: values[match[1]], text)
    sections = []
    for block in re.split(r"\n\s*\n", policy.body.strip()):
        for heading, text in [(block.startswith("## "), block[3:] if block.startswith("## ") else block)]:
            sections.append({"heading": heading, "text": expand(text)})
    return {"policy": policy, "policy_contact_email": contact_email, "policy_title": expand(policy.title), "policy_sections": sections}
