/** @odoo-module **/
/**
 * Catalogue : filtres, tri et recherche.
 *
 * Tout se fait sur les cartes déjà présentes dans la page (data-serie, data-acces,
 * data-blocs, data-couches, data-code, data-nom) : le catalogue tient en quelques dizaines
 * de cartes, et un aller-retour serveur par clic serait plus lent que de les masquer.
 * Sans JavaScript la page reste complète, simplement non filtrée.
 *
 * Enregistré comme publicWidget pour la même raison que le tuto : un script ordinaire
 * tombe dans le bundle « lazy » du site, que rien n'évalue.
 */
import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.BesacraftCatalogue = publicWidget.Widget.extend({
    selector: ".bc-catalogue",

    start() {
        this.grille = this.el.querySelector(".bc-grille");
        this.cases = Array.from(this.grille.children);
        this.etat = {
            serie: new URLSearchParams(window.location.search).get("serie") || "tout",
            acces: "tout",
            tri: "code",
            sens: 1,
            q: "",
        };
        this.el.querySelectorAll("[data-filtre]").forEach((b) => {
            b.addEventListener("click", () => this._regler({ serie: b.dataset.filtre }));
        });
        this.el.querySelectorAll("[data-acces-f]").forEach((b) => {
            b.addEventListener("click", () => this._regler({ acces: b.dataset.accesF }));
        });
        this.el.querySelectorAll("[data-tri]").forEach((b) => {
            b.addEventListener("click", () => {
                // Un second clic sur le tri actif inverse le sens.
                const sens = this.etat.tri === b.dataset.tri
                    ? -this.etat.sens : parseInt(b.dataset.sens, 10);
                this._regler({ tri: b.dataset.tri, sens });
            });
        });
        const champ = this.el.querySelector("[data-recherche]");
        if (champ) {
            champ.addEventListener("input", () => this._regler({ q: champ.value }));
        }
        this._appliquer();
        return this._super(...arguments);
    },

    _regler(changement) {
        Object.assign(this.etat, changement);
        this._appliquer();
    },

    _appliquer() {
        const { serie, acces, tri, sens, q } = this.etat;
        const terme = q.trim().toLowerCase();
        const cle = (c) => {
            const carte = c.firstElementChild;
            return tri === "code"
                ? parseInt(carte.dataset.code, 10)
                : parseInt(carte.dataset[tri], 10) || 0;
        };
        this.cases.sort((a, b) => (cle(a) - cle(b)) * sens);
        let visibles = 0;
        for (const c of this.cases) {
            const d = c.firstElementChild.dataset;
            const ok = (serie === "tout" || d.serie === serie)
                && (acces === "tout" || d.acces === acces)
                && (!terme || (d.nom || "").includes(terme) || d.code.includes(terme));
            c.hidden = !ok;
            if (ok) {
                visibles += 1;
            }
            this.grille.appendChild(c);
        }
        this.el.querySelectorAll("[data-filtre]").forEach((b) => {
            b.setAttribute("aria-pressed", b.dataset.filtre === serie);
        });
        this.el.querySelectorAll("[data-acces-f]").forEach((b) => {
            b.setAttribute("aria-pressed", b.dataset.accesF === acces);
        });
        this.el.querySelectorAll("[data-tri]").forEach((b) => {
            const actif = b.dataset.tri === tri;
            b.setAttribute("aria-pressed", actif);
            const fleche = b.querySelector(".bc-f-sens");
            if (fleche && actif) {
                fleche.textContent = sens > 0 ? "↑" : "↓";
            }
        });
        const nb = this.el.querySelector("[data-nb]");
        if (nb) {
            nb.textContent = visibles;
        }
        // Un seul état vide à la fois : celui de la série filtrée si elle a le sien, sinon
        // le message générique.
        const vides = Array.from(this.el.querySelectorAll("[data-vide]"));
        // Le message « premiers tutos » n'a de sens que sans autre filtre : une recherche
        // sans résultat dans une série pleine ne doit pas la dire vide.
        const propre = acces === "tout" && !terme
            ? vides.filter((v) => v.dataset.vide === serie)[0] : undefined;
        for (const v of vides) {
            v.hidden = !(visibles === 0 && (propre ? v === propre : v.dataset.vide === "*"));
        }
    },
});
