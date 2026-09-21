from odoo import http
from odoo.http import request


class BesacraftBuilds(http.Controller):
    """Public pages of the build catalogue."""

    @http.route("/builds", type="http", auth="public", website=True, sitemap=True)
    def catalogue(self, serie=None, **kw):
        """The catalogue, laid out as a shelf of construction boxes."""
        domaine = [("is_published", "=", True)]
        Build = request.env["besacraft.build"].sudo()
        series = request.env["besacraft.serie"].sudo().search([])
        if serie:
            domaine.append(("serie_id.code", "=", serie))
        builds = Build.search(domaine)
        # Le compteur de chaque filtre se lit sur la totalité, pas sur la sélection
        # courante : un filtre qui afficherait « 0 » une fois cliqué serait absurde.
        tous = Build.search_count([("is_published", "=", True)])
        par_serie = {
            s.id: Build.search_count([("is_published", "=", True), ("serie_id", "=", s.id)])
            for s in series
        }
        return request.render("besacraft_builds.catalogue", {
            "builds": builds, "series": series, "serie_active": serie,
            "total": tous, "par_serie": par_serie,
        })

    @http.route("/t/<int:code>", type="http", auth="public", website=True, sitemap=True)
    def tuto(self, code, **kw):
        """A build's tutorial sheet. The URL carries the number without padding zeros."""
        build = request.env["besacraft.build"].sudo().search(
            [("code", "=", "%03d" % code), ("is_published", "=", True)], limit=1)
        if not build:
            return request.not_found()
        return request.render("besacraft_builds.tuto", {
            "build": build,
            "accessible": build.is_accessible_by(request.env.user.partner_id),
        })
