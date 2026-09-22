import base64
import json

from odoo import http
from odoo.http import request


class BesacraftBuilds(http.Controller):
    """Public pages of the build catalogue."""

    @http.route("/builds", type="http", auth="public", website=True, sitemap=True)
    def catalogue(self, serie=None, **kw):
        """The catalogue, laid out as a shelf of construction boxes."""
        # website_domain() borne au site courant : le même Odoo sert aussi la boutique
        # freelance, et /builds y afficherait les tutos de Besacraft.
        domaine = [("is_published", "=", True)] + request.website.website_domain()
        Build = request.env["besacraft.build"].sudo()
        series = request.env["besacraft.serie"].sudo().search([])
        if serie:
            domaine.append(("serie_id.code", "=", serie))
        builds = Build.search(domaine)
        # Le compteur de chaque filtre se lit sur la totalité, pas sur la sélection
        # courante : un filtre qui afficherait « 0 » une fois cliqué serait absurde.
        publies = [("is_published", "=", True)] + request.website.website_domain()
        tous = Build.search_count(publies)
        par_serie = {
            s.id: Build.search_count(publies + [("serie_id", "=", s.id)]) for s in series
        }
        return request.render("besacraft_builds.catalogue", {
            "builds": builds, "series": series, "serie_active": serie,
            "total": tous, "par_serie": par_serie,
        })

    @http.route("/t/<int:code>", type="http", auth="public", website=True, sitemap=True)
    def tuto(self, code, **kw):
        """A build's tutorial sheet. The URL carries the number without padding zeros."""
        build = request.env["besacraft.build"].sudo().search(
            [("code", "=", "%03d" % code), ("is_published", "=", True)]
            + request.website.website_domain(), limit=1)
        if not build:
            return request.not_found()
        # Les couches partent en JSON : la page change de couche sans aller-retour serveur,
        # et la liste se coche pendant qu'on pose, hors ligne si besoin.
        accessible = build.is_accessible_by(request.env.user.partner_id)
        # Sans accès, la notice ne part pas dans la page : le voile serait une serrure en
        # carton si la liste des blocs restait lisible dans le code source.
        couches = [] if not accessible else [{
            "sequence": c.sequence,
            "title": c.title or "",
            "block_count": c.block_count,
            "lines": [{"id": l.id, "name": l.name_fr or l.item_key, "key": l.item_key,
                       "mod": l.mod or "", "qty": l.qty} for l in c.line_ids],
        } for c in build.layer_ids]
        return request.render("besacraft_builds.tuto", {
            "build": build,
            "accessible": accessible,
            "couches_json": json.dumps(couches),
            "decalage": build.layer_offset,
        })

    def _vers_le_produit(self, build):
        """Redirection vers le produit quand l'accès manque, sinon None.

        `sudo` sur le produit : un visiteur n'a pas le droit de lire product.product, mais
        il a le droit de savoir ce qu'il doit acheter et combien ça coûte.
        """
        if build.is_accessible_by(request.env.user.partner_id):
            return None
        produit = build.sudo().product_id
        if build.enroll == "payment" and produit:
            return request.redirect(produit.product_tmpl_id.website_url, code=303)
        return None     # enroll=invite : la fiche s'affiche, verrouillée et sans achat

    @http.route("/besacraft/viewer/<int:build_id>", type="http", auth="public", sitemap=False)
    def viewer(self, build_id, **kw):
        """Serve the build's standalone viewer.html from OUR origin.

        Same origin is not a detail: the page injects a stylesheet into the iframe and
        reads the build data out of it, and neither is possible across origins.
        """
        build = request.env["besacraft.build"].sudo().browse(build_id).exists()
        if not build or not build.viewer_attachment_id:
            return request.not_found()
        redirection = self._vers_le_produit(build)
        if redirection:
            return redirection
        piece = build.viewer_attachment_id
        contenu = base64.b64decode(piece.datas)
        # The viewer is regenerated per build version: a long cache plus an ETag on the
        # attachment id avoids shipping several megabytes on every layer change.
        etag = '"%s-%s"' % (build.id, piece.id)
        if request.httprequest.headers.get("If-None-Match") == etag:
            return request.make_response("", status=304, headers=[("ETag", etag)])
        return request.make_response(contenu, headers=[
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(contenu))),
            ("Cache-Control", "private, max-age=86400"),
            ("ETag", etag),
        ])
