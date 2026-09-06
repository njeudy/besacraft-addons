from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    """Un produit peut créditer des ressources au serveur.

    C'est ainsi qu'on finance le serveur : un mécène achète un pack, et les blocs
    correspondants sont livrés à la réception du 97 rue Battant, dans la dimension
    Besançon. Un pack vaut plusieurs lignes — mille pierres et mille chênes en font
    deux.
    """

    _inherit = "product.template"

    est_ressource_besacraft = fields.Boolean(
        "Ressource Besacraft",
        help="Cocher pour que l'achat de ce produit crédite des blocs au serveur.",
    )
    besacraft_line_ids = fields.One2many(
        "besacraft.product.line", "product_tmpl_id", string="Blocs crédités",
    )
    besacraft_total = fields.Integer(
        "Blocs au total", compute="_compute_besacraft_total", store=True,
        help="Ce que ce produit livre en tout, toutes lignes confondues.",
    )

    @api.depends("besacraft_line_ids.quantite")
    def _compute_besacraft_total(self):
        for produit in self:
            produit.besacraft_total = sum(produit.besacraft_line_ids.mapped("quantite"))

    @api.constrains("est_ressource_besacraft", "besacraft_line_ids")
    def _check_lignes(self):
        for produit in self:
            if produit.est_ressource_besacraft and not produit.besacraft_line_ids:
                # Sans ligne, l'acheteur paierait pour rien et le serveur ne livrerait
                # rien : mieux vaut refuser que découvrir le vide à la première commande.
                raise ValidationError(_(
                    "« %s » est marqué comme ressource Besacraft mais ne crédite aucun bloc.",
                    produit.display_name,
                ))


class BesacraftProductLine(models.Model):
    """Un bloc et sa quantité, dans un produit."""

    _name = "besacraft.product.line"
    _description = "Bloc crédité par un produit"
    _order = "product_tmpl_id, sequence, id"

    product_tmpl_id = fields.Many2one(
        "product.template", "Produit", required=True, ondelete="cascade", index=True,
    )
    sequence = fields.Integer(default=10)
    item_id = fields.Many2one(
        "besacraft.item", "Bloc", required=True, ondelete="restrict",
        domain="[('actif_en_vente', '=', True)]",
        help="Seuls les blocs cochés « proposable à la vente » sont offerts ici.",
    )
    identifiant = fields.Char(related="item_id.identifiant", string="Identifiant", store=False)
    image_1920 = fields.Image(related="item_id.image_1920", string="Vignette", store=False)
    quantite = fields.Integer("Quantité", required=True, default=64)

    _sql_constraints = [
        ("quantite_positive", "CHECK(quantite > 0)",
         "Une quantité doit être supérieure à zéro."),
        ("item_unique_par_produit", "unique(product_tmpl_id, item_id)",
         "Ce bloc figure déjà dans ce produit — ajuster sa quantité plutôt que de le répéter."),
    ]
