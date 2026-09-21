{
    "name": "Besacraft — Build Catalogue",
    "version": "18.0.1.0.0",
    "license": "LGPL-3",
    "author": "Nicolas JEUDY",
    "website": "https://besacraft.fr",
    "category": "Besacraft",
    "summary": "Build tutorials: catalogue, layers and 3D viewer",
    "depends": ["besacraft_base", "product", "sale", "website"],
    "data": [
        "security/ir.model.access.csv",
        "data/besacraft_serie_data.xml",
        "views/besacraft_serie_views.xml",
        "views/besacraft_build_views.xml",
        "views/menus.xml",
        "views/website_catalogue.xml",
        "views/website_tuto.xml",
    ],
    "assets": {
        "web.assets_frontend": [
            "besacraft_builds/static/src/scss/notice.scss",
        ],
    },
    "installable": True,
    "application": True,
}
