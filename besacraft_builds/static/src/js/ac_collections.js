/** @odoo-module **/
/**
 * Collections page: search with a live preview, filters (series, access), sort, and a grid
 * that rearranges itself with an animation.
 *
 * Everything runs on the cards already in the page (data-n, data-nom, data-series,
 * data-series-noms, data-acces, data-blocs, data-couches): the catalogue is a few dozen
 * cards, and a round trip per click would be slower than hiding them. Without JavaScript the
 * page stays complete, just not filtered. The words the script needs live in the markup
 * (`[data-ac-textes]`) so they are translated like the rest of the page.
 *
 * The rearrangement is FLIP with the Web Animations API: each card that stays glides from its
 * old place to the new one (520 ms), the ones that come back appear in a cascade. Nothing
 * moves under prefers-reduced-motion.
 *
 * A public widget rather than a plain script, as for the other pages of the module: an
 * ordinary script ends up in the "lazy" bundle of the site, which nothing evaluates.
 */
import publicWidget from "@web/legacy/js/public/public_widget";

const plat = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

publicWidget.registry.BesacraftCollections = publicWidget.Widget.extend({
    selector: ".ac-collections",

    start() {
        this.grille = this.el.querySelector(".ac-grille");
        this.cartes = Array.from(this.grille.querySelectorAll(".ac-build"));
        this.aucun = this.el.querySelector(".ac-aucun");
        this.q = this.el.querySelector("#ac-q");
        this.liste = this.el.querySelector("#ac-apercu");
        this.nEl = this.el.querySelector(".ac-compte__n");
        this.motEl = this.el.querySelector(".ac-compte__mot");
        this.raz = this.el.querySelector(".ac-filtres .ac-raz");
        this.calme = window.matchMedia("(prefers-reduced-motion: reduce)");
        this.premier = true;
        this.sel = -1;
        this.etat = { serie: "", acces: "", tri: "n" };
        this.cartes.forEach((c) => {
            c._q = plat(`${c.dataset.n} ${c.dataset.nom} ${c.dataset.seriesNoms || ""}`);
        });

        this.el.querySelectorAll(".ac-puces").forEach((g) => {
            g.addEventListener("click", (e) => {
                const b = e.target.closest(".ac-puce");
                if (b) {
                    this._choisir(g.dataset.filtre, b.dataset.val);
                    this._appliquer();
                }
            });
        });
        this.q.addEventListener("input", () => { this._appliquer(); this._apercu(); });
        this.q.addEventListener("keydown", (e) => this._touche(e));
        this.q.addEventListener("focus", () => { if (this.q.value.trim()) { this._apercu(); } });
        this.q.addEventListener("blur", () => setTimeout(() => this._fermer(), 120));
        this.liste.addEventListener("mousedown", (e) => this._clicApercu(e));
        this.el.querySelectorAll(".ac-raz").forEach((b) => {
            b.addEventListener("click", () => this._toutAfficher());
        });
        // « / » focuses the search, as on most catalogues.
        this._onSlash = (e) => {
            if (e.key === "/" && document.activeElement !== this.q
                && !/input|textarea|select/i.test(document.activeElement.tagName)) {
                e.preventDefault();
                this.q.focus();
            }
        };
        document.addEventListener("keydown", this._onSlash);

        // Deep link from a series page: ?serie=schematics
        const s = new URLSearchParams(window.location.search).get("serie");
        if (s && this.el.querySelector(`[data-filtre="serie"] [data-val="${CSS.escape(s)}"]`)) {
            this._choisir("serie", s);
        }
        this._appliquer();
        return this._super(...arguments);
    },

    destroy() {
        document.removeEventListener("keydown", this._onSlash);
        this._super(...arguments);
    },

    _texte(cle) {
        const el = this.el.querySelector(`[data-ac-textes] [data-k="${cle}"]`);
        return el ? el.textContent.trim() : "";
    },

    _choisir(groupe, val) {
        this.etat[groupe] = val;
        this.el.querySelectorAll(`[data-filtre="${groupe}"] .ac-puce`).forEach((b) => {
            b.setAttribute("aria-pressed", b.dataset.val === val ? "true" : "false");
        });
    },

    _appliquer() {
        const { serie, acces, tri } = this.etat;
        const animer = !this.premier && !this.calme.matches;
        const avant = new Map();
        if (animer) {
            this.cartes.forEach((c) => { if (!c.hidden) { avant.set(c, c.getBoundingClientRect()); } });
        }
        const mots = plat(this.q.value.trim()).split(/\s+/).filter(Boolean);
        let n = 0;
        this.cartes.forEach((c) => {
            const ok = (!serie || c.dataset.series.split(" ").includes(serie))
                && (!acces || c.dataset.acces === acces)
                && mots.every((m) => c._q.includes(m));
            c.hidden = !ok;
            if (ok) { n++; }
        });
        this.cartes.slice().sort((a, b) => (tri === "n"
            ? a.dataset.n.localeCompare(b.dataset.n)
            : (+b.dataset[tri] - +a.dataset[tri]) || a.dataset.n.localeCompare(b.dataset.n))
        ).forEach((c) => this.grille.appendChild(c));
        this.nEl.textContent = n;
        this.motEl.textContent = this._texte(n === 1 ? "un" : "plusieurs");
        this.aucun.hidden = n > 0;
        const dit = this.aucun.querySelector(".ac-aucun__dit");
        dit.textContent = this._texte(!n && serie && !acces && !mots.length ? "vide_serie" : "vide");
        this.raz.hidden = !(serie || acces || mots.length);
        if (animer) {
            let k = 0;
            this.cartes.forEach((c) => {
                if (c.hidden) { return; }
                const r = c.getBoundingClientRect(), a = avant.get(c);
                if (a) {
                    const dx = a.left - r.left, dy = a.top - r.top;
                    if (dx || dy) {
                        c.animate([{ transform: `translate(${dx}px,${dy}px)` }, { transform: "none" }],
                            { duration: 520, easing: "cubic-bezier(.22,1,.36,1)" });
                    }
                } else {
                    c.animate([{ opacity: 0, transform: "translateY(14px) scale(.96)" }, { opacity: 1, transform: "none" }],
                        { duration: 420, delay: Math.min(k++, 8) * 45, easing: "cubic-bezier(.22,1,.36,1)", fill: "backwards" });
                }
            });
        }
        this.premier = false;
    },

    // --- Preview while typing: the first 6 visible cards, with a direct launch link ---------------
    _fermer() {
        this.liste.hidden = true;
        this.q.setAttribute("aria-expanded", "false");
        this.q.removeAttribute("aria-activedescendant");
        this.sel = -1;
    },

    _apercu() {
        const v = this.q.value.trim();
        if (!v) {
            this._fermer();
            return;
        }
        const vues = this.cartes.filter((c) => !c.hidden);
        this.liste.replaceChildren();
        vues.slice(0, 6).forEach((c, i) => {
            const img = c.querySelector(".ac-build__boite img");
            const lancer = c.querySelector(".ac-build__lancer");
            const etat = c.querySelector(".ac-build__etat").textContent.trim();
            const series = Array.from(c.querySelectorAll(".ac-badge")).map((b) => b.textContent.trim()).join(" · ");
            const li = document.createElement("li");
            li.setAttribute("role", "option");
            li.id = `ac-ap-${i}`;
            li.setAttribute("aria-selected", "false");
            li.dataset.n = c.dataset.n;
            const vig = document.createElement("span");
            vig.className = "ac-apercu__vig";
            if (img) {
                const im = document.createElement("img");
                im.src = img.getAttribute("src");
                im.alt = "";
                vig.appendChild(im);
            } else {
                vig.innerHTML = '<svg viewBox="0 0 72 72" fill="none" stroke="#36CFC0" stroke-width="2.4" aria-hidden="true"><path d="M36 8 62 22v28L36 64 10 50V22z"/><path d="M10 22l26 14 26-14M36 36v28" opacity=".6"/></svg>';
            }
            const corps = document.createElement("span");
            const n = document.createElement("span");
            n.className = "ac-apercu__n";
            n.textContent = `N°${c.dataset.n} · ${etat}`;
            const nom = document.createElement("span");
            nom.className = "ac-apercu__nom";
            nom.textContent = c.dataset.nom;
            const meta = document.createElement("span");
            meta.className = "ac-apercu__meta";
            const m1 = document.createElement("mark");
            m1.textContent = c.dataset.couches;
            const m2 = document.createElement("mark");
            m2.textContent = (+c.dataset.blocs).toLocaleString(document.documentElement.lang || undefined);
            meta.append(`${series} · `, m1, ` ${this._texte("couches")} · `, m2, ` ${this._texte("blocs")}`);
            corps.append(n, nom, meta);
            const go = document.createElement("a");
            go.className = "ac-apercu__lancer";
            go.href = lancer.getAttribute("href");
            go.textContent = this._texte("lancer");
            li.append(vig, corps, go);
            this.liste.appendChild(li);
        });
        const note = (cls, texte) => {
            const li = document.createElement("li");
            li.className = cls;
            li.textContent = texte;
            this.liste.appendChild(li);
            return li;
        };
        if (!vues.length) {
            note("ac-apercu__rien", this._texte("aucun").replace("%s", v));
        } else if (vues.length > 6) {
            note("ac-apercu__tout", this._texte("tous").replace("%s", vues.length)).dataset.tout = "1";
        }
        this.liste.hidden = false;
        this.q.setAttribute("aria-expanded", "true");
        this.sel = -1;
    },

    _montrer(n) {
        const c = this.cartes.find((x) => x.dataset.n === n);
        this._fermer();
        if (c) {
            c.scrollIntoView({ behavior: this.calme.matches ? "auto" : "smooth", block: "center" });
            c.classList.add("ac-build--vue");
            setTimeout(() => c.classList.remove("ac-build--vue"), 1600);
        }
    },

    _clicApercu(e) {
        if (e.target.closest(".ac-apercu__lancer")) {
            return; // the link opens the build
        }
        e.preventDefault();
        const li = e.target.closest("li");
        if (!li) {
            return;
        }
        if (li.dataset.tout) {
            this._fermer();
            this.el.querySelector("#ac-grille").scrollIntoView({ behavior: this.calme.matches ? "auto" : "smooth" });
        } else if (li.dataset.n) {
            this._montrer(li.dataset.n);
        }
    },

    _touche(e) {
        const items = Array.from(this.liste.querySelectorAll('li[role="option"]'));
        if (e.key === "Escape") {
            this._fermer();
            return;
        }
        if (!items.length || this.liste.hidden) {
            return;
        }
        if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            this.sel = (this.sel + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
            items.forEach((li, i) => li.setAttribute("aria-selected", i === this.sel ? "true" : "false"));
            this.q.setAttribute("aria-activedescendant", items[this.sel].id);
            items[this.sel].scrollIntoView({ block: "nearest" });
        } else if (e.key === "Enter" && this.sel > -1) {
            e.preventDefault();
            window.location.href = items[this.sel].querySelector(".ac-apercu__lancer").getAttribute("href");
        }
    },

    _toutAfficher() {
        this._choisir("serie", "");
        this._choisir("acces", "");
        this.q.value = "";
        this._appliquer();
        this._fermer();
    },
});

/**
 * The site's header turns fixed once the visitor scrolls; the sticky bars of these pages have
 * to stop below it, not under it. `--ac-top` carries the header's height while it is fixed.
 */
publicWidget.registry.BesacraftHeaderOffset = publicWidget.Widget.extend({
    selector: ".ac",

    start() {
        this.header = document.querySelector("header#top");
        this._maj = () => {
            const fixe = this.header && window.getComputedStyle(this.header).position === "fixed";
            const h = fixe ? Math.max(0, this.header.getBoundingClientRect().bottom) : 0;
            this.el.style.setProperty("--ac-top", `${Math.round(h)}px`);
        };
        window.addEventListener("scroll", this._maj, { passive: true });
        window.addEventListener("resize", this._maj);
        this._maj();
        return this._super(...arguments);
    },

    destroy() {
        window.removeEventListener("scroll", this._maj);
        window.removeEventListener("resize", this._maj);
        this._super(...arguments);
    },
});
