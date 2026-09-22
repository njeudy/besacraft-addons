{
    "name": "Besacraft — Site Theme",
    "version": "18.0.1.0.0",
    "license": "LGPL-3",
    "author": "Nicolas JEUDY",
    "website": "https://besacraft.fr",
    "category": "Besacraft",
    "summary": "Notice-style skin for besacraft.fr: palette, type scale, header and footer",
    # Pas un `theme_*` au sens Odoo, et c'est voulu : installer un thème COPIE ses vues dans
    # la base, et la copie cesse alors de suivre le module -- une correction poussée ici ne
    # serait jamais visible en ligne. Ici tout passe par des variables SCSS et de l'héritage
    # de vues, donc une mise à jour de module suffit.
    "depends": ["website", "besacraft_builds"],
    "data": [
        "views/layout.xml",
        "views/menus.xml",
    ],
    "assets": {
        # Les variables primaires sont lues AVANT Bootstrap : c'est le seul endroit d'où on
        # peut changer les couleurs et les fontes de tout le site plutôt que de les répéter.
        # En APPEND, pas en prepend : le site pose ses propres valeurs d'éditeur dans ce
        # même bundle, et ce qui passe avant se fait écraser sans bruit -- le module semble
        # installé et la page garde ses fontes d'origine.
        "web._assets_primary_variables": [
            "besacraft_theme/static/src/scss/primary_variables.scss",
        ],
        "web.assets_frontend": [
            "besacraft_theme/static/src/scss/theme.scss",
        ],
    },
    "installable": True,
    "application": False,
}
