import base64
import json
import random

import werkzeug

from odoo import http
from odoo.http import request
from odoo.tools import format_amount, is_html_empty

from ..models.besacraft_build import prix_affiche


def _site_besacraft(env, rule=None, qs=None):
    """Sitemap hook: the catalogue is only crawled on the sites that serve it.

    One callable stands for every route that names it (the sitemap runs it once), so it
    lists all the pages itself: the shelf, each published build with its tutorial, and the
    series with their episodes. Nothing is listed on a site that publishes no series.
    """
    site = env["website"].get_current_website()
    series = site._besacraft_series()
    if not series:
        return
    Build = env["besacraft.build"].sudo()
    yield {"loc": "/builds"}
    yield {"loc": "/builds/collections"}
    yield {"loc": "/builds/shop"}
    for build in Build.search(Build._domaine_site(site) + [("is_published", "=", True)]):
        yield {"loc": "/builds/%d" % int(build.code)}
        yield {"loc": "/t/%d" % int(build.code)}
    for serie in series:
        yield {"loc": "/builds/serie/%s" % serie.code}
        yield {"loc": "/builds/serie/%s/episodes" % serie.code}


class BesacraftBuilds(http.Controller):
    """Public pages of the build catalogue."""

    def _site(self):
        return request.env["website"].get_current_website()

    def _garde_site(self):
        """404 sur un site qui ne publie aucune série.

        Borner les ENREGISTREMENTS par `website_id` ne suffisait pas : les autres sites
        servaient /builds en rayon vide, habillage compris. Un catalogue qui existe et
        ne contient rien a l'air cassé — mieux vaut que la page n'existe pas du tout.

        `get_current_website()` et non `request.website` : la route du viewer n'est pas
        déclarée `website=True` (elle sert un fichier, pas une page), et `request.website`
        n'y existe donc pas — la garde y répondait 500 au lieu de 404.
        """
        return not self._site()._besacraft_series()

    def _filtre_publie(self):
        """`[]` pour un éditeur du site, le filtre de publication pour tout le monde.

        Un tuto se relit en ligne avant d'être ouvert au public : sans cette exception,
        « non publié » voudrait dire « invisible même pour son auteur », et la seule
        façon de se relire serait de publier d'abord. C'est le comportement du blog.
        """
        if request.env.user.has_group("website.group_website_designer"):
            return []
        return [("is_published", "=", True)]

    def _domaine_builds(self):
        """Builds a visitor may see here: published (editors: all) and in this site's series."""
        # `_site()` et non `request.website` : la route de la vitrine sert un fichier et
        # n'est pas `website=True`, `request.website` n'y existe pas.
        return self._filtre_publie() + request.env["besacraft.build"]._domaine_site(
            self._site())

    @staticmethod
    def _code(code):
        return "%03d" % code

    def _build(self, code):
        """The build behind /builds/<n> or /t/<n>, or an empty recordset."""
        return request.env["besacraft.build"].sudo().search(
            [("code", "=", self._code(code))] + self._domaine_builds(), limit=1)

    @staticmethod
    def _avec_piece(records, champ):
        """Ids of the records whose binary field holds something.

        Asked of ir.attachment rather than by reading the field: testing `build.short_video`
        would load the whole video just to learn whether it exists.
        """
        pieces = request.env["ir.attachment"].sudo().search_fetch(
            [("res_model", "=", records._name), ("res_field", "=", champ),
             ("res_id", "in", records.ids)], ["res_id"])
        return set(pieces.mapped("res_id"))

    def _contexte_cartes(self, builds):
        """What the shared card needs beyond the build: who already owns what, who has a box.

        One query for the whole shelf: `is_accessible_by` per card would search the members
        table once for every build.
        """
        partner = request.env.user.partner_id
        membres = request.env["besacraft.build.member"].sudo().search(
            [("build_id", "in", builds.ids), ("partner_id", "=", partner.id)])
        return {
            "acquis": set(membres.build_id.ids),
            "avec_boite": self._avec_piece(builds, "box_image"),
            "avec_vue": self._avec_piece(builds, "overview_image"),
        }

    def _comptes(self, builds, series):
        """The figures the v2 pages quote: how many builds, per series, free and paid."""
        return {
            "total": len(builds),
            "par_serie": {s.id: len(builds.filtered(lambda b, s=s: s in b.series()))
                          for s in series},
            "n_gratuits": len(builds.filtered(lambda b: b.enroll == "public")),
            "n_payants": len(builds.filtered(lambda b: b.enroll == "payment")),
            "n_blocs": sum(builds.mapped("block_count")),
        }

    def _tirer_holo(self, serie=None, code=None):
        """One build to draw as a hologram, drawn at random among those the site shows.

        `serie` narrows the draw to one series, and only a series of this site counts: a
        series published elsewhere yields nothing rather than leaking its builds. `code`
        picks one build. Only builds that carry positions can be drawn.
        """
        Build = request.env["besacraft.build"].sudo()
        domaine = self._domaine_builds() + [("holo_data", "!=", False)]
        if serie:
            series = self._site()._besacraft_series().filtered(lambda s: s.code == serie)
            if not series:
                return Build
            domaine = domaine + Build._domaine_series(series)
        if code and str(code).isdigit():
            domaine.append(("code", "=", self._code(int(code))))
        ids = Build.search(domaine).ids
        return Build.browse(random.choice(ids)) if ids else Build

    def _couche_apercu(self, couche, role):
        """One layer as the build page previews it: number, count, a few real blocks."""
        return {"sequence": couche.sequence, "block_count": couche.block_count, "role": role,
                "types": len(couche.line_ids), "lines": couche.line_ids[:8]}

    @http.route("/builds", type="http", auth="public", website=True,
                sitemap=_site_besacraft)
    def catalogue(self, serie=None, **kw):
        """The builds home: a hologram, how it works, the latest builds, the series."""
        if self._garde_site():
            return request.not_found()
        site = self._site()
        series = site._besacraft_series()
        if serie in series.mapped("code"):
            # The shelf moved to /builds/collections; old links keep their filter.
            return request.redirect("/builds/collections?serie=%s" % serie)
        Build = request.env["besacraft.build"].sudo()
        builds = Build.search(self._domaine_builds())
        derniers = Build.search(self._domaine_builds(), order="code desc", limit=5)
        holo = self._tirer_holo()
        valeurs = {
            "series": series, "derniers": derniers, "holo_build": holo,
            "couverture": self._couvertures(series),
            "sources": self._sources(builds),
            "ex_ligne": holo.layer_ids[:1].line_ids[:1],
            "barre_active": "home",
        }
        valeurs.update(self._comptes(builds, series))
        valeurs.update(self._contexte_cartes(derniers | holo))
        return request.render("besacraft_builds.catalogue", valeurs)

    @staticmethod
    def _sources(builds):
        """The distinct (author, licence, url) the builds credit, for the credit section."""
        vus = []
        for build in builds:
            source = (build.source_author, build.source_license, build.source_url)
            if source[0] and source not in vus:
                vus.append(source)
        return vus[:4]

    def _couvertures(self, series):
        """Ids of the series that have a cover picture or a logo, for the home cards."""
        return {
            "cover": self._avec_piece(series, "cover_image"),
            "logo": self._avec_piece(series, "logo"),
        }

    @http.route("/builds/collections", type="http", auth="public", website=True,
                sitemap=_site_besacraft)
    def collections(self, serie=None, **kw):
        """Every build of the site, to search, filter and sort in the browser.

        Same context as the catalogue: the page differs by its layout, not by its data.
        """
        if self._garde_site():
            return request.not_found()
        Build = request.env["besacraft.build"].sudo()
        builds = Build.search(self._domaine_builds())
        series = self._site()._besacraft_series()
        holo = self._tirer_holo()
        valeurs = {
            "builds": builds, "series": series,
            "serie_active": serie if serie in series.mapped("code") else None,
            "holo_build": holo, "barre_active": "collections",
        }
        valeurs.update(self._comptes(builds, series))
        niveaux = set(builds.mapped("level"))
        # « all Beginner » is only worth saying when it is true of the whole shelf.
        valeurs["niveau_commun"] = (dict(Build._fields["level"]._description_selection(
            Build.env)).get(niveaux.pop()) if len(niveaux) == 1 else False)
        valeurs.update(self._contexte_cartes(builds | holo))
        return request.render("besacraft_builds.collections", valeurs)

    @http.route("/builds/shop", type="http", auth="public", website=True,
                sitemap=_site_besacraft)
    def shop(self, **kw):
        """The shop: a featured build, then every series of the site with its builds.

        Every build of a series is shelved, free ones included: the shop shows the three
        states side by side (free, paid, bought), and a series with nothing to sell yet
        still says what is coming. A build filed in several series shows on each of their
        shelves, as on the series pages. The cart is the site's own website_sale cart.
        """
        if self._garde_site():
            return request.not_found()
        Build = request.env["besacraft.build"].sudo()
        builds = Build.search(self._domaine_builds())
        payants = builds.filtered(lambda b: b.enroll == "payment" and b.product_id)
        vedette = self._vedette(payants or builds)
        holo = (self._tirer_holo(code=int(vedette.code)) if vedette else Build) \
            or self._tirer_holo()
        cartes = self._contexte_cartes(builds | holo)
        series = self._site()._besacraft_series()
        rayons = []
        for serie in series:
            rayon = builds.filtered(lambda b, s=serie: s in b.series())
            pack = serie.sudo().pack_product_id
            payants_rayon = rayon & payants
            # What is for sale first, all of it; then free builds up to one full row, so
            # that the three states sit side by side. The rest of the free builds is in
            # the collections, one link away: a shop that lists 30 free guides is a
            # catalogue, and the one paid guide drowns in it.
            autres = rayon - payants_rayon
            montres = payants_rayon | autres[:max(self.RANGEE - len(payants_rayon), 0)]
            rayons.append({
                "serie": serie, "builds": montres, "n_builds": len(rayon),
                "n_caches": len(rayon - montres),
                "pack": pack,
                "pack_prix": pack and prix_affiche(pack),
                # Bought when every paid guide of the series already is: nothing left to unlock.
                "pack_acquis": bool(payants_rayon) and set(payants_rayon.ids) <= cartes["acquis"],
            })
        valeurs = {
            "rayons": rayons, "builds": builds, "total": len(payants),
            "vedette": vedette, "holo_build": holo,
            "offerts": {b.id: [i + 1 for i, c in enumerate(b.chapter_ids) if c.free]
                        for b in builds},
            "sources": self._sources(builds),
            "couverture": self._couvertures(series),
            "barre_active": "shop",
        }
        valeurs.update(cartes)
        valeurs.update(self._panier())
        return request.render("besacraft_builds.shop", valeurs)

    # Cards per row of a shelf on a wide screen.
    RANGEE = 4

    @staticmethod
    def _vedette(builds):
        """The featured build: the tallest of the shelf, the one with the most layers."""
        if not builds:
            return builds
        return max(builds, key=lambda b: (b.layer_count, b.block_count, b.code))

    def _montant(self, montant, devise):
        return format_amount(request.env, montant, devise)

    def _panier(self):
        """The site's cart as the shop's drawer shows it.

        The real website_sale cart, read here and changed through /shop/cart/update_json:
        no cart of our own to keep in step with the one checkout uses. Every line is listed,
        a build's or not -- hiding what the visitor put in elsewhere would make the total lie.
        """
        commande = request.website.sale_get_order()
        lignes = []
        if commande:
            commande = commande.sudo()
            produits = commande.order_line.product_id
            par_produit = {b.product_id.id: b for b in request.env["besacraft.build"].sudo().search(
                [("product_id", "in", produits.ids)])}
            packs = {s.pack_product_id.id: s for s in request.env["besacraft.serie"].sudo().search(
                [("pack_product_id", "in", produits.ids)])}
            avec_boite = self._avec_piece(
                request.env["besacraft.build"].browse([b.id for b in par_produit.values()]),
                "box_image")
            ht = request.website.show_line_subtotals_tax_selection == "tax_excluded"
            for ligne in commande.website_order_line:
                build = par_produit.get(ligne.product_id.id)
                lignes.append({
                    "ligne": ligne, "build": build, "pack": packs.get(ligne.product_id.id),
                    "image": (build and build.id in avec_boite
                              and "/web/image/besacraft.build/%d/box_image/96x96" % build.id),
                    # The site's choice, as website_sale's own cart lines make it: a line
                    # tax excluded on a site that shows prices tax excluded.
                    "prix": self._montant(
                        ligne.price_subtotal if ht else ligne.price_total, commande.currency_id),
                })
        return {
            "panier": lignes,
            "panier_produits": [l["ligne"].product_id.id for l in lignes],
            "panier_n": int(commande.cart_quantity) if commande else 0,
            "panier_total": self._montant(
                commande.amount_total if commande else 0.0,
                commande.currency_id if commande else request.website.currency_id),
        }

    @http.route("/builds/shop/panier", type="json", auth="public", website=True)
    def shop_panier(self, **kw):
        """The drawer, re-rendered after the cart changed through /shop/cart/update_json."""
        if self._garde_site():
            raise werkzeug.exceptions.NotFound()
        valeurs = self._panier()
        return {
            "html": request.env["ir.ui.view"]._render_template(
                "besacraft_builds.shop_panier_lignes", valeurs),
            "n": valeurs["panier_n"], "total": valeurs["panier_total"],
            "produits": valeurs["panier_produits"],
        }

    @http.route("/builds/<int:code>", type="http", auth="public", website=True,
                sitemap=_site_besacraft)
    def build(self, code, **kw):
        """A build's own page: the box, the short, what the tutorial holds, how to get it."""
        if self._garde_site():
            return request.not_found()
        build = self._build(code)
        if not build:
            return request.not_found()
        partner = request.env.user.partner_id
        couches = build.layer_ids
        apercu = []
        if couches:
            # Première, milieu, dernière : trois vraies couches de la notice, pas la notice.
            milieu = couches[(len(couches) + 1) // 2 - 1]
            roles = [(couches[0], "Première couche"), (milieu, "Couche du milieu"),
                     (couches[-1], "Dernière couche")]
            vus = []
            for couche, role in roles:
                if couche not in vus:
                    vus.append(couche)
                    apercu.append(self._couche_apercu(couche, role))
        # Le OR des séries vient en tête : un domaine Odoo ANDe implicitement les
        # expressions qui suivent, donc l'ordre inverse ferait porter le OR sur le reste.
        voisins = build.sudo().search(
            build._domaine_series(build.series())
            + [("id", "!=", build.id)] + self._domaine_builds())
        voisins = sorted(voisins, key=lambda b: abs(int(b.code) - int(build.code)))[:4]
        voisins = request.env["besacraft.build"].sudo().browse(
            [b.id for b in sorted(voisins, key=lambda b: b.code)])
        valeurs = {
            "build": build, "main_object": build,
            "accessible": build.is_accessible_by(partner),
            # Un build gratuit est lisible par tout le monde, mais il n'entre dans les
            # livres du mod que si son lecteur l'y met : d'où un bouton qui ne regarde
            # pas l'accès mais l'adhésion.
            "peut_rejoindre": (build.enroll == "public"
                               and not request.env.user._is_public()
                               and partner not in build.partner_ids),
            "apercu": apercu, "voisins": voisins,
            "a_un_court": build.id in self._avec_piece(build, "short_video"),
            "barre_active": "catalogue",
            "produit": build.product_id,
        }
        valeurs.update(self._contexte_cartes(build | voisins))
        return request.render("besacraft_builds.build", valeurs)

    @http.route("/builds/<int:code>/rejoindre", type="http", auth="user",
                methods=["POST"], website=True, sitemap=False)
    def rejoindre(self, code, **kw):
        """Add a free build to the visitor's own books.

        Paying builds are refused here on purpose: access to those is granted by the
        confirmed sale order, and a route that could hand them out would be a hole.
        """
        if self._garde_site():
            return request.not_found()
        build = self._build(code)
        if not build:
            return request.not_found()
        if build.enroll != "public":
            raise werkzeug.exceptions.Forbidden()
        build.sudo()._action_add_members(request.env.user.partner_id)
        # Back where the button was: the product sheet, or the build page.
        return request.redirect(("/t/%d" if kw.get("retour") == "fiche" else "/builds/%d") % code)

    @http.route("/builds/<int:code>/court", type="http", auth="public", website=True,
                sitemap=False)
    def court(self, code, **kw):
        """The build's vertical short. Streamed by the core, which answers Range requests."""
        if self._garde_site():
            return request.not_found()
        build = self._build(code)
        if not build or build.id not in self._avec_piece(build, "short_video"):
            return request.not_found()
        return request.env["ir.binary"]._get_stream_from(
            build, "short_video", mimetype="video/mp4").get_response()

    @http.route("/t/<int:code>", type="http", auth="public", website=True,
                sitemap=_site_besacraft)
    def tuto(self, code, **kw):
        """A build's product sheet. The URL carries the number without padding zeros.

        The gallery (box, 3D showcase, box face), the buying column, the episodes the build
        shows up in, its story with the vertical short and the chapters, the showcase, the
        technical sheet. Only the episodes of a series this site publishes are listed.
        """
        if self._garde_site():
            return request.not_found()
        build = self._build(code)
        if not build:
            return request.not_found()
        partner = request.env.user.partner_id
        series_site = self._site()._besacraft_series()
        episodes = request.env["besacraft.episode"].sudo().search(
            self._filtre_publie() + [("build_ids", "in", build.ids),
                                     ("serie_id", "in", series_site.ids)],
            order="number, date, id")
        pieces = {champ: build.id in self._avec_piece(build, champ) for champ in (
            "box_image", "box_face_image", "cutout_image", "overview_image", "short_video")}
        payant = build.enroll == "payment" and bool(build.product_id)
        accessible = build.is_accessible_by(partner)
        chapitres = build.chapter_ids
        valeurs = {
            "build": build, "main_object": build,
            "serie": build.serie_id, "series_build": build.series() & series_site,
            "pieces": pieces, "vues": self._vues_fiche(build, pieces),
            "a_vitrine": bool(build.vitrine_glb_attachment_id),
            "payant": payant, "accessible": accessible,
            "acquis": set(build.ids) if payant and accessible else set(),
            "produit": build.sudo().product_id,
            "peut_rejoindre": (build.enroll == "public"
                               and not request.env.user._is_public()
                               and partner not in build.partner_ids),
            "chapitres": chapitres,
            "offerts": [i + 1 for i, c in enumerate(chapitres) if c.free],
            "episodes": episodes,
            "avec_poster": self._avec_piece(episodes, "poster"),
            "liens_episodes": {e.id: e._lien_au_moment(build) for e in episodes},
            "moments": {m.episode_id.id: m.timecode
                        for m in episodes.appearance_ids.filtered(
                            lambda m: m.build_id == build and m.seconds)},
            "barre_active": "shop" if payant else "collections",
            "a_description": not is_html_empty(build.description),
            "editeur": request.env.user.has_group("website.group_website_designer"),
            "niveau": dict(build._fields["level"]._description_selection(
                request.env)).get(build.level),
        }
        return request.render("besacraft_builds.fiche", valeurs)

    @staticmethod
    def _vues_fiche(build, pieces):
        """The gallery's views, in order: the box, the 3D showcase, the box face.

        Without a box, the build's overview stands first. The showcase needs its glb, and
        shows the cutout (or the overview) until it is asked for.
        """
        url = "/web/image/besacraft.build/%d/%%s/1400x1400" % build.id
        vues = []
        if pieces["box_image"]:
            vues.append({"cle": "boite", "image": url % "box_image"})
        elif pieces["overview_image"]:
            vues.append({"cle": "vue", "image": url % "overview_image"})
        if build.vitrine_glb_attachment_id:
            affiche = next((c for c in ("cutout_image", "overview_image", "box_image")
                            if pieces[c]), None)
            vues.append({"cle": "3d", "image": affiche and url % affiche})
        if pieces["box_face_image"]:
            vues.append({"cle": "face", "image": url % "box_face_image"})
        return vues

    @http.route("/builds/<int:code>/vitrine", type="http", auth="public", website=True,
                sitemap=False)
    def vitrine_page(self, code, **kw):
        """The 3D showcase on its own, framed by the product sheet (and openable full page).

        A page without the site's layout: it is an iframe's content, and the website's
        header, bundle and editor have nothing to do in there. Same guards as the glb.
        """
        if self._garde_site():
            return request.not_found()
        build = self._build(code)
        if not build or not build.vitrine_glb_attachment_id:
            return request.not_found()
        serie = build.serie_id.sudo()
        return request.render("besacraft_builds.vitrine_page", {
            "build": build, "serie": serie,
            "seul": kw.get("seul") == "1",
            "logo": serie.id in self._avec_piece(serie, "logo") and serie.id,
            "niveau": dict(build._fields["level"]._description_selection(
                request.env)).get(build.level),
        })

    @http.route("/builds/<int:code>/guide", type="http", auth="public", website=True,
                sitemap=False)
    def guide(self, code, **kw):
        """The layer-by-layer notice, which /t/<n> held until it became the product sheet.

        Kept as it was, at an address of its own, until the full-screen build screen of
        /builds/<n> takes it over: the sheet must not leave the notice unreachable meanwhile.
        """
        if self._garde_site():
            return request.not_found()
        build = self._build(code)
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
        # L'aperçu d'un tuto payant : la couche 1 en clair, rien des suivantes que leur
        # numéro. Elle suffit à juger de la notice sans en livrer la suite.
        apercu = None
        masquees = []
        if not accessible and build.enroll == "payment" and build.layer_ids:
            apercu = self._couche_apercu(build.layer_ids[0], "Première couche")
            masquees = list(range(2, min(build.layer_count, 4) + 1))
        return request.render("besacraft_builds.tuto", {
            "build": build,
            # `main_object` est la clé sur laquelle la barre d'édition du site se branche :
            # c'est elle qui fait apparaître l'interrupteur « Publié / Non publié » et le
            # panneau « Optimiser le référencement ». Sans elle, la page est éditable mais
            # ne se publie que depuis le backend.
            "main_object": build,
            "accessible": accessible,
            "couches_json": json.dumps(couches),
            "decalage": build.layer_offset,
            "apercu": apercu, "masquees": masquees,
            "produit": build.product_id,
        })

    def _serie_du_site(self, code):
        """The series behind /builds/serie/<code>, only if this site publishes it."""
        return request.website._besacraft_series().filtered(lambda s: s.code == code)[:1]

    @http.route("/builds/serie/<string:code>", type="http", auth="public", website=True,
                sitemap=_site_besacraft)
    def serie(self, code, **kw):
        """A series' page: who it is, its episodes, its builds, a hologram drawn within it."""
        if self._garde_site():
            return request.not_found()
        serie = self._serie_du_site(code)
        if not serie:
            return request.not_found()
        Build = request.env["besacraft.build"].sudo()
        domaine = self._domaine_builds() + Build._domaine_series(serie)
        tous = Build.search(domaine, order="code desc")
        builds = tous[:5]
        series = self._site()._besacraft_series()
        episodes = request.env["besacraft.episode"].sudo().search(
            self._filtre_publie() + [("serie_id", "=", serie.id)])
        autorises = Build.search(self._domaine_builds())
        par_serie = self._comptes(autorises, series)["par_serie"]
        # The latest episode that shows each build of the shelf.
        vu_dans = {}
        for episode in episodes:
            for build in episode.build_ids & builds:
                vu_dans.setdefault(build.id, episode)
        holo = self._tirer_holo(serie=serie.code)
        valeurs = {
            "serie": serie.sudo(), "series": series, "par_serie": par_serie,
            "builds": builds, "n_builds": len(tous),
            "episodes": episodes, "n_episodes": len(episodes),
            "n_blocs": sum(tous.mapped("block_count")),
            "vu_dans": vu_dans, "holo_build": holo,
            "couverture": self._couvertures(series),
            "barre_active": "series", "serie_active": serie.code,
        }
        valeurs.update(self._contexte_cartes(builds | holo))
        return request.render("besacraft_builds.serie", valeurs)

    @http.route("/builds/serie/<string:code>/episodes", type="http", auth="public",
                website=True, sitemap=_site_besacraft)
    def episodes(self, code, **kw):
        """The series' episodes, laid out like a blog."""
        if self._garde_site():
            return request.not_found()
        serie = self._serie_du_site(code)
        if not serie:
            return request.not_found()
        episodes = request.env["besacraft.episode"].sudo().search(
            self._filtre_publie() + [("serie_id", "=", serie.id)])
        autorises = request.env["besacraft.build"].sudo().search(self._domaine_builds())
        vus = {e.id: e.build_ids & autorises for e in episodes}
        tous = autorises.browse()
        for v in vus.values():
            tous |= v
        valeurs = {
            "serie": serie.sudo(), "episodes": episodes, "vus": vus,
            "avec_boite": self._avec_piece(tous, "box_image"),
            "barre_active": serie.code,
        }
        return request.render("besacraft_builds.episodes", valeurs)

    @http.route("/besacraft/holo", type="http", auth="public", methods=["GET"],
                website=True, sitemap=False)
    def holo(self, code=None, serie=None, **kw):
        """One build to draw as a hologram, and the site's figures.

        `serie` restricts the draw to one series of this site; a series the site does not
        publish yields `build: null`. No 404 guard: the theme calls this from pages of any
        site, and a site with no series simply gets `build: null`. A fresh draw per load,
        hence no cache.
        """
        Build = request.env["besacraft.build"].sudo()
        series = self._site()._besacraft_series()
        resultat = {"build": None, "stats": {"builds": 0, "blocs": 0, "series": len(series)}}
        if series:
            publies = self._domaine_builds()
            resultat["stats"]["builds"] = Build.search_count(publies)
            resultat["stats"]["blocs"] = sum(
                Build.search(publies).mapped("block_count"))
            build = self._tirer_holo(serie=serie, code=code)
            if build:
                donnees = json.loads(build.holo_data)
                resultat["build"] = {
                    "code": build.code, "nom": build.name,
                    "taille": donnees.get("taille"), "couches": donnees.get("couches"),
                    "url": "/builds/%d" % int(build.code),
                    "blocs": build.block_count, "couches_n": build.layer_count,
                    "serie": build.serie_id.name, "couleur": build.serie_id.color,
                }
        return request.make_json_response(
            resultat, headers=[("Cache-Control", "no-store")])

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

    @http.route("/besacraft/vitrine/<int:code>.glb", type="http", auth="public",
                methods=["GET"], sitemap=False)
    def vitrine(self, code, **kw):
        """The 3D model of the product sheet's showcase, with the guards of the pages.

        No payment check: the showcase is what makes someone buy, it shows the finished
        building and none of the notice. Streamed by the core, which handles the ETag and
        Range requests -- a glb weighs up to 20 MB.
        """
        if self._garde_site():
            return request.not_found()
        build = self._build(code)
        if not build or not build.vitrine_glb_attachment_id:
            return request.not_found()
        return request.env["ir.binary"]._get_stream_from(
            build.vitrine_glb_attachment_id.sudo(), "raw",
            filename="%s.glb" % build.code, mimetype="model/gltf-binary",
        ).get_response()

    @http.route("/besacraft/viewer/<int:build_id>", type="http", auth="public", sitemap=False)
    def viewer(self, build_id, **kw):
        """Serve the build's standalone viewer.html from OUR origin.

        Same origin is not a detail: the page injects a stylesheet into the iframe and
        reads the build data out of it, and neither is possible across origins.
        """
        if self._garde_site():
            return request.not_found()
        build = request.env["besacraft.build"].sudo().browse(build_id).exists()
        if not build or not build.viewer_attachment_id or not build.is_shown_on(self._site()):
            return request.not_found()
        redirection = self._vers_le_produit(build)
        if redirection:
            return redirection
        piece = build.viewer_attachment_id
        contenu = base64.b64decode(piece.datas)
        # A long cache plus an ETag avoids shipping several megabytes on every layer change.
        # The ETag follows the CONTENT: the import refreshes the viewer by rewriting the same
        # attachment, and an ETag on its id kept browsers on the old viewer for a day.
        etag = '"%s-%s"' % (build.id, piece.checksum or piece.id)
        if request.httprequest.headers.get("If-None-Match") == etag:
            return request.make_response("", status=304, headers=[("ETag", etag)])
        return request.make_response(contenu, headers=[
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(contenu))),
            ("Cache-Control", "private, max-age=86400"),
            ("ETag", etag),
        ])
