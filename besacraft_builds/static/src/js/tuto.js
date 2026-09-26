/** @odoo-module **/
/**
 * Fiche de tuto « Établi ».
 *
 * Le viewer 3D est un fichier autonome produit par buildplan : on ne réimplémente pas son
 * moteur, on clique ses propres commandes depuis la page hôte. C'est possible uniquement
 * parce qu'il est servi depuis notre origine (/besacraft/viewer/<id>) ; sans ça, ni
 * l'injection de style ni la lecture de l'état ne passeraient.
 *
 * Enregistré comme publicWidget et non comme script autonome : en 18.0 les assets du site
 * sont scindés en « minimal » et « lazy », et un fichier ordinaire tombe dans le lazy, que
 * rien n'évalue sur une page sans composant. Le widget, lui, démarre sur son sélecteur.
 */
import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.BesacraftTuto = publicWidget.Widget.extend({
    selector: ".bc-tuto",

    start() {
        demarrer();
        return this._super.apply(this, arguments);
    },
});

function demarrer() {
    "use strict";

    var racine = document.querySelector(".bc-tuto");
    if (!racine) {
        return;
    }

    var boite = document.getElementById("bc_donnees");
    var couches = JSON.parse((boite && boite.dataset.couches) || "[]");
    // Le viewer numérote TOUTES les couches, fondations enterrées comprises ; le tutoriel
    // commence après. Sans ce décalage, la couche 1 de la liste pilote une couche vide.
    var decalage = parseInt((boite && boite.dataset.decalage) || "0", 10) || 0;
    var vueEnsemble = false;   // position 0 : tout le build posé
    var cadre = document.getElementById("bc_viewer");
    var index = 0;
    var dejaBranche = false;

    /* ---------------------------------------------------------------- l'établi */

    function ligneBloc(b) {
        var ligne = document.createElement("div");
        ligne.className = "bc-ligne";

        var caseAcocher = document.createElement("button");
        caseAcocher.type = "button";
        caseAcocher.className = "bc-case";
        caseAcocher.title = "Marquer comme posé";
        // Cocher ne regarde que celui qui construit : c'est local, ça marche sans compte.
        caseAcocher.addEventListener("click", function () {
            ligne.classList.toggle("bc-pose");
        });

        var icone = document.createElement("img");
        icone.className = "bc-ligne-i";
        icone.src = "/web/image/besacraft.build.layer.line/" + b.id + "/icon";
        icone.alt = "";
        icone.loading = "lazy";

        var nom = document.createElement("button");
        nom.type = "button";
        nom.className = "bc-ligne-n";
        var titre = document.createElement("span");
        titre.className = "bc-ligne-nom";
        titre.textContent = b.name;
        var mod = document.createElement("span");
        mod.className = "bc-ligne-mod";
        mod.textContent = b.mod || "";
        nom.appendChild(titre);
        nom.appendChild(mod);
        nom.addEventListener("click", function () {
            ouvrirRecette(b.key);
        });

        var quantite = document.createElement("span");
        quantite.className = "bc-ligne-q";
        quantite.innerHTML = '<span class="bc-x">×</span><span class="bc-qte"></span>';
        quantite.querySelector(".bc-qte").textContent = b.qty;

        ligne.appendChild(caseAcocher);
        ligne.appendChild(icone);
        ligne.appendChild(nom);
        ligne.appendChild(quantite);
        return ligne;
    }

    function rendreCouche() {
        var c = couches[index];
        if (!c) {
            return;
        }
        document.getElementById("bc_num").textContent = String(c.sequence).padStart(2, "0");
        document.getElementById("bc_pos").textContent = c.sequence;
        document.getElementById("bc_titre").textContent = c.title || "Couche " + c.sequence;
        document.getElementById("bc_total").textContent = c.block_count;

        var liste = document.getElementById("bc_liste");
        liste.innerHTML = "";
        c.lines.forEach(function (b) {
            liste.appendChild(ligneBloc(b));
        });
        var prev = document.getElementById("bc_prev");
        var next = document.getElementById("bc_next");
        // Reculer depuis la couche 1 ne bute pas sur un bouton mort : ça remonte à
        // l'étape 0, le build entier, celle par laquelle on est arrivé.
        prev.textContent = index > 0
            ? "‹ Couche " + couches[index - 1].sequence : "‹ Le build complet";
        prev.disabled = false;
        next.textContent = index < couches.length - 1
            ? "Couche " + couches[index + 1].sequence + " ›" : "Terminé";
        next.disabled = index === couches.length - 1;

        document.getElementById("bc_cur_n").textContent = c.sequence;
        document.getElementById("bc_curseur").value = c.sequence;
        document.getElementById("bc_tout").classList.remove("bc-tout-actif");

        document.querySelectorAll(".bc-couche-carte").forEach(function (carte) {
            carte.classList.toggle("bc-cc-active",
                parseInt(carte.dataset.seq, 10) === c.sequence);
        });
    }

    function allerA(n, piloterViewer) {
        vueEnsemble = false;
        index = Math.max(0, Math.min(couches.length - 1, n));
        rendreCouche();
        if (piloterViewer) {
            pousserCurseur("#slider", couches[index].sequence + calerDecalage());
        }
    }

    function voirTout() {
        // L'étape 0, et l'état d'arrivée sur la page : avant de poser la première couche,
        // on veut voir ce qu'on va construire. C'est aussi ce que montre le viewer au
        // chargement — commencer l'établi sur la couche 1 désaccordait les deux.
        vueEnsemble = true;
        var d = doc();
        var curseur = d && d.getElementById("slider");
        if (curseur) {
            pousserCurseur("#slider", curseur.max);
        }
        document.getElementById("bc_num").textContent = "00";
        document.getElementById("bc_pos").textContent = "0";
        document.getElementById("bc_titre").textContent = "Le build complet";
        document.getElementById("bc_total").textContent =
            couches.reduce(function (t, c) { return t + c.block_count; }, 0);
        var liste = document.getElementById("bc_liste");
        liste.innerHTML = "";
        // Tous les blocs du build, cumulés par type.
        var cumul = {};
        couches.forEach(function (c) {
            c.lines.forEach(function (b) {
                if (!cumul[b.key]) {
                    cumul[b.key] = { id: b.id, name: b.name, mod: b.mod, key: b.key, qty: 0 };
                }
                cumul[b.key].qty += b.qty;
            });
        });
        Object.keys(cumul)
            .map(function (k) { return cumul[k]; })
            .sort(function (a, b) { return b.qty - a.qty; })
            .forEach(function (b) { liste.appendChild(ligneBloc(b)); });
        document.querySelectorAll(".bc-couche-carte").forEach(function (carte) {
            carte.classList.remove("bc-cc-active");
        });

        var prev = document.getElementById("bc_prev");
        var next = document.getElementById("bc_next");
        prev.textContent = "‹ Début";
        prev.disabled = true;
        next.textContent = couches.length ? "Couche " + couches[0].sequence + " ›" : "Terminé";
        next.disabled = !couches.length;

        // Le curseur compte les couches posées : à l'étape 0 elles le sont toutes, donc
        // il va au maximum. Le mettre à zéro montrerait un terrain nu, l'inverse de ce
        // qu'on regarde.
        if (couches.length) {
            var derniere = couches[couches.length - 1].sequence;
            document.getElementById("bc_curseur").value = derniere;
            document.getElementById("bc_cur_n").textContent = derniere;
        }
        document.getElementById("bc_tout").classList.add("bc-tout-actif");
    }

    document.getElementById("bc_tout").addEventListener("click", voirTout);
    document.getElementById("bc_prev").addEventListener("click", function () {
        if (index === 0 && !vueEnsemble) {
            voirTout();
        } else {
            allerA(index - 1, true);
        }
    });
    document.getElementById("bc_next").addEventListener("click", function () {
        allerA(vueEnsemble ? 0 : index + 1, true);
    });

    /* ---------------------------------------------------------------- le viewer */

    function doc() {
        try {
            return cadre && cadre.contentDocument;
        } catch (e) {
            return null;    // autre origine : on renonce au pilotage, la notice suffit
        }
    }

    function cliquer(selecteur) {
        var d = doc();
        var el = d && d.querySelector(selecteur);
        if (el) {
            el.click();
        }
    }

    function pousserCurseur(selecteur, valeur) {
        var d = doc();
        var el = d && d.querySelector(selecteur);
        if (!el) {
            return;
        }
        el.value = valeur;
        // Le viewer écoute « input » : écrire .value seul ne déclenche rien.
        el.dispatchEvent(new Event("input", { bubbles: true }));
    }

    function ouvrirRecette(cle) {
        if (!cle) {
            return;
        }
        var d = doc();
        var li = d && d.querySelector('#stepItems li[data-item="' + cle + '"]');
        if (li) {
            li.click();
        }
    }

    function masquerHabillage(d) {
        var style = d.createElement("style");
        style.textContent =
            "#hud,#stepbar,#panel{display:none!important}" +
            "#app{grid-template-columns:1fr!important;grid-template-rows:1fr!important}" +
            "#modal .box{font-family:'Anonymous Pro',monospace}";
        d.head.appendChild(style);
    }

    var CASES = [
        ["optDim", "Atténuer les couches posées"],
        ["optGhost", "Couches précédentes en transparence"],
        ["optUnder", "Couche sous la borne en transparence"],
        ["optFrame", "Cadre de la couche courante"],
        ["optGrid", "Grille"],
        ["optShadow", "Ombres"],
        ["optDecor", "Décor"],
        ["optReal", "Rendu réaliste"],
        ["optCycle", "Cycle du soleil"],
        ["optLoop", "Animation en boucle"],
        ["optKinetic", "Machines Create"],
        ["optRotate", "Rotation automatique"],
    ];

    var CURSEURS = [
        ["hour", "Heure"],
        ["mist", "Brume"],
        ["cycleSpeed", "Cycle"],
        ["rotSpeed", "Rotation"],
    ];

    function construireReglages(d) {
        var cases = document.getElementById("bc_cases");
        CASES.forEach(function (paire) {
            var source = d.getElementById(paire[0]);
            // Une option sans objet est ABSENTE du DOM du viewer (un build sans Create n'a
            // pas #optKinetic) : on masque la ligne, on ne l'affiche pas désactivée.
            if (!source) {
                return;
            }
            var etiquette = document.createElement("label");
            etiquette.className = "bc-case-l";
            var boite2 = document.createElement("input");
            boite2.type = "checkbox";
            boite2.checked = source.checked;
            boite2.addEventListener("change", function () {
                source.click();     // le viewer écoute « change », jamais .checked
                boite2.checked = source.checked;
            });
            etiquette.appendChild(boite2);
            etiquette.appendChild(document.createTextNode(paire[1]));
            cases.appendChild(etiquette);
        });

        var reglages = document.getElementById("bc_reglages");
        CURSEURS.forEach(function (paire) {
            var source = d.getElementById(paire[0]);
            if (!source) {
                return;
            }
            var bloc = document.createElement("div");
            bloc.className = "bc-reglage";
            var titre = document.createElement("span");
            titre.className = "bc-curseur-t";
            titre.textContent = paire[1];
            var curseur = document.createElement("input");
            curseur.type = "range";
            curseur.className = "bc-curseur";
            curseur.min = source.min;
            curseur.max = source.max;
            curseur.step = source.step;
            curseur.value = source.value;
            var valeur = document.createElement("span");
            valeur.className = "bc-curseur-v";
            var libelle = d.getElementById(paire[0] + "Label");
            valeur.textContent = libelle ? libelle.textContent : source.value;
            curseur.addEventListener("input", function () {
                source.value = curseur.value;
                source.dispatchEvent(new Event("input", { bubbles: true }));
                valeur.textContent = libelle ? libelle.textContent : curseur.value;
            });
            bloc.appendChild(titre);
            bloc.appendChild(curseur);
            bloc.appendChild(valeur);
            reglages.appendChild(bloc);
        });
    }

    function suivreEtape(d) {
        var etiquette = d.getElementById("stepLabel");
        if (!etiquette) {
            return;
        }
        // L'utilisateur peut naviguer au clavier dans l'iframe : on se resynchronise sur
        // l'état réel du viewer plutôt que de supposer que la page le pilote seule.
        new MutationObserver(function () {
            var m = /(\d+)\s*\/\s*\d+/.exec(etiquette.textContent || "");
            if (!m) {
                return;
            }
            // Tant qu'on est à l'étape 0, on ne suit pas le viewer. Il fait défiler son
            // étiquette pendant qu'il monte la scène, et chacune de ces valeurs de
            // passage se lirait ici comme « l'utilisateur a choisi une couche » : la page
            // basculait sur la liste de la couche 1 alors que la 3D montre tout le build.
            // On quitte l'étape 0 par un geste, jamais parce que l'iframe a bougé.
            if (vueEnsemble) {
                return;
            }
            var seq = parseInt(m[1], 10) - calerDecalage();
            var pos = couches.findIndex(function (c) { return c.sequence === seq; });
            if (pos >= 0 && pos !== index) {
                index = pos;
                rendreCouche();
            }
        }).observe(etiquette, { childList: true, characterData: true, subtree: true });
    }

    function calerDecalage() {
        // Le décalage se DÉDUIT du viewer : son curseur va de 1 à son nombre de couches,
        // le tutoriel n'en montre qu'une partie. La différence est exacte par construction,
        // là où une valeur recopiée du plan finit toujours par diverger d'une unité.
        //
        // Calculé à chaque usage et non une fois au chargement : le viewer règle le max de
        // son curseur après avoir construit la scène, donc bien après l'événement « load ».
        var d = doc();
        var curseur = d && d.getElementById("slider");
        var maxViewer = curseur ? parseInt(curseur.max, 10) : 0;
        if (maxViewer > 1 && couches.length) {
            decalage = maxViewer - couches.length;
        }
        return decalage;
    }

    function brancherViewer() {
        var d = doc();
            var voile = document.getElementById("bc_voile");
            if (voile) {
                voile.hidden = true;
            }
            if (!d) {
                return;
            }
            masquerHabillage(d);
            construireReglages(d);
            suivreEtape(d);

            // Sans recettes, le viewer laisse #btnBom sans gestionnaire et les blocs ne
            // s'ouvrent pas : on masque plutôt que de proposer un bouton mort.
            var bom = d.getElementById("btnBom");
            if (bom && bom.onclick) {
                var mien = document.getElementById("bc_bom");
                mien.hidden = false;
                mien.addEventListener("click", function () { bom.click(); });
        } else {
            racine.classList.add("bc-sans-recettes");
        }
    }

    if (cadre) {
        // L'iframe peut avoir fini AVANT que ce script ne tourne : le bundle est chargé en
        // fin de page et « load » ne se rejoue pas. On branche les deux chemins, sinon le
        // voile reste et les reglages restent vides alors que le viewer est bien la.
        cadre.addEventListener("load", brancherViewer);
        var dejaLa = doc();
        if (dejaLa && dejaLa.readyState === "complete" && dejaLa.getElementById("app")) {
            brancherViewer();
        }

        document.querySelectorAll(".bc-angle").forEach(function (bouton) {
            bouton.addEventListener("click", function () {
                if (bouton.dataset.az) {
                    cliquer('#hud [data-az="' + bouton.dataset.az + '"]');
                } else {
                    cliquer("#" + bouton.dataset.cible);
                }
            });
        });

        document.getElementById("bc_lecture").addEventListener("click", function () {
            cliquer("#play");
            var d = doc();
            var play = d && d.getElementById("play");
            var enCours = play && play.classList.contains("on");
            this.textContent = enCours ? "❚❚ Pause" : "▶ Bloc par bloc";
            // Lancer l'animation est le geste qui sort de l'étape 0 : à partir de là
            // l'établi suit le viewer couche par couche.
            if (enCours) {
                vueEnsemble = false;
            }
        });

        document.getElementById("bc_replay").addEventListener("click", function () {
            cliquer("#replay");
        });

        document.getElementById("bc_curseur").addEventListener("input", function () {
            var seq = parseInt(this.value, 10);
            var pos = couches.findIndex(function (c) { return c.sequence === seq; });
            allerA(pos >= 0 ? pos : seq - 1, true);
        });

        document.getElementById("bc_dedans").addEventListener("input", function () {
            document.getElementById("bc_dedans_v").textContent = this.value;
            pousserCurseur("#sliderLo", parseInt(this.value, 10) + calerDecalage());
        });

        document.getElementById("bc_cadence").addEventListener("input", function () {
            document.getElementById("bc_cadence_v").textContent = this.value + " ms";
            pousserCurseur("#delay", this.value);
        });

        var tiroir = document.getElementById("bc_tiroir_b");
        tiroir.addEventListener("click", function () {
            var corps = document.getElementById("bc_tiroir_c");
            corps.hidden = !corps.hidden;
            document.getElementById("bc_chevron").textContent = corps.hidden ? "▸" : "▾";
        });
    }

    /* ---------------------------------------------------------------- plein écran */

    function quitterPlein() {
        var zone = document.querySelector(".bc-scene");
        if (!zone || !zone.classList.contains("bc-plein-actif")) {
            return;
        }
        zone.classList.remove("bc-plein-actif");
        var b = document.getElementById("bc_plein_b");
        if (b) {
            b.textContent = "Plein écran";
        }
        var sortie = document.getElementById("bc_sortie");
        if (sortie) {
            sortie.hidden = true;
        }
        try {
            if (document.fullscreenElement) {
                document.exitFullscreen();
            }
        } catch (e) {
            // sans importance
        }
    }

    var sortieB = document.getElementById("bc_sortie");
    if (sortieB) {
        sortieB.addEventListener("click", quitterPlein);
    }

    var bouton = document.getElementById("bc_plein_b");
    if (bouton) {
        bouton.addEventListener("click", function () {
            var zone = document.querySelector(".bc-scene");
            var actif = zone.classList.toggle("bc-plein-actif");
            bouton.textContent = actif ? "Quitter" : "Plein écran";
            // La barre de titre disparaît sous la superposition : sans ce bouton-ci,
            // il n'y a plus aucun moyen de revenir à la page.
            var sortie = document.getElementById("bc_sortie");
            if (sortie) {
                sortie.hidden = !actif;
            }
            // L'API Fullscreen n'est pas toujours autorisée (page en iframe sans
            // allow="fullscreen") : la superposition CSS fait le travail, le reste est un
            // bonus. Et surtout : on ne démonte jamais l'iframe, sinon le viewer recharge
            // ses quelques mégaoctets.
            try {
                if (actif && document.fullscreenEnabled) {
                    zone.requestFullscreen();
                } else if (document.fullscreenElement) {
                    document.exitFullscreen();
                }
            } catch (e) {
                // sans importance : l'affichage ne dépend pas de cette API
            }
        });
        document.addEventListener("keydown", function (ev) {
            if (ev.key === "Escape") {
                quitterPlein();
            }
        });
    }

    /* ---------------------------------------------------------------- la notice */

    document.querySelectorAll(".bc-cc-voir").forEach(function (bouton2) {
        bouton2.addEventListener("click", function () {
            var seq = parseInt(bouton2.dataset.seq, 10);
            var pos = couches.findIndex(function (c) { return c.sequence === seq; });
            allerA(pos >= 0 ? pos : 0, true);
            document.getElementById("bc_plein").scrollIntoView({ behavior: "smooth" });
        });
    });

    var PAQUET = 8;
    var montrees = 4;

    function rendreNotice() {
        var cartes = document.querySelectorAll(".bc-couche-carte");
        cartes.forEach(function (carte, i) {
            carte.hidden = i >= montrees;
        });
        var plus = document.getElementById("bc_plus");
        var reste = cartes.length - montrees;
        plus.hidden = reste <= 0;
        plus.textContent = "Afficher les " + Math.min(PAQUET, reste) + " couches suivantes";
    }

    var plus = document.getElementById("bc_plus");
    if (plus) {
        plus.addEventListener("click", function () {
            montrees += PAQUET;
            rendreNotice();
        });
        rendreNotice();
    }

    voirTout();
}
