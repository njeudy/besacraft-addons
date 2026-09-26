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
    # Multi, pas simple : le même Odoo sert plusieurs sites, et un tuto Besacraft n'a
    # rien à faire dans la boutique du site freelance. Le mixin apporte website_id et le
    # filtrage par site courant.
    #
    # `website.seo.metadata` par-dessus, dans l'ordre de `blog.post` : un tuto est une page
    # publique qu'on partage, elle a besoin de son titre, de sa description et de son image
    # Open Graph. Sans ce mixin, la barre « Optimiser le référencement » de l'éditeur est
    # vide et un lien partagé sort sans vignette.
    #
    # `website.searchable.mixin` pour que la recherche du site trouve un tuto. Sans lui, le
    # seul chemin vers /t/<n> est le catalogue : quelqu'un qui tape « hôtel de ville » dans
    # la loupe ne trouve rien, alors que la page existe.
    _inherit = ["website.seo.metadata", "website.published.multi.mixin",
                "website.searchable.mixin"]
    _order = "code"

    def _default_website_id(self):
        """The site that carries the catalogue, when there is exactly one.

        Left empty, website_id means « every site of this database », and this one
        serves six. Thirty-seven builds had been created that way and showed up in the
        freelance shop. A default costs nothing and closes the hole at the source
        rather than in each caller.

        Exactly one: with several candidates the answer would be arbitrary, and a
        tutorial filed under the wrong site is harder to notice than one filed under
        none. Ambiguity leaves the field empty and the human decides.
        """
        sites = self.env["website"].search([("besacraft_enabled", "=", True)])
        return sites if len(sites) == 1 else self.env["website"]

    # Redéclaré pour son seul défaut : le champ lui-même vient du mixin.
    website_id = fields.Many2one(default=lambda self: self._default_website_id())

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
    # Crédit de la structure d'origine. Les blueprints du pack sont sous GPL-3.0 : le nom,
    # la licence et le lien doivent voyager avec elle partout où on la montre ou la vend.
    source_author = fields.Char("Original Author")
    source_license = fields.Char("Licence")
    source_url = fields.Char("Source")
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
    # Une grille CSS, pas un `row` Bootstrap : le champ est rendu hors de tout `container`
    # selon le gabarit de boutique, et les marges négatives d'un `row` débordent alors de la
    # page -- le texte se retrouve coupé sur le bord droit.
    GRILLE = ('<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));'
              'gap:1px;background:#E4DFD3;border:1px solid #E4DFD3;margin:1.5rem 0">%s</div>')
    CASE = ('<div style="background:#FBFAF7;padding:14px 16px">'
            '<div style="font-size:11px;font-weight:700;letter-spacing:.16em;'
            'text-transform:uppercase;color:#7A5D38">%s</div>'
            '<div style="font-size:1.6rem;line-height:1.1;color:#323837">%s</div></div>')

    DESCRIPTION = """
<p class="lead">%(accroche)s</p>
<p>Un tutoriel <strong>couche par couche</strong> : on pose la première rangée, puis la
suivante, jusqu'au toit. Pas de plan à déchiffrer, pas de vidéo à mettre en pause toutes les
dix secondes — la visionneuse 3D tourne dans le navigateur et n'affiche que la couche en
cours de construction.</p>
%(cases)s
<h4>Dans la boîte</h4>
<ul>
  <li><strong>La vue 3D</strong> du build, à tourner et à parcourir couche par couche.</li>
  <li><strong>La liste des blocs</strong> de chaque couche, cochable pendant que tu poses.</li>
  <li><strong>La notice complète</strong>, de la fondation au faîtage.</li>
  <li><strong>Les recettes de fabrication</strong> et les matières premières à réunir.</li>
  <li><strong>La vidéo courte</strong> de la construction, du premier bloc à la vue finale.</li>
</ul>
<p class="text-muted"><em>Pas de schematic : on construit soi-même, c'est le principe.</em>
Jouable en survie — aucun bloc inaccessible, aucune commande, aucun mod obligatoire.
%(niveau)s</p>
%(credit)s
"""

    CREDIT = ('<p class="small text-muted border-top pt-3 mt-4">'
              'Structure d\'origine : %s%s.%s</p>')

    NIVEAUX = {"debutant": "Accessible dès la première cabane.",
               "confirme": "Pour qui a déjà terminé quelques chantiers.",
               "forgeron": "Un gros morceau, à prendre au sérieux."}
    NIVEAUX_COURT = {"debutant": "Débutant", "confirme": "Confirmé", "forgeron": "Forgeron"}

    def _description_produit(self):
        """The shop copy, written from the plan's own numbers.

        Elle vit dans website_description, donc en base et éditable : une page de boutique
        se retouche sans déployer, et le module n'a pas à s'insérer dans le gabarit produit
        pour dire ce qu'il a à dire. D'où le HTML autonome -- classes Bootstrap seulement,
        aucune dépendance au SCSS du module, pour tenir dans n'importe quel thème.
        """
        self.ensure_one()
        emprise = ("%d × %d × %d" % (self.size_x, self.size_y, self.size_z)
                   if self.size_x else "—")
        cases = self.GRILLE % "".join(self.CASE % paire for paire in (
            ("Pièces", "{:,}".format(self.block_count).replace(",", " ")),
            ("Couches", self.layer_count),
            ("Emprise", emprise),
            ("Niveau", self.NIVEAUX_COURT.get(self.level, "—")),
            ("Palette", self.palette_label or "—"),
            ("Collection", self.serie_id.name),
        ))
        return self.DESCRIPTION % {
            "accroche": self.accroche or self.name,
            "cases": cases,
            "niveau": self.NIVEAUX.get(self.level, ""),
            "credit": self._credit_html(),
        }

    def _credit_html(self):
        """The original structure's credit, or nothing when the build is ours.

        Une licence libre se respecte en citant, pas en ayant l'intention de citer : le
        bloc se construit à partir des champs, donc il suit la structure sans qu'on y pense.
        """
        self.ensure_one()
        if not self.source_author:
            return ""
        licence = " — %s" % self.source_license if self.source_license else ""
        lien = (' <a href="%s" target="_blank" rel="noopener">Voir la source</a>'
                % self.source_url if self.source_url else "")
        return self.CREDIT % (self.source_author, licence, lien)

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

    def _search_get_detail(self, website, order, options):
        """What the site's search box knows about a tutorial.

        The number is searchable as well as the title: on the box it is the number that
        is printed large, and that is what someone reads back to you.
        """
        domain = [website.website_domain()]
        # Même règle que les pages : un rédacteur cherche aussi ce qu'il n'a pas publié.
        if not self.env.user.has_group("website.group_website_designer"):
            domain.append([("is_published", "=", True)])
        return {
            "model": "besacraft.build",
            "base_domain": domain,
            "search_fields": ["name", "code", "accroche"],
            "fetch_fields": ["id", "name", "code", "accroche", "website_url"],
            "mapping": {
                "name": {"name": "name", "type": "text", "match": True},
                "description": {"name": "accroche", "type": "text", "match": True},
                "website_url": {"name": "website_url", "type": "text", "truncate": False},
            },
            "icon": "fa-cubes",
            "order": "code asc" if "code" not in (order or "") else order,
        }
