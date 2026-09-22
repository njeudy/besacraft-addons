from odoo import fields, models


class BesacraftVendre(models.TransientModel):
    """Turn a build into something on sale, in one step.

    Doing it by hand means creating the product, copying the price, attaching the images
    and publishing -- four places to forget one. The wizard does the parts that are
    immediate and hands the slow ones (layer images, the short video) to a PAO mission,
    because fetching and attaching several megabytes has no business blocking a dialog.
    """

    _name = "besacraft.vendre"
    _description = "Sell this Build"

    build_id = fields.Many2one("besacraft.build", required=True, ondelete="cascade")
    price = fields.Float("Price", required=True, digits="Product Price")
    serie_id = fields.Many2one(related="build_id.serie_id", readonly=True)
    block_count = fields.Integer(related="build_id.block_count", readonly=True)
    with_media = fields.Boolean(
        "Attach media", default=True,
        help="Layer images and the tutorial short, through a PAO mission.")
    product_name = fields.Char("Product Name", compute="_compute_product_name", readonly=False,
                               store=True)

    @staticmethod
    def _nom_produit(build):
        return "Tuto %s — %s" % (build.code, build.name)

    def _compute_product_name(self):
        for wizard in self:
            wizard.product_name = (self._nom_produit(wizard.build_id)
                                   if wizard.build_id else False)

    def action_vendre(self):
        self.ensure_one()
        build = self.build_id
        produit = build.product_id
        valeurs = {
            "name": self.product_name or self._nom_produit(build),
            "type": "service",
            "is_besacraft_tutorial": True,
            "list_price": self.price,
            "is_published": True,
            "description_sale": build.accroche or "",
            "website_description": build._description_produit(),
            # La boite d'abord : une boutique montre un produit, pas une capture d'ecran.
            "image_1920": build.box_image or build.overview_image,
        }
        if produit:
            produit.product_tmpl_id.write(valeurs)
        else:
            modele = self.env["product.template"].create(valeurs)
            produit = modele.product_variant_id
        build.write({
            "enroll": "payment",
            "product_id": produit.id,
            "state": "publie",
            "is_published": True,
        })

        if self.with_media:
            build._demander_mission_media()

        return {
            "type": "ir.actions.act_url",
            "url": produit.product_tmpl_id.website_url,
            "target": "new",
        }
