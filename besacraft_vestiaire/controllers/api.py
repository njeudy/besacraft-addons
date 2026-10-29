from odoo import http
from odoo.http import request

from odoo.addons.besacraft_minecraft_api.controllers.base import partenaire_ou_401, reponse


class VestiaireApi(http.Controller):

    @http.route("/mc/v1/vestiaire/moi", type="http", auth="public", methods=["GET"],
                csrf=False, save_session=False)
    def moi(self, **kw):
        partner = partenaire_ou_401()
        if not partner._vestiaire_valide():
            Code = request.env["besacraft.vestiaire.code"].sudo()
            code = Code._emettre(partner.minecraft_uuid, partner.minecraft_login or "")
            return reponse({"erreur": "compte_non_valide", "code": code.code,
                            "url": Code._url(code.code)}, code=403)
        skin = partner._vestiaire_skin_actif()
        return reponse({
            "pseudo": partner.minecraft_login,
            "skin": {"empreinte": skin.empreinte, "modele": skin.modele} if skin else None,
            "cape": partner.vestiaire_cape_id.empreinte or None,
        })
