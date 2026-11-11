# Contact enquiries and email delivery

The form remains hidden until delivery is configured and enabled with a real
recipient; the fresh-site placeholder `email@site.eu` does not enable sending.

The public Contact page retains the site's contact details and adds required email,
mobile number and message fields. Messages are emailed to the public email address
saved in **manage-local → Contact**. The website does not retain enquiry contents.

In the **Email delivery** section of that page:

1. Enter the SMTP hostname and port supplied by your email provider.
2. Choose STARTTLS (normally 587), SSL/TLS (normally 465), or an unauthenticated
   local mail server's security setting.
3. Set a sender address your provider permits, plus its SMTP username and password
   or application password. Visitor addresses are used as Reply-To, not as From.
4. Enable delivery and save. Also save the public recipient email in Contact details.

A blank password preserves the saved password. The explicit removal checkbox clears
it. Passwords are never returned to the editor or written into audit history.
The form confirms success only when the mail backend accepts a message. Final inbox
delivery still depends on the provider. No email is sent just by saving settings.

SMTP settings live in `CONTACT_MAIL_SETTINGS_FILE`, outside the source and static
mounts. Docker uses `/var/lib/contact-mail/smtp.json` on the `contact-mail` volume;
the file is mode 0600 and the directory is mode 0700. The owner portal can write
this volume; public web services mount it read-only. Back it up as private credentials.
Local Python development defaults to `~/.local/share/fieldnotes-mail/smtp.json`.

Submissions require CSRF protection and a signed, browser-bound form token. The
honeypot and shared limit of five attempts per IP address per 15 minutes help bound
abuse. Delivery IDs prevent resending a successful form on refresh or duplicate POST.
Only delivery state/timestamps and pseudonymous rate counters are stored in the
website database. `manage.py cleanup_security` expires rate counters and removes
delivery records older than seven days; schedule this operator command as needed.

Automated tests use Django's in-memory mail backend and synthetic addresses; they
never send external email. Theme previews disable contact submissions.
