# Documentation

Use these guides for the current application. Older proposals and implementation
snapshots are separated into the archive so they are not mistaken for setup steps.

| Guide | Contents |
| --- | --- |
| [Installation](../INSTALL.md) | Fresh Docker/PostgreSQL or local Python setup, owner login, configuration and upgrades |
| [Development](development.md) | Source layout, tests, migrations, translations and maintenance commands |
| [Instagram connection](instagram-connection.md) | Owner login/MFA and loading recent posts into the website |
| [Instagram operator setup](instagram-operator-access.md) | Isolated service, credential volumes and local agent setup |
| [Contact email](contact-email.md) | SMTP settings, enquiry delivery, private storage and abuse controls |
| [Site policy](site-policy.md) | Full-text editor, shared contact email, preview, history and policy-only publication |
| [SEO and discovery](site-discovery.md) | Search/social metadata, examples, fallback values and business details |
| [Standalone Instagram PoC](instagram-private-api-poc.md) | Retained diagnostic tool; not required for normal website operation |
| [Archive](archive/README.md) | Original requirements, source Word document and historical decisions |

The current implementation and later owner instructions take precedence over
superseded proposals in the archive. The default installation is local-only;
installation does not publish the website or alter Tailscale routing.
