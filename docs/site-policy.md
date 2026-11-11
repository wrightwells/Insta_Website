# Editable site policy

Open **manage-local → Site policy** (`/manage-local/policy/`) to edit the policy
site name, title, operator/business name, contact address, last-updated date
and complete policy text. The policy uses the email saved in Contact settings. New sites default to
`email@site.eu`; replace that placeholder with your real address. Contact email
changes also republish the policy-only page.
The existing policy is preserved as the initial text.

Use blank lines for paragraphs and `## ` for section headings. The placeholders
`{site_name}`, `{operator_name}`, `{contact_email}` and `{contact_address}` insert
the corresponding fields. Content is rendered as escaped plain text; HTML is not
executed. The full policy preview appears below the editor. Preview does not save;
Save publishes the changes. Previous versions can be reviewed and restored from
the audit history. Policy text is currently English; the owner interface is EN/FR.

The website's `/privacy/` reads the restricted `public_policy` database view.
Each save also atomically writes a rendered HTML artifact to `POLICY_EXPORT_FILE`.
The policy-only service reads this artifact on each request from a read-only
`site-policy` volume; it has no database or credential access. It serves only the
policy, its dedicated stylesheet, and robots.txt. Existing network access remains
unchanged. The website can use the published artifact during database outages.

For initial deployment or to republish an existing saved policy:

```bash
docker compose run --rm --no-deps migration python manage.py export_policy
```

Docker uses `/var/lib/site-policy/privacy.html` for the writer and
`/policy-export/privacy.html` for the policy-only reader. Local Python development
uses `~/.local/share/fieldnotes-policy/privacy.html` unless overridden.
