from odoo import fields, models


class BesacraftVestiaireFichier(models.Model):
    """One file of a remote cosmetic: a model, an animation or a texture the game
    downloads by its SHA-256 instead of finding it in the mod's jar."""

    _name = "besacraft.vestiaire.fichier"
    _description = "Wardrobe remote file"
    _order = "cosmetique_id, chemin"

    cosmetique_id = fields.Many2one("besacraft.vestiaire.cosmetique", string="Cosmetic",
                                    required=True, ondelete="cascade", index=True)
    chemin = fields.Char(string="Path", required=True,
                         help="Path under assets/besacraft/ in the mod, e.g. textures/cosmetique/<code>.png.")
    sha256 = fields.Char(string="SHA-256", required=True, index=True)
    taille = fields.Integer(string="Size (bytes)", required=True)
    contenu = fields.Binary(string="Content", attachment=True, required=True)

    _sql_constraints = [
        ("unique_chemin", "unique(cosmetique_id, chemin)", "A remote file path must be unique per cosmetic."),
    ]
