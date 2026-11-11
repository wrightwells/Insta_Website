"""Packaged EN/FR interface resources. Captions never pass through these."""

COPY = {
    "en": {
        "contact_form_title": "Send us a message", "contact_send": "Send message",
        "contact_sent": "Thank you. Your message has been sent.",
        "contact_failed": "We cannot send messages right now. Please use the contact details on this page or try again later.",
        "contact_expired": "This form has expired. Reload the page and try again.",
        "contact_limited": "Too many messages. Please wait 15 minutes before trying again.",
        "contact_privacy": "Your email, mobile number and message are used to respond to your enquiry and are sent to our contact mailbox.",
        "contact_preview": "Contact form submissions are disabled in this preview.",
        "theme_preview_notice": "Theme preview — these settings have not been saved.", "theme_preview_back": "Back to Appearance",
        "feed": "Main feed", "contact": "Contact", "reviews": "Reviews", "privacy": "Privacy policy",
        "skip": "Skip to content", "language": "Language", "navigation": "Main navigation",
        "journal": "THE JOURNAL", "feed_title": "Moments worth keeping.",
        "source": "View on Instagram", "next": "Older stories", "back": "Back to the latest",
        "reviews_title": "A few kind words.", "reviews_empty": "Reviews will appear here once they are published.",
        "contact_title": "Let’s get in touch.",
        "contact_empty": "Contact details will appear here soon.",
        "contact_unavailable": "The contact form is not available yet. Please check back later.",
        "unavailable_title": "We’ll be back soon.",
        "unavailable": "This page is temporarily unavailable. Please try again later.",
        "not_found": "We couldn’t find that page.", "invalid_cursor": "This page link is invalid. Return to the latest stories.",
        "reference": "Reference", "rating": "Rating out of 5", "media_missing": "Image currently unavailable",
    },
    "fr": {
        "contact_form_title": "Envoyez-nous un message", "contact_send": "Envoyer le message",
        "contact_sent": "Merci. Votre message a été envoyé.",
        "contact_failed": "L’envoi de messages est indisponible. Utilisez les coordonnées sur cette page ou réessayez plus tard.",
        "contact_expired": "Ce formulaire a expiré. Rechargez la page et réessayez.",
        "contact_limited": "Trop de messages. Veuillez patienter 15 minutes avant de réessayer.",
        "contact_privacy": "Votre adresse e-mail, numéro de mobile et message servent à répondre à votre demande et sont envoyés à notre messagerie.",
        "contact_preview": "L’envoi du formulaire est désactivé dans cet aperçu.",
        "theme_preview_notice": "Aperçu du thème — ces paramètres ne sont pas enregistrés.", "theme_preview_back": "Retour à l’apparence",
        "feed": "Fil principal", "contact": "Contact", "reviews": "Avis", "privacy": "Confidentialité",
        "skip": "Aller au contenu", "language": "Langue", "navigation": "Navigation principale",
        "journal": "LE JOURNAL", "feed_title": "Des moments à garder.",
        "source": "Voir sur Instagram", "next": "Histoires précédentes", "back": "Les dernières histoires",
        "reviews_title": "Quelques mots doux.", "reviews_empty": "Les avis apparaîtront ici après leur publication.",
        "contact_title": "Restons en contact.",
        "contact_empty": "Les coordonnées seront bientôt disponibles ici.",
        "contact_unavailable": "Le formulaire de contact n’est pas encore disponible. Veuillez revenir plus tard.",
        "unavailable_title": "Nous revenons bientôt.",
        "unavailable": "Cette page est temporairement indisponible. Veuillez réessayer plus tard.",
        "not_found": "Cette page est introuvable.", "invalid_cursor": "Ce lien est invalide. Revenez aux dernières histoires.",
        "reference": "Référence", "rating": "Note sur 5", "media_missing": "Image momentanément indisponible",
    },
}


def localised(obj, field: str, locale: str, default: str) -> str:
    return getattr(obj, f"{field}_{locale}") or getattr(obj, f"{field}_{default}") or getattr(obj, f"{field}_{'fr' if default == 'en' else 'en'}")
