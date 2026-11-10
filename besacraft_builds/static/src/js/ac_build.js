/** @odoo-module **/
/**
 * Build screen (/builds/<n>): the guide full screen under a console bar.
 *
 * The guide is the build's own viewer, served from our origin, so the bar can read where it
 * stands: the chapter follows the guide's step (by the zone name of the guided viewer, or by
 * the layer of the older one). Without access the guide is not loaded at all; "try" loads the
 * viewer the server cut down to the free chapters. The remote button only shows when the
 * loaded guide has a remote.
 */
import publicWidget from "@web/legacy/js/public/public_widget";

const CLE_REPLIE = "acb-replie";

publicWidget.registry.BesacraftBuildScreen = publicWidget.Widget.extend({
    selector: ".ac.acb",

    start() {
        const el = this.el;
        this.cadre = el.querySelector(".acb-guide");
        this.charge = el.querySelector(".acb-charge");
        this.voile = el.querySelector(".acb-voile");
        this.apercu = el.querySelector(".acb-apercu");
        this.bulle = el.querySelector(".acb-bulle");
        this.tele = el.querySelector('[data-acb="tele"]');
        this.plein = el.querySelector('[data-acb="plein"]');
        try {
            this.chapitres = JSON.parse(el.dataset.chapitres || "[]");
        } catch {
            this.chapitres = [];
        }
        this.decalage = parseInt(el.dataset.decalage || "0", 10) || 0;
        this.ecouteurs = [];

        this.on('[data-acb="replier"]', () => this.replier(true));
        this.on('[data-acb="deplier"]', () => this.replier(false));
        this.on('[data-acb="tele"]', () => this.basculerBulle());
        this.on('[data-acb="compris"]', () => {
            this.fermerBulle();
            this.tele.focus();
        });
        this.on('[data-acb="plein"]', () => this.pleinEcran());
        this.on('[data-acb="essayer"]', () => this.essayer());
        this.on('[data-acb="debloquer"]', () => {
            this.apercu.hidden = true;
            this.voile.hidden = false;
        });
        this.surDocument("keydown", (e) => {
            if (e.key === "Escape" && this.bulle && !this.bulle.hidden) {
                this.fermerBulle();
                this.tele.focus();
            }
        });
        this.surDocument("fullscreenchange", () => this.majPlein());
        try {
            if (sessionStorage.getItem(CLE_REPLIE) === "1") {
                el.classList.add("is-replie");
            }
        } catch {
            // Storage refused (private mode): the bar simply starts unfolded.
        }

        if (this.cadre) {
            this.cadre.addEventListener("load", () => this.brancher());
        }
        if (el.dataset.src) {
            this.charger(el.dataset.src);
        } else if (el.dataset.apercuDirect) {
            this.essayer();
        }
        return this._super(...arguments);
    },

    destroy() {
        this.ecouteurs.forEach(([cible, type, f]) => cible.removeEventListener(type, f));
        if (this.observateur) {
            this.observateur.disconnect();
        }
        this._super(...arguments);
    },

    on(selecteur, f) {
        const bouton = this.el.querySelector(selecteur);
        if (bouton) {
            bouton.addEventListener("click", f);
        }
    },

    surDocument(type, f) {
        document.addEventListener(type, f);
        this.ecouteurs.push([document, type, f]);
    },

    charger(src) {
        if (!this.cadre || this.cadre.getAttribute("src") === src) {
            return;
        }
        this.el.classList.add("is-charge");
        this.charge?.classList.remove("is-fini");
        this.cadre.src = src;
    },

    essayer() {
        if (this.voile) {
            this.voile.hidden = true;
        }
        if (this.apercu) {
            this.apercu.hidden = false;
        }
        this.charger(this.el.dataset.apercu);
    },

    replier(oui) {
        this.el.classList.toggle("is-replie", oui);
        try {
            sessionStorage.setItem(CLE_REPLIE, oui ? "1" : "0");
        } catch {
            // Not remembered, that is all.
        }
        if (oui) {
            this.fermerBulle();
            this.el.querySelector('[data-acb="deplier"]').focus();
        } else {
            this.el.querySelector('[data-acb="replier"]').focus();
        }
    },

    basculerBulle() {
        const ouvrir = this.bulle.hidden;
        this.bulle.hidden = !ouvrir;
        this.tele.setAttribute("aria-expanded", ouvrir ? "true" : "false");
    },

    fermerBulle() {
        if (this.bulle) {
            this.bulle.hidden = true;
        }
        this.tele?.setAttribute("aria-expanded", "false");
    },

    pleinEcran() {
        if (document.fullscreenElement) {
            document.exitFullscreen();
            return;
        }
        const el = this.el;
        if (el.requestFullscreen) {
            el.requestFullscreen().catch(() => {});
        } else if (el.webkitRequestFullscreen) {
            el.webkitRequestFullscreen();
        }
    },

    majPlein() {
        const on = !!document.fullscreenElement;
        const montre = this.plein.querySelector(`[data-acb-plein="${on ? "on" : "off"}"]`);
        const cache = this.plein.querySelector(`[data-acb-plein="${on ? "off" : "on"}"]`);
        montre.hidden = false;
        cache.hidden = true;
        this.plein.title = montre.textContent.trim();
    },

    doc() {
        try {
            return this.cadre && this.cadre.contentDocument;
        } catch {
            return null; // another origin: the bar keeps its first chapter
        }
    },

    brancher() {
        if (!this.cadre.getAttribute("src")) {
            return;
        }
        this.charge?.classList.add("is-fini");
        const d = this.doc();
        if (!d) {
            return;
        }
        // The remote lives in the guided viewer only: no button for a guide without one.
        if (this.tele && d.getElementById("gRemote")) {
            this.tele.hidden = false;
        }
        const etiquette = d.getElementById("stepLabel");
        if (!etiquette) {
            return;
        }
        if (this.observateur) {
            this.observateur.disconnect();
        }
        // The guide may be stepped from its own keys or from the phone: follow what it shows
        // rather than what this page asked of it.
        this.observateur = new MutationObserver(() => this.suivre(d));
        this.observateur.observe(d.body, { childList: true, characterData: true, subtree: true });
        this.suivre(d);
    },

    suivre(d) {
        const ou = d.querySelector(".gwhere");
        let chapitre = null;
        if (ou && this.chapitres.length) {
            const nom = (ou.textContent || "").split(" · ")[0].trim();
            chapitre = this.chapitres.find((c) => c.nom === nom) || null;
        }
        const m = /(\d+)\s*\/\s*(\d+)/.exec(d.getElementById("stepLabel")?.textContent || "");
        if (!chapitre && m && this.chapitres.length && !ou) {
            const couche = parseInt(m[1], 10) - this.decalage;
            chapitre = this.chapitres.find((c) => c.de <= couche && couche <= c.a) || null;
        }
        if (chapitre) {
            this.ecrire("[data-acb-chap-n]", String(chapitre.n));
            this.ecrire("[data-acb-chap-nom]", chapitre.nom);
        } else if (m && !this.chapitres.length) {
            this.ecrire("[data-acb-couche]", String(Math.max(1, parseInt(m[1], 10) - this.decalage)));
        }
    },

    ecrire(selecteur, texte) {
        const cible = this.el.querySelector(selecteur);
        if (cible && cible.textContent !== texte) {
            cible.textContent = texte;
        }
    },
});
