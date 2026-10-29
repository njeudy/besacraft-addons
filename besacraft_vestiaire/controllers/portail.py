import base64

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal

MAX_UPLOAD = 2 * 1024 * 1024  # the image check refuses more than 1 MB; never read further than this


class VestiairePortail(CustomerPortal):
    """The player's own wardrobe. Records are read and written as sudo, so every
    action first checks that it concerns the logged-in player's own data."""

    def _vestiaire_partner(self):
        partner = request.env.user.partner_id
        return partner if partner._vestiaire_valide() else None

    def _vestiaire_page(self, erreur=None):
        partner = self._vestiaire_partner()
        if not partner:
            return request.redirect("/my")
        sudo = partner.sudo()
        return request.render("besacraft_vestiaire.portal_vestiaire", {
            "partner": partner, "skins": sudo.vestiaire_skin_ids,
            "capes": sudo._vestiaire_capes(), "cape_portee": sudo.vestiaire_cape_id,
            "erreur": erreur, "page_name": "vestiaire"})

    @http.route("/my/vestiaire", type="http", auth="user", website=True)
    def vestiaire(self, **kw):
        return self._vestiaire_page()

    @http.route("/my/vestiaire/skin/ajouter", type="http", auth="user", website=True,
                methods=["POST"])
    def ajouter_skin(self, image=None, name=None, modele="classic", **kw):
        partner = self._vestiaire_partner()
        if not partner or not hasattr(image, "read"):
            return request.redirect("/my/vestiaire")
        try:
            with request.env.cr.savepoint():
                request.env["besacraft.vestiaire.skin"].sudo().create({
                    "partner_id": partner.id, "name": name or "Skin",
                    "modele": "slim" if modele == "slim" else "classic",
                    "image": base64.b64encode(image.read(MAX_UPLOAD)),
                    "actif": not partner.sudo().vestiaire_skin_ids})
        except ValidationError as erreur:
            return self._vestiaire_page(erreur=erreur.args[0])
        return request.redirect("/my/vestiaire")

    def _mon_skin(self, skin_id):
        partner = self._vestiaire_partner()
        skin = request.env["besacraft.vestiaire.skin"].sudo().browse(skin_id).exists()
        return skin if partner and skin.partner_id == partner else None

    @http.route("/my/vestiaire/skin/<int:skin_id>/apercu", type="http", auth="user",
                website=True, methods=["GET"])
    def apercu_skin(self, skin_id, **kw):
        # Inactive skins are not served by the public texture route, so the owner
        # previews them here.
        skin = self._mon_skin(skin_id)
        if not skin:
            return request.not_found()
        return request.make_response(base64.b64decode(skin.image),
                                     headers=[("Content-Type", "image/png"),
                                              ("Cache-Control", "private, max-age=3600")])

    @http.route("/my/vestiaire/skin/<int:skin_id>/activer", type="http", auth="user",
                website=True, methods=["POST"])
    def activer_skin(self, skin_id, **kw):
        skin = self._mon_skin(skin_id)
        if skin:
            skin.actif = True
        return request.redirect("/my/vestiaire")

    @http.route("/my/vestiaire/skin/<int:skin_id>/supprimer", type="http", auth="user",
                website=True, methods=["POST"])
    def supprimer_skin(self, skin_id, **kw):
        skin = self._mon_skin(skin_id)
        if skin:
            skin.unlink()
        return request.redirect("/my/vestiaire")

    @http.route("/my/vestiaire/cape", type="http", auth="user", website=True, methods=["POST"])
    def porter_cape(self, cape_id=None, **kw):
        partner = self._vestiaire_partner()
        if partner:
            sudo = partner.sudo()
            if not cape_id:
                sudo.vestiaire_cape_id = False
            elif cape_id.isdigit():
                cape = request.env["besacraft.vestiaire.cape"].sudo().browse(int(cape_id)).exists()
                if cape and cape in sudo._vestiaire_capes():
                    sudo.vestiaire_cape_id = cape
        return request.redirect("/my/vestiaire")
