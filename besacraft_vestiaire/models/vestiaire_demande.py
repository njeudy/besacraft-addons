from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class BesacraftVestiaireDemande(models.Model):
    _name = "besacraft.vestiaire.demande"
    _description = "Wardrobe account request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    uuid = fields.Char(required=True, index=True, readonly=True)
    pseudo = fields.Char(required=True, readonly=True)
    prenom = fields.Char(string="First name", required=True, tracking=True)
    email = fields.Char(required=True, tracking=True)
    moins_de_15 = fields.Boolean(string="Under 15")
    email_parent = fields.Char(string="Parent email", tracking=True)
    state = fields.Selection([("a_valider", "To validate"), ("validee", "Validated"),
                              ("refusee", "Refused")], default="a_valider",
                             required=True, tracking=True)
    message_refus = fields.Text(string="Refusal message")
    partner_id = fields.Many2one("res.partner", readonly=True)
    partner_cible_id = fields.Many2one(
        "res.partner", string="Contact to link", compute="_compute_partner_cible",
        help="The contact validation would use. Empty: a new contact is created.")

    def _chercher_partner(self):
        """The contact with this UUID first, else the one with this email."""
        self.ensure_one()
        Partner = self.env["res.partner"].sudo()
        partner = Partner._vestiaire_par_uuid(self.uuid)
        if not partner:
            email = (self.email or "").strip().lower()
            partner = Partner.search([("email_normalized", "=", email)], limit=1) if email \
                else Partner.browse()
        return partner

    @api.depends("uuid", "email", "state")
    def _compute_partner_cible(self):
        for demande in self:
            demande.partner_cible_id = (
                demande._chercher_partner() if demande.state == "a_valider" else False)

    @api.constrains("moins_de_15", "email_parent")
    def _check_parent(self):
        for demande in self:
            if demande.moins_de_15 and not demande.email_parent:
                raise ValidationError(_("A parent's email is required under 15."))

    @api.model
    def _soumettre(self, code, valeurs):
        jeton = self.env["besacraft.vestiaire.code"].sudo()._trouver(code)
        if not jeton:
            raise ValidationError(_("This link has expired."))
        champs = {k: valeurs.get(k) for k in ("prenom", "email", "moins_de_15", "email_parent")}
        for cle in ("prenom", "email", "email_parent"):
            champs[cle] = (champs[cle] or "").strip()
        if not champs["prenom"] or not champs["email"]:
            raise ValidationError(_("First name and email are required."))
        if champs["moins_de_15"] and not champs["email_parent"]:
            raise ValidationError(_("A parent's email is required under 15."))
        ouverte = self.sudo().search([("uuid", "=", jeton.uuid), ("state", "=", "a_valider")],
                                     limit=1)
        if ouverte:
            ouverte.write(champs)
            return ouverte
        demande = self.sudo().create(dict(champs, uuid=jeton.uuid, pseudo=jeton.pseudo))
        admin = self.env.ref("base.user_admin", raise_if_not_found=False)
        if admin:
            demande.activity_schedule("mail.mail_activity_data_todo", user_id=admin.id,
                                      summary=_("Validate %s's wardrobe account", jeton.pseudo))
        return demande

    def action_valider(self):
        Partner = self.env["res.partner"].sudo()
        for demande in self.filtered(lambda d: d.state == "a_valider"):
            partner = demande._chercher_partner()
            if partner and partner.minecraft_uuid != demande.uuid:
                autre = Partner.normaliser_uuid_minecraft(partner.minecraft_uuid)
                if autre and autre != demande.uuid:
                    raise UserError(_(
                        "Contact %(name)s (id %(id)s) already has another Minecraft UUID. "
                        "Fix the contact or refuse the request.",
                        name=partner.display_name, id=partner.id))
            if partner and partner.user_ids.filtered(lambda u: not u.share):
                raise UserError(_(
                    "Contact %(name)s (id %(id)s) is an internal user. "
                    "Fix the contact or refuse the request.",
                    name=partner.display_name, id=partner.id))
            site = self.env["besacraft.vestiaire.code"]._site_besacraft()
            if not partner:
                partner = Partner.create({"name": demande.prenom, "email": demande.email})
            if site and not partner.website_id:
                # The portal invitation links to the contact's website domain.
                partner.website_id = site
            partner.write({"minecraft_uuid": demande.uuid, "minecraft_login": demande.pseudo,
                           "email": partner.email or demande.email,
                           "vestiaire_parent_email": demande.email_parent or False})
            if not partner.user_ids:
                assistant = self.env["portal.wizard"].sudo().create(
                    {"partner_ids": [(6, 0, partner.ids)]})
                assistant.user_ids.action_grant_access()
            if demande.email_parent:
                self.env.ref("besacraft_vestiaire.mail_parent_info").sudo().send_mail(
                    demande.id, force_send=False)
            demande.write({"state": "validee", "partner_id": partner.id})
            demande.activity_feedback(["mail.mail_activity_data_todo"])

    def action_refuser(self):
        for demande in self.filtered(lambda d: d.state == "a_valider"):
            demande.state = "refusee"
            self.env.ref("besacraft_vestiaire.mail_demande_refusee").sudo().send_mail(
                demande.id, force_send=False)
            demande.activity_feedback(["mail.mail_activity_data_todo"])
