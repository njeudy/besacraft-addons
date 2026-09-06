{
    "name": "Besacraft — ressources Minecraft",
    "version": "18.0.1.0.0",
    "license": "LGPL-3",
    "author": "Nicolas JEUDY",
    "website": "https://besacraft.fr",
    "category": "Besacraft",
    "summary": "Le catalogue des blocs, et les produits qui en créditent au serveur",
    "depends": ["besacraft_base", "product"],
    "data": [
        "security/ir.model.access.csv",
        "data/besacraft.item.csv",
        "views/besacraft_item_views.xml",
        "views/product_views.xml",
    ],
    "installable": True,
    "application": False,
}
