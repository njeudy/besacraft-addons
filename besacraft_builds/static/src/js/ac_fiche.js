/** @odoo-module **/
/**
 * Product sheet: the gallery shows one view at a time, and the 3D showcase (a glb of up to
 * 20 MB) is only loaded on demand -- a click on its view, or the visitor reaching the
 * showcase section. Without JavaScript the first view and the rest of the page stay readable.
 *
 * A public widget, as for the other pages of the module: an ordinary script ends up in the
 * "lazy" bundle of the site, which nothing evaluates.
 */
import publicWidget from "@web/legacy/js/public/public_widget";

function iframe(hote, src, titre) {
    if (hote.querySelector("iframe")) {
        return;
    }
    const f = document.createElement("iframe");
    f.src = src;
    f.title = titre;
    f.setAttribute("allowfullscreen", "");
    hote.replaceChildren(f);
}

publicWidget.registry.BesacraftFiche = publicWidget.Widget.extend({
    selector: ".ac.fi",

    start() {
        const titre = this.el.querySelector("#fi-titre")?.textContent.trim() || "";
        this.onglets = Array.from(this.el.querySelectorAll(".fi-rail button"));
        this.compteur = this.el.querySelector(".fi-leg__n");
        this.onglets.forEach((t) => t.addEventListener("click", () => this.voir(t.dataset.vue)));
        const v3d = this.el.querySelector(".fi-vue[data-iframe]");
        if (v3d) {
            v3d.querySelector(".fi-lancer3d").addEventListener("click", () =>
                iframe(v3d, v3d.dataset.iframe, titre)
            );
        }
        const bas = this.el.querySelector("[data-iframe-lazy]");
        if (bas) {
            if ("IntersectionObserver" in window) {
                this.io = new IntersectionObserver(
                    (entrees) => {
                        if (entrees.some((e) => e.isIntersecting)) {
                            iframe(bas, bas.dataset.iframeLazy, titre);
                            this.io.disconnect();
                        }
                    },
                    { rootMargin: "200px" }
                );
                this.io.observe(bas);
            } else {
                iframe(bas, bas.dataset.iframeLazy, titre);
            }
        }
        return this._super(...arguments);
    },

    destroy() {
        this.io?.disconnect();
        this._super(...arguments);
    },

    voir(id) {
        this.onglets.forEach((t, i) => {
            const on = t.dataset.vue === id;
            t.setAttribute("aria-current", on ? "true" : "false");
            if (on && this.compteur) {
                this.compteur.textContent = `${i + 1} / ${this.onglets.length}`;
            }
        });
        this.el.querySelectorAll(".fi-vue").forEach((v) => {
            v.classList.toggle("is-on", v.id === id);
            if (v.id !== id) {
                v.querySelector("video")?.pause();
            }
        });
        this.el.querySelectorAll("[data-leg]").forEach((l) => {
            l.hidden = l.dataset.leg !== id;
        });
    },
});
