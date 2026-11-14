from odoo.http import request

from odoo.addons.besacraft_minecraft_api.controllers.auth import BesacraftMcAuth


class VestiaireMcAuth(BesacraftMcAuth):

    def _apres_certification(self, partenaire, pseudo):
        super()._apres_certification(partenaire, pseudo)
        # Mojang just vouched for this name: a renamed player keeps their skins on /csl/.
        if pseudo and partenaire.minecraft_login != pseudo:
            partenaire.sudo().minecraft_login = pseudo

    def _reponse_compte_non_lie(self, uuid, pseudo):
        corps = super()._reponse_compte_non_lie(uuid, pseudo)
        Code = request.env["besacraft.vestiaire.code"].sudo()
        code = Code._emettre(uuid, pseudo)
        corps.update({"code": code.code, "url": Code._url(code.code)})
        return corps
