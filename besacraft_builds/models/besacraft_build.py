import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

CODE_RE = re.compile(r"^\d+$")


class BesacraftBuild(models.Model):
    """A build tutorial: what buildplan produced, ready to be published.

    Counts come from the plan and are never recomputed here -- the files are the
    reference, and a rounding of our own would silently contradict the video and
    the printed notice.
    """

    _name = "besacraft.build"
    _description = "Build Tutorial"
    _inherit = ["website.published.mixin"]
    _order = "code"

    name = fields.Char(required=True, translate=True,
                       help="Editorial title, accented. Not the schematic's technical name.")
    code = fields.Char(required=True, index=True, copy=False,
                       help="Tutorial number, zero-padded to three digits: 043 -> /t/43.")
    serie_id = fields.Many2one("besacraft.serie", required=True, ondelete="restrict")
    accroche = fields.Text("Tagline", translate=True)
    level = fields.Selection(
        [("debutant", "Beginner"), ("confirme", "Confident"), ("forgeron", "Blacksmith")],
        default="debutant", required=True,
    )
    state = fields.Selection(
        [("brouillon", "Draft"), ("tourne", "Filmed"), ("publie", "Published")],
        default="brouillon", required=True,
    )
    block_count = fields.Integer(help="From the plan. Never recomputed.")
    layer_count = fields.Integer(help="From the plan. Never recomputed.")
    size_x = fields.Integer()
    size_y = fields.Integer()
    size_z = fields.Integer()
    palette_label = fields.Char(help='Free text, e.g. "11 block types".')
    has_recipes = fields.Boolean(help="True when recipes.json was generated; drives the recipe UI.")
    layer_offset = fields.Integer(
        "Viewer Offset",
        help="Foundation layers sunk below ground level, which the tutorial skips but the "
             "viewer still counts. Layer 1 here is layer 1+offset there.")
    overview_image = fields.Image("Overview")
    box_image = fields.Image(
        "Box",
        help="The build's box, rendered by buildplan. This is what the shop shows: a "
             "bare render looks like a screenshot, a box looks like something you buy.")
    youtube_url = fields.Char()
    viewer_attachment_id = fields.Many2one("ir.attachment", ondelete="set null")
    build_json_attachment_id = fields.Many2one("ir.attachment", ondelete="set null")
    layer_ids = fields.One2many("besacraft.build.layer", "build_id")
    enroll = fields.Selection(
        [("public", "Free"), ("payment", "On payment"), ("invite", "On invitation")],
        default="public", required=True,
        help="Free: anyone. On payment: access is granted when the order is confirmed.",
    )
    product_id = fields.Many2one(
        "product.product", string="Product",
        help="The product that grants access. Required when enroll is 'payment'.",
    )
    member_ids = fields.One2many("besacraft.build.member", "build_id", string="Access Lines")
    # Computed, never stored: a Many2many stored on besacraft_build_member would fight the
    # model that already owns that table -- Odoo builds the m2m table without an id column,
    # and every search on the model then fails on "column ... .id does not exist".
    # website_slides computes slide.channel.partner_ids for exactly this reason.
    partner_ids = fields.Many2many(
        "res.partner", string="Members", compute="_compute_partner_ids", search="_search_partner_ids",
    )

    _sql_constraints = [
        ("code_uniq", "unique(code)", "A tutorial number must be unique."),
        ("product_required_on_payment",
         "CHECK (enroll != 'payment' OR product_id IS NOT NULL)",
         "A paying build needs a product."),
    ]

    @api.constrains("code")
    def _check_code(self):
        for build in self:
            if not CODE_RE.match(build.code or ""):
                raise ValidationError("The tutorial number must contain digits only.")

    @api.depends("member_ids.partner_id")
    def _compute_partner_ids(self):
        for build in self:
            build.partner_ids = build.member_ids.partner_id

    def _search_partner_ids(self, operator, value):
        membres = self.env["besacraft.build.member"].sudo().search(
            [("partner_id", operator, value)])
        return [("id", "in", membres.build_id.ids)]

    def _action_add_members(self, partners, member_status="joined"):
        """Grant access. Idempotent: an existing member is left untouched."""
        Member = self.env["besacraft.build.member"].sudo()
        a_creer = []
        for build in self:
            deja = Member.search([("build_id", "=", build.id),
                                  ("partner_id", "in", partners.ids)]).mapped("partner_id")
            for partner in partners - deja:
                a_creer.append({"build_id": build.id, "partner_id": partner.id,
                                "member_status": member_status})
        return Member.create(a_creer) if a_creer else Member

    # Ce qu'on achete, dit dans l'ordre ou on se pose les questions : ce que c'est, ce
    # qu'il y a dedans, et combien de temps ca prend. Les chiffres viennent du plan, pas
    # d'une estimation -- promettre 23 couches et en livrer 21 se voit a la premiere.
    DESCRIPTION = """
<p class="lead">%(accroche)s</p>
<p>Un tutoriel <strong>couche par couche</strong> : on pose la première rangée, puis la
suivante, jusqu'au toit. Pas de plan à déchiffrer, pas de vidéo à mettre en pause toutes
les dix secondes — la visionneuse 3D tourne dans le navigateur et n'affiche que la couche
en cours de construction.</p>
<h4>Ce que vous obtenez</h4>
<ul>
  <li><strong>La visionneuse 3D</strong> du build, couche par couche, à faire tourner et
      zoomer dans tous les sens.</li>
  <li><strong>L'inventaire complet</strong> : %(palette)s, avec les quantités exactes à
      réunir avant de commencer.</li>
  <li><strong>La vidéo courte</strong> de la construction, du premier bloc à la vue finale.</li>
  <li><strong>Un accès à vie</strong>, depuis n'importe quel appareil, mises à jour comprises.</li>
</ul>
<h4>Le chantier en trois chiffres</h4>
<ul>
  <li><strong>%(blocs)s blocs</strong> à poser</li>
  <li><strong>%(couches)s couches</strong> de la fondation au faîtage</li>
  <li><strong>%(taille)s</strong> d'emprise au sol</li>
</ul>
<p class="text-muted">Collection %(serie)s · %(niveau)s. Jouable en survie : aucun bloc
inaccessible, aucune commande, aucun mod obligatoire.</p>
"""

    NIVEAUX = {"debutant": "accessible dès la première cabane",
               "confirme": "pour qui a déjà terminé quelques chantiers",
               "forgeron": "un gros morceau, à prendre au sérieux"}

    def _description_produit(self):
        """The shop copy, written from the plan's own numbers."""
        self.ensure_one()
        taille = ("%d × %d blocs" % (self.size_x, self.size_z)
                  if self.size_x and self.size_z else "variable")
        return self.DESCRIPTION % {
            "accroche": self.accroche or self.name,
            "palette": self.palette_label or "la liste des blocs",
            "blocs": "{:,}".format(self.block_count).replace(",", " "),
            "couches": self.layer_count,
            "taille": taille,
            "serie": self.serie_id.name,
            "niveau": self.NIVEAUX.get(self.level, ""),
        }

    def action_vendre(self):
        """Open the wizard, pre-filled with what we already know."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Vendre ce build",
            "res_model": "besacraft.vendre",
            "view_mode": "form",
            "target": "new",
            "context": {"default_build_id": self.id,
                        "default_price": self.product_id.list_price or 4.0},
        }

    def _demander_mission_media(self):
        """Ask a PAO mission to attach what takes time: layer images and the short.

        A dialog must not wait on several megabytes being rendered and uploaded, and the
        video may not even exist yet. The task is picked up by the next poll.
        """
        Tache = self.env["project.task"].sudo()
        projet = self.env["project.project"].sudo().search(
            [("name", "ilike", "Besacraft")], limit=1)
        for build in self:
            Tache.create({
                "name": "Médias de la fiche produit — tuto %s %s" % (build.code, build.name),
                "project_id": projet.id if projet else False,
                "ai_state": "pending",
                "description": build._brief_media(),
            })

    def _brief_media(self):
        self.ensure_one()
        return (
            "<h3>Compléter la fiche produit du tuto %(code)s</h3>"
            "<p>Le build est en vente, son produit existe et porte déjà le rendu d'ensemble. "
            "Il reste à l'habiller :</p><ul>"
            "<li>Ajouter les <b>images de couches</b> (<code>images/step-NN.png</code> et "
            "<code>plan-NN.png</code> du dossier buildplan) en galerie du produit.</li>"
            "<li>Ajouter le <b>short vidéo</b> du tuto dans les médias de la fiche produit.</li>"
            "<li>Vérifier que la boîte de construction s'affiche correctement sur "
            "<code>%(url)s</code>.</li>"
            "</ul><p>Build : %(nom)s · %(blocs)s blocs · %(couches)s couches · série %(serie)s.</p>"
        ) % {
            "code": self.code, "nom": self.name,
            "blocs": self.block_count, "couches": self.layer_count,
            "serie": self.serie_id.name,
            "url": self.product_id.product_tmpl_id.website_url if self.product_id else "/shop",
        }

    def is_accessible_by(self, partner):
        """True when this partner may see the viewer and the notice."""
        self.ensure_one()
        if self.enroll == "public":
            return True
        if not partner:
            return False
        return bool(self.env["besacraft.build.member"].sudo().search_count(
            [("build_id", "=", self.id), ("partner_id", "=", partner.id)]))

    def _compute_website_url(self):
        # website.published.mixin's hook: the public URL drops the padding zeros.
        super()._compute_website_url()
        for build in self:
            build.website_url = "/t/%d" % int(build.code) if build.code else ""
