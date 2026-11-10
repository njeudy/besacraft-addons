/** @odoo-module **/
/**
 * The shop's cart: a console in the corner and a drawer, over the site's real website_sale
 * cart. A buy button toggles its product through /shop/cart/update_json -- the route the
 * shop's own pages use -- and the drawer is then rendered again by the server
 * (/builds/shop/panier), so prices, taxes and labels are the ones checkout will show.
 *
 * Without JavaScript the buttons are plain forms posting to /shop/cart/update, and the
 * console is inert: the visitor lands on the shop's cart page.
 */
import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.BesacraftShop = publicWidget.Widget.extend({
    selector: ".ac.sh",

    start() {
        const $ = (id) => document.getElementById(id);
        this.console = $("sh-console");
        this.tiroir = $("sh-tiroir");
        this.fond = $("sh-fond");
        this.liste = $("sh-liste");
        this.vide = $("sh-vide");
        this.total = $("sh-total");
        this.totalConsole = $("sh-console-tot");
        this.n = $("sh-console-n");
        this.ligne = $("sh-ligne");
        this.commande = $("sh-commande");
        if (!this.console || !this.tiroir) {
            return this._super(...arguments);
        }
        this.boutons = Array.from(this.el.querySelectorAll("[data-ajout]"));
        this.boutons.forEach((b) =>
            b.closest("form").addEventListener("submit", (ev) => {
                ev.preventDefault();
                this.basculer(b);
            })
        );
        this.console.addEventListener("click", () =>
            this.tiroir.classList.contains("is-open") ? this.fermer() : this.ouvrir()
        );
        document.getElementById("sh-ferme").addEventListener("click", () => this.fermer());
        this.fond.addEventListener("click", () => this.fermer());
        this.onKey = (ev) => {
            if (ev.key === "Escape" && this.tiroir.classList.contains("is-open")) {
                this.fermer();
            }
        };
        document.addEventListener("keydown", this.onKey);
        this.liste.addEventListener("click", (ev) => {
            const retire = ev.target.closest(".sh-tiroir__retire");
            if (retire) {
                const li = retire.closest("li");
                this.changer(+li.dataset.produit, { line_id: +li.dataset.ligne, set_qty: 0 }, "retrait");
            }
        });
        return this._super(...arguments);
    },

    destroy() {
        document.removeEventListener("keydown", this.onKey);
        this._super(...arguments);
    },

    basculer(bouton) {
        const produit = +bouton.dataset.ajout;
        if (bouton.getAttribute("aria-pressed") === "true") {
            const li = this.liste.querySelector(`li[data-produit="${produit}"]`);
            this.changer(produit, { line_id: li ? +li.dataset.ligne : undefined, set_qty: 0 }, "retrait", bouton);
        } else {
            this.changer(produit, { add_qty: 1 }, "ajout", bouton);
        }
    },

    async changer(produit, valeurs, message, bouton) {
        if (bouton) {
            bouton.setAttribute("aria-busy", "true");
        }
        try {
            await rpc("/shop/cart/update_json", { product_id: produit, display: false, ...valeurs });
            const panier = await rpc("/builds/shop/panier", {});
            this.afficher(panier);
            this.dire(message);
            this.console.classList.remove("is-bump");
            void this.console.offsetWidth;
            this.console.classList.add("is-bump");
        } catch {
            this.dire("erreur");
        } finally {
            if (bouton) {
                bouton.removeAttribute("aria-busy");
            }
        }
    },

    afficher(panier) {
        this.liste.innerHTML = panier.html;
        const plein = panier.produits.length > 0;
        this.vide.hidden = plein;
        this.total.textContent = panier.total;
        this.totalConsole.textContent = panier.total;
        this.n.textContent = panier.n;
        this.n.classList.toggle("is-vide", !panier.n);
        this.commande.setAttribute("aria-disabled", plein ? "false" : "true");
        this.boutons.forEach((b) =>
            b.setAttribute("aria-pressed", panier.produits.includes(+b.dataset.ajout) ? "true" : "false")
        );
        // The site header's cart badge, so both counters agree.
        document.querySelectorAll(".my_cart_quantity").forEach((el) => {
            el.textContent = panier.n;
            el.classList.toggle("d-none", !panier.n);
        });
    },

    dire(cle) {
        this.ligne.querySelectorAll("[data-msg]").forEach((s) => {
            s.hidden = s.dataset.msg !== cle;
        });
    },

    ouvrir() {
        this.dernierFocus = document.activeElement;
        this.tiroir.classList.add("is-open");
        this.fond.classList.add("is-open");
        this.console.setAttribute("aria-expanded", "true");
        document.getElementById("sh-ferme").focus();
    },

    fermer() {
        this.tiroir.classList.remove("is-open");
        this.fond.classList.remove("is-open");
        this.console.setAttribute("aria-expanded", "false");
        if (this.dernierFocus) {
            this.dernierFocus.focus();
        }
    },
});
