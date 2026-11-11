# Instagram connection and website imports

The owner selected the working `instagrapi` integration in November 2026. It
replaces the previous Meta developer-app/OAuth/token setup. The old token CLI and
Graph client are removed. No Meta app ID, developer token or OAuth callback is
used by this website.

Open **http://localhost:8001/manage-local/instagram/** and sign in with your normal
website owner account. The public website continues on http://localhost:8000/
and the existing private Tailscale address.

1. Save your Instagram username/password. Leave the password blank to retain it
   for the same username. No Instagram request is made by saving alone.
2. Select **Connect and verify**. If requested, enter a fresh two-factor or backup
   code and connect again within five minutes. Resolve other challenges directly
   in Instagram. A saved session may expire; the page shows when it was verified.
3. Choose **1–12 recent posts**, then **Load recent posts**. Submit once and wait;
   images can take a few minutes to download and validate.
4. Valid new posts publish immediately. Visit **Stories** to edit or hide them.
   Re-importing updates source captions/media without creating duplicate posts.
   Owner display captions, ordering, publication decisions and image overrides
   remain intact. Failed downloads leave existing good posts untouched.

Imports download every carousel image and use a video's cover image. The public
feed displays the locally hosted PNG images and original caption, with links to
the original post. Full video playback and official embeds are not part of this
increment. Neither interface language translates the caption.

## Runtime boundary

The owner page is part of the existing authenticated, CSRF-protected EN/FR
administration app. Passwords/codes are submitted transiently to that owner app
and forwarded to an isolated Instagram service. They are not kept in Django
sessions, the website database, history, audit logs, page defaults or responses.
The public runtime has neither Instagram dependencies nor a credential/control
volume. The separate agent encrypts the password and reusable session with its
key held on a separate volume.

The agent has no host port and is on a dedicated Docker network shared only with
admin. A separate private control key authenticates admin-to-agent calls. That
control key can request account changes and imports; protect it as a capability.
The control volume is read-only in admin. It contains no Instagram password,
Instagram session or encryption key. Agent endpoints never return those values.
The public website connects only to its existing database/public media views.

Images are downloaded only from cached first-party CDN references, checked for
size/type/dimensions, re-encoded to metadata-free PNGs, and stored within the
website's existing quota. Published-only database views gate public image delivery.
The normalized source snapshot and imported media IDs support future extension;
original source revisions and owner audit entries are retained on changes.

One owner import at a time is enforced through a database lease. A crashed
import's lease expires after an hour. Imports commit per post, so earlier valid
posts survive a later failure. This is a manual recent-post import, not a complete
archive, deletion detector or scheduled synchronization service. Pinned/ranked
posts can affect the recent listing.

The integration remains unofficial. Instagram may reject a login, expire a session,
restrict requests or require manual verification. There is no retry loop for
account restrictions and no automatic fresh password login during reads.

See [operator instructions](instagram-operator-access.md) for deployment and
storage, and [the retained PoC](instagram-private-api-poc.md) for low-level adapter
functions. Historical specification documents retain superseded proposals for
provenance; this owner-selected integration is the current implementation.

Imports have a ten-minute batch time budget (plus one in-flight bounded request)
and a 50 MiB downloaded-image budget per post. If a large batch fails, load fewer
posts. Changes committed before a timeout remain available.
