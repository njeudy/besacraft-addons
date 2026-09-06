import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class BesacraftItem(models.Model):
    """Un bloc du jeu, tel que le serveur le nomme.

    Le catalogue est livré avec le module : identifiants, noms lisibles, source et
    famille. Les vignettes n'y sont pas — les textures de Conquest Reforged sont
    sous licence « tous droits réservés » et celles de Mojang ne le sont pas
    davantage, si bien que les redistribuer dans le dépôt serait fautif. Elles
    s'importent séparément, depuis les jars que l'instance possède, par
    ``tools/import_images.py``.
    """

    _name = "besacraft.item"
    _description = "Bloc Minecraft"
    _order = "source, famille, name"
    _rec_name = "name"

    name = fields.Char("Nom", required=True, index=True)
    identifiant = fields.Char(
        "Identifiant", required=True, index=True,
        help="Ce que le serveur attend : minecraft:stone, conquest:light_limestone_brick.",
    )
    source = fields.Char("Provenance", index=True, help="Minecraft ou Conquest Reforged.")
    famille = fields.Char(
        "Famille", index=True,
        help="Regroupement d'origine du mod — 1_stone, 3_wood, 2_roof. "
             "Sert à s'y retrouver parmi vingt mille blocs.",
    )
    image_1920 = fields.Image("Vignette", max_width=64, max_height=64)
    actif_en_vente = fields.Boolean(
        "Proposable à la vente", default=False,
        help="Cocher les blocs que l'on veut pouvoir mettre dans un pack. "
             "Le catalogue complet reste consultable, mais tout n'a pas vocation à être vendu.",
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("identifiant_unique", "unique(identifiant)",
         "Deux blocs ne peuvent pas porter le même identifiant."),
    ]

    @api.depends("name", "identifiant")
    def _compute_display_name(self):
        for item in self:
            item.display_name = f"{item.name} ({item.identifiant})"
