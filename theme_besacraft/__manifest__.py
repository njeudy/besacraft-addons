{
    "name": "Besacraft — Notice",
    "version": "18.0.1.0.0",
    "license": "LGPL-3",
    "author": "Nicolas JEUDY",
    "website": "https://besacraft.fr",
    # C'est la CATEGORIE qui fait un theme, pas le nom du module -- et un theme est la seule
    # chose qu'Odoo sache n'appliquer qu'a UN site : `_get_active_addons_list` ecarte tous
    # les themes sauf celui affecte au site courant. Un module ordinaire aurait repeint les
    # six sites de cette base, dont la boutique freelance.
    "category": "Theme/Creative",
    "summary": "Notice-style skin for besacraft.fr: palette, type scale, header and footer",
    "depends": ["website"],
    "assets": {
        # En APPEND : le site pose ses propres valeurs d'editeur dans ce meme bundle, et ce
        # qui passe avant se fait ecraser sans bruit.
        "web._assets_primary_variables": [
            "theme_besacraft/static/src/scss/primary_variables.scss",
        ],
        "web.assets_frontend": [
            # Les fontes viennent par URL plutot que par `@import url()` dans le SCSS :
            # l'URL de Google Fonts contient des `;` dans son parametre `wght`, sur lesquels
            # le compilateur SCSS coupe la regle -- ce qui casse le bundle entier.
            "https://fonts.googleapis.com/css2?family=VT323&family=Anonymous+Pro:ital,wght@0,400;0,700;1,400&display=swap",
            "theme_besacraft/static/src/scss/theme.scss",
        ],
    },
    "installable": True,
}
