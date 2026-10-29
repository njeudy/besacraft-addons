from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


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
        ouverte = self.sudo().search([("uuid", "=", jeton.uuid), ("state", "=", "a_valider")],
                                     limit=1)
        if ouverte:
            ouverte.write(champs)
            return ouverte
        demande = self.sudo().create(dict(champs, uuid=jeton.uuid, pseudo=jeton.pseudo))
        admin = self.env.ref("base.user_admin")
        demande.activity_schedule("mail.mail_activity_data_todo", user_id=admin.id,
                                  summary=_("Validate %s's wardrobe account", jeton.pseudo))
        return demande

    def action_valider(self):
        Partner = self.env["res.partner"].sudo()
        for demande in self.filtered(lambda d: d.state == "a_valider"):
            partner = Partner._vestiaire_par_uuid(demande.uuid) or Partner.search(
                [("email_normalized", "=", (demande.email or "").strip().lower())], limit=1)
            if not partner:
                partner = Partner.create({"name": demande.prenom, "email": demande.email})
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
