from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request


class VestiaireDemande(http.Controller):

    @http.route("/vestiaire/demande", type="http", auth="public", website=True,
                methods=["GET"], sitemap=False)
    def page(self, code=None, **kw):
        jeton = request.env["besacraft.vestiaire.code"].sudo()._trouver(code)
        return request.render("besacraft_vestiaire.page_demande", {
            "expire": not jeton, "jeton": jeton, "envoye": False, "erreur": False})

    @http.route("/vestiaire/demande", type="http", auth="public", website=True,
                methods=["POST"], sitemap=False)
    def envoyer(self, code=None, **post):
        Demande = request.env["besacraft.vestiaire.demande"].sudo()
        jeton = request.env["besacraft.vestiaire.code"].sudo()._trouver(code)
        try:
            Demande._soumettre(code, {
                "prenom": (post.get("prenom") or "").strip(),
                "email": (post.get("email") or "").strip(),
                "moins_de_15": bool(post.get("moins_de_15")),
                "email_parent": (post.get("email_parent") or "").strip(),
            })
        except ValidationError as erreur:
            return request.render("besacraft_vestiaire.page_demande", {
                "expire": not jeton, "jeton": jeton, "envoye": False, "erreur": str(erreur)})
        return request.render("besacraft_vestiaire.page_demande", {
            "expire": False, "jeton": jeton, "envoye": True, "erreur": False})
