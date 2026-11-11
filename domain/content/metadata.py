"""Public, editable metadata fields shared by forms, revisions and migrations."""
SEO_FIELDS = tuple(f"seo_{page}_{kind}_{locale}" for page in ("feed", "reviews", "contact") for kind in ("title", "description") for locale in ("en", "fr"))
