// The 3D showcase: the build's real model (its glb) mounted in a leather and brass box cut to
// its size, under glass, to turn around. The page is /builds/<n>/vitrine, framed by the
// product sheet; everything about the build is read from the <body> data attributes, and the
// words printed on the box from the #mots spans, so that they are translated with the page.
//
// A static ES module, not part of the frontend bundle: three.js and its add-ons are vendored in
// ../../lib/three and resolved through the page's import map. Nothing comes from a CDN.

import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

const d = document.body.dataset;
const mots = Object.fromEntries(
    Array.from(document.querySelectorAll("#mots [data-mot]"), (m) => [m.dataset.mot, m.textContent.trim()])
);
const B = {
    code: d.code, titre: d.titre, serie: d.serie, couleur: d.couleur,
    blocs: Number(d.blocs) || 0, couches: Number(d.couches) || 0, emprise: d.emprise,
};
const charge = document.getElementById("charge");
const err = document.getElementById("err");

function erreur(cle) {
    charge.hidden = true;
    err.hidden = false;
    err.querySelectorAll("[data-err]").forEach((e) => (e.hidden = e.dataset.err !== cle));
}

const canvas = document.getElementById("c");
let renderer;
try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
} catch (e) {
    erreur("webgl");
    throw e;
}
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.95;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const scene = new THREE.Scene();
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(renderer), 0.04).texture;
const camera = new THREE.PerspectiveCamera(30, 1, 0.5, 2000);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.enablePan = false;
controls.minAzimuthAngle = -1.1;
controls.maxAzimuthAngle = 1.1;
controls.minPolarAngle = 0.75;
controls.maxPolarAngle = 1.62;

// --- Materials -------------------------------------------------------------------------------
function cv(w, h) {
    const c = document.createElement("canvas");
    c.width = w;
    c.height = h;
    return [c, c.getContext("2d")];
}
function rnd(seed) {
    let s = seed;
    return () => (s = (s * 16807) % 2147483647) / 2147483647;
}
function cuir(ctx, w, h, c0, c1, seed) {
    const g = ctx.createRadialGradient(w * 0.42, h * 0.35, 0, w * 0.5, h * 0.5, Math.max(w, h) * 0.75);
    g.addColorStop(0, c0);
    g.addColorStop(1, c1);
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
    const r = rnd(seed || 7);
    ctx.globalAlpha = 0.07;
    for (let i = 0; i < (w * h) / 260; i++) {
        ctx.fillStyle = r() > 0.5 ? "#000" : "#FFE2C0";
        ctx.fillRect(r() * w, r() * h, 1 + r() * 2.2, 1 + r() * 1.4);
    }
    ctx.globalAlpha = 0.05;
    ctx.strokeStyle = "#000";
    for (let i = 0; i < w / 9; i++) {
        ctx.beginPath();
        const y = r() * h;
        ctx.moveTo(0, y);
        ctx.bezierCurveTo(w * 0.3, y + r() * 30 - 15, w * 0.7, y + r() * 30 - 15, w, y + r() * 20 - 10);
        ctx.stroke();
    }
    ctx.globalAlpha = 1;
}
function couture(ctx, w, h, m) {
    ctx.save();
    ctx.strokeStyle = "rgba(240,222,190,.5)";
    ctx.lineWidth = Math.max(2, m * 0.12);
    ctx.setLineDash([m * 0.42, m * 0.3]);
    ctx.strokeRect(m, m, w - 2 * m, h - 2 * m);
    ctx.restore();
}
function texCanvas(c) {
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    t.anisotropy = 8;
    return t;
}
const PX = 64; // texture pixels per block on the printed panels

const mLaiton = new THREE.MeshStandardMaterial({ color: 0xc9a862, metalness: 1, roughness: 0.32 });
const mLaitonBas = new THREE.MeshStandardMaterial({ color: 0x9a7d47, metalness: 1, roughness: 0.45 });
const mVerre = new THREE.MeshPhysicalMaterial({
    color: 0xffffff, metalness: 0, roughness: 0.02, transparent: true, opacity: 0.07,
    envMapIntensity: 1.6, clearcoat: 1, clearcoatRoughness: 0.02, depthWrite: false,
    side: THREE.DoubleSide,
});
function mCuir(w, h, c0, c1, seed, stitch) {
    const [c, x] = cv(
        Math.min(2048, Math.max(64, Math.round((w * PX) / 2))),
        Math.min(2048, Math.max(64, Math.round((h * PX) / 2)))
    );
    cuir(x, c.width, c.height, c0, c1, seed);
    if (stitch) {
        couture(x, c.width, c.height, PX * 0.35);
    }
    return new THREE.MeshStandardMaterial({ map: texCanvas(c), roughness: 0.78, metalness: 0 });
}

// --- Prints: top band (plate), bottom band (series + figures), lid --------------------------
const LOGO = new Image();
if (d.logo) {
    LOGO.src = d.logo;
}
const nb = (n) => String(n).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
function fitFont(ctx, txt, weight, family, max, avail) {
    let s = max;
    ctx.font = `${weight} ${s}px ${family}`;
    while (ctx.measureText(txt).width > avail && s > 8) {
        s -= 2;
        ctx.font = `${weight} ${s}px ${family}`;
    }
    return s;
}
function rivet(ctx, x, y, r) {
    const g = ctx.createRadialGradient(x - r * 0.3, y - r * 0.3, 0, x, y, r);
    g.addColorStop(0, "#F4E3B4");
    g.addColorStop(0.7, "#8A6E3C");
    g.addColorStop(1, "#5A4424");
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, 7);
    ctx.fill();
}
function plaque(ctx, x, y, w, h) {
    ctx.fillStyle = "#0B0907";
    ctx.fillRect(x, y + h * 0.06, w, h);
    const g = ctx.createLinearGradient(0, y, 0, y + h);
    g.addColorStop(0, "#DCC48C");
    g.addColorStop(0.55, "#C2A466");
    g.addColorStop(1, "#A88A50");
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, h * 0.08);
    ctx.fill();
    ctx.fillStyle = "rgba(255,255,255,.35)";
    ctx.fillRect(x + h * 0.08, y + 2, w - h * 0.16, Math.max(2, h * 0.025));
    const r = h * 0.045;
    const m = h * 0.1;
    [[x + m, y + m], [x + w - m, y + m], [x + m, y + h - m], [x + w - m, y + h - m]].forEach(
        ([a, b]) => rivet(ctx, a, b, r)
    );
}
function bandeauHaut(W, H) {
    const [c, x] = cv(Math.round(W * PX), Math.round(H * PX));
    const w = c.width;
    const h = c.height;
    cuir(x, w, h, "#47301F", "#271A11", 3);
    couture(x, w, h, PX * 0.4);
    const pw = Math.min(w * 0.62, PX * 30);
    const ph = h * 0.62;
    const px = (w - pw) / 2;
    const py = (h - ph) / 2 - h * 0.03;
    plaque(x, px, py, pw, ph);
    x.fillStyle = "#3A2A14";
    x.textAlign = "center";
    x.textBaseline = "alphabetic";
    x.font = `500 ${Math.round(ph * 0.16)}px "JetBrains Mono"`;
    x.fillText(`N°${B.code}`, w / 2, py + ph * 0.34);
    x.fillStyle = "#1A140E";
    fitFont(x, B.titre, "700", "Cinzel", Math.round(ph * 0.36), pw * 0.84);
    x.fillText(B.titre, w / 2, py + ph * 0.76);
    const side = (w - pw) / 2;
    if (LOGO.complete && LOGO.naturalWidth && side > h * 0.8) {
        const lh = h * 0.62;
        const lw = (lh * LOGO.naturalWidth) / LOGO.naturalHeight;
        const s = Math.min(1, (side * 0.7) / lw);
        x.drawImage(LOGO, side / 2 - (lw * s) / 2, h / 2 - (lh * s) / 2, lw * s, lh * s);
        x.drawImage(LOGO, w - side / 2 - (lw * s) / 2, h / 2 - (lh * s) / 2, lw * s, lh * s);
    }
    return texCanvas(c);
}
function bandeauBas(W, H) {
    const [c, x] = cv(Math.round(W * PX), Math.round(H * PX));
    const w = c.width;
    const h = c.height;
    cuir(x, w, h, "#422C1E", "#241810", 5);
    couture(x, w, h, PX * 0.4);
    const rh = h * 0.5;
    const ry = (h - rh) / 2;
    const t = (B.serie || "").toUpperCase();
    // The series ribbon gives way to the figures on a narrow box.
    const place = w * 0.5;
    fitFont(x, t, "700", "Cinzel", Math.round(rh * 0.42), place - rh * 1.4);
    const tw = x.measureText(t).width + rh * 1.4;
    x.fillStyle = "#0B0907";
    x.fillRect(PX * 1.2, ry + rh * 0.1, tw, rh);
    x.fillStyle = B.couleur;
    x.fillRect(PX * 1.2, ry, tw, rh);
    const g = x.createLinearGradient(0, ry, 0, ry + rh);
    g.addColorStop(0, "#DCC48C");
    g.addColorStop(1, "#A88A50");
    x.fillStyle = g;
    x.fillRect(PX * 1.2 - rh * 0.18, ry, rh * 0.18, rh);
    x.save();
    x.strokeStyle = "rgba(255,240,220,.55)";
    x.setLineDash([rh * 0.12, rh * 0.08]);
    x.lineWidth = 2;
    x.strokeRect(PX * 1.2 + rh * 0.14, ry + rh * 0.14, tw - rh * 0.28, rh * 0.72);
    x.restore();
    x.fillStyle = "#FBF3E2";
    x.textAlign = "left";
    x.textBaseline = "middle";
    x.fillText(t, PX * 1.2 + rh * 0.7, ry + rh * 0.54);
    x.textAlign = "right";
    x.fillStyle = "#E6CF97";
    const dispo = w - tw - PX * 4;
    fitFont(x, `${nb(B.blocs)} ${mots.blocs}`, "700", '"JetBrains Mono"', Math.round(h * 0.24), dispo);
    x.fillText(`${nb(B.blocs)} ${mots.blocs}`, w - PX * 1.4, h * 0.4);
    x.fillStyle = "#C9AE72";
    const ligne = `${B.couches} ${mots.couches} · ${mots.emprise} ${B.emprise}`;
    fitFont(x, ligne, "500", '"JetBrains Mono"', Math.round(h * 0.15), dispo);
    x.fillText(ligne, w - PX * 1.4, h * 0.68);
    return texCanvas(c);
}
function dessus(W, D) {
    const [c, x] = cv(Math.round((W * PX) / 2), Math.round((D * PX) / 2));
    const w = c.width;
    const h = c.height;
    cuir(x, w, h, "#47301F", "#271A11", 9);
    couture(x, w, h, PX * 0.2);
    x.fillStyle = B.couleur;
    x.fillRect(w * 0.08, 0, h * 0.22, h);
    x.fillStyle = "#E6CF97";
    x.textAlign = "center";
    x.textBaseline = "middle";
    const t = `◆ ${B.titre.toUpperCase()} ◆`;
    fitFont(x, t, "700", "Cinzel", Math.round(h * 0.22), w * 0.7);
    x.fillText(t, w * 0.56, h / 2);
    return texCanvas(c);
}
function fond(W, H) {
    const [c, x] = cv(1024, Math.max(16, Math.round((1024 * H) / W)));
    const w = c.width;
    const h = c.height;
    const g = x.createRadialGradient(w * 0.5, h * 0.42, 0, w * 0.5, h * 0.5, w * 0.7);
    g.addColorStop(0, "#6B4C36");
    g.addColorStop(0.6, "#432E21");
    g.addColorStop(1, "#2A1C13");
    x.fillStyle = g;
    x.fillRect(0, 0, w, h);
    // One-block grid, as on the plan.
    x.strokeStyle = "rgba(201,174,114,.10)";
    x.lineWidth = 1;
    const s = w / W;
    for (let i = 0; i <= W; i++) {
        x.beginPath();
        x.moveTo(i * s, 0);
        x.lineTo(i * s, h);
        x.stroke();
    }
    for (let j = 0; j <= H; j++) {
        x.beginPath();
        x.moveTo(0, h - j * s);
        x.lineTo(w, h - j * s);
        x.stroke();
    }
    return texCanvas(c);
}

// --- The box, cut to the build -------------------------------------------------------------
const verre = [];
const box = (w, h, dd, m, x, y, z) => {
    const o = new THREE.Mesh(new THREE.BoxGeometry(w, h, dd), m);
    o.position.set(x, y, z);
    o.castShadow = true;
    o.receiveShadow = true;
    return o;
};

function lumieres(H, bbas, ih, iw, id, zb) {
    const g = new THREE.Group();
    const spot = new THREE.SpotLight(0xffe3b8, 2.6, 0, Math.atan2(Math.max(iw, id), ih) * 0.9, 0.7, 0);
    spot.position.set(0, bbas + ih - 0.3, zb + 0.6 + id * 0.62);
    spot.target.position.set(0, bbas, zb + 0.6 + id / 2);
    spot.castShadow = true;
    spot.shadow.mapSize.set(2048, 2048);
    spot.shadow.bias = -0.0004;
    spot.shadow.normalBias = 0.02;
    g.add(spot, spot.target);
    const inner = new THREE.PointLight(0xffd9a8, 1.2, 0, 0);
    inner.position.set(0, bbas + ih * 0.6, zb + id);
    g.add(inner);
    // A ramp behind the top of the bezel lights the build's front faces, which the ceiling
    // ramp leaves in the shade.
    const face = new THREE.SpotLight(0xffe8c8, 1.6, 0, 0.9, 0.8, 0);
    face.position.set(0, bbas + ih - 0.4, zb + 0.6 + id - 0.3);
    face.target.position.set(0, bbas + ih * 0.2, zb + 0.6 + id * 0.4);
    g.add(face, face.target);
    return g;
}

function monter(model) {
    const coffret = new THREE.Group();
    scene.add(coffret);

    // The build sits at the origin, turned to show its long side to the glass.
    const bb = new THREE.Box3().setFromObject(model);
    const sz = bb.getSize(new THREE.Vector3());
    const piv = new THREE.Group();
    piv.add(model);
    model.position.set(-(bb.min.x + sz.x / 2), -bb.min.y, -(bb.min.z + sz.z / 2));
    if (sz.z > sz.x * 1.15) {
        piv.rotation.y = Math.PI / 2;
    }
    const bw = piv.rotation.y ? sz.z : sz.x;
    const bd = piv.rotation.y ? sz.x : sz.z;
    const bh = sz.y;

    // The box hugs the build: walls flush with its bounding box (a breath against z-fighting).
    const m = 0.02;
    const t = Math.max(1.2, bw * 0.035);
    const ps = bh < bw * 0.45 ? 1.4 : 0.8; // a low build stands on a higher base
    const iw = bw + 2 * m;
    const id = bd + 2 * m;
    const ih = bh + Math.max(2.5, bh * 0.12) + ps;
    const hb = Math.max(5, iw * 0.16);
    const bbas = Math.max(3.6, iw * 0.1);
    const W = iw + 2 * t;
    const D = id + t + 0.6;
    const H = bbas + ih + hb;
    const zf = D / 2;
    const zb = -D / 2;

    const leather = mCuir(W, H, "#3F2A1D", "#21160F", 11, false);
    const leatherSide = mCuir(D, H, "#3A261A", "#1E140D", 13, true);
    const imprime = (tex) => new THREE.MeshStandardMaterial({ map: tex, roughness: 0.7 });
    // Front: top band, bottom band, two posts; the glass between them.
    coffret.add(box(W, hb, t, [leather, leather, leather, leather, imprime(bandeauHaut(W, hb)), leather], 0, H - hb / 2, zf - t / 2));
    coffret.add(box(W, bbas, t, [leather, leather, leather, leather, imprime(bandeauBas(W, bbas)), leather], 0, bbas / 2, zf - t / 2));
    coffret.add(box(t, ih, t, leather, -W / 2 + t / 2, bbas + ih / 2, zf - t / 2));
    coffret.add(box(t, ih, t, leather, W / 2 - t / 2, bbas + ih / 2, zf - t / 2));
    // Sides, back, lid, bottom.
    coffret.add(box(t, H, D - t, leatherSide, -W / 2 + t / 2, H / 2, -t / 2));
    coffret.add(box(t, H, D - t, leatherSide, W / 2 - t / 2, H / 2, -t / 2));
    coffret.add(box(W - 2 * t, H, 0.6, leather, 0, H / 2, zb + 0.3));
    const mTop = new THREE.MeshStandardMaterial({ map: dessus(W, D), roughness: 0.75 });
    coffret.add(box(W, 0.9, D, [leather, leather, mTop, leather, leather, leather], 0, H + 0.45, 0));
    coffret.add(box(W, bbas, D - t, leather, 0, bbas / 2, -t / 2));
    // Inside: gridded back, velvet walls, a wooden base rimmed with brass.
    const velours = new THREE.MeshStandardMaterial({ color: 0x3a281c, roughness: 0.95 });
    const back = new THREE.Mesh(new THREE.PlaneGeometry(iw, ih), new THREE.MeshStandardMaterial({ map: fond(iw, ih), roughness: 0.9 }));
    back.position.set(0, bbas + ih / 2, zb + 0.61);
    back.receiveShadow = true;
    coffret.add(back);
    const ceil = new THREE.Mesh(new THREE.PlaneGeometry(iw, id), velours);
    ceil.rotation.x = Math.PI / 2;
    ceil.position.set(0, bbas + ih - 0.01, zb + 0.6 + id / 2);
    coffret.add(ceil);
    coffret.add(box(iw, ps, id, new THREE.MeshStandardMaterial({ color: 0x5a3b24, roughness: 0.6 }), 0, bbas + ps / 2, zb + 0.6 + id / 2));
    coffret.add(box(iw, 0.25, 0.25, mLaiton, 0, bbas + ps, zf - t - 0.1));
    piv.position.set(0, bbas + ps, zb + 0.6 + id / 2);
    coffret.add(piv);
    // Brass: bezel around the glass, angle irons on the edges, corners, rivets.
    const lb = 0.45;
    const lz = zf + 0.12;
    coffret.add(box(iw + 2 * lb, lb, 0.45, mLaiton, 0, bbas + ih + lb / 2 - 0.05, lz - 0.1));
    coffret.add(box(iw + 2 * lb, lb, 0.45, mLaiton, 0, bbas - lb / 2 + 0.05, lz - 0.1));
    coffret.add(box(lb, ih, 0.45, mLaiton, -iw / 2 - lb / 2, bbas + ih / 2, lz - 0.1));
    coffret.add(box(lb, ih, 0.45, mLaiton, iw / 2 + lb / 2, bbas + ih / 2, lz - 0.1));
    const a = 0.35;
    const e = 0.5;
    [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(([sx, sz2]) => {
        coffret.add(box(e, H + 0.9, e, mLaitonBas, sx * (W / 2 - e / 2 + 0.05), (H + 0.9) / 2, sz2 * (D / 2 - e / 2 + 0.05)));
        [0, H + 0.9].forEach((y) =>
            coffret.add(box(1.3, 1.3, 1.3, mLaiton, sx * (W / 2 - 0.55), y + (y ? -0.55 : 0.55), sz2 * (D / 2 - 0.55)))
        );
    });
    [0, H + 0.9].forEach((y) =>
        [-1, 1].forEach((sz2) =>
            coffret.add(box(W - 2, a, a, mLaitonBas, 0, y + (y ? -a / 2 : a / 2), sz2 * (D / 2 - a / 2 + 0.05)))
        )
    );
    [0, H + 0.9].forEach((y) =>
        [-1, 1].forEach((sx) =>
            coffret.add(box(a, a, D - 2, mLaitonBas, sx * (W / 2 - a / 2 + 0.05), y + (y ? -a / 2 : a / 2), 0))
        )
    );
    const rv = new THREE.SphereGeometry(0.16, 12, 8);
    const nv = Math.max(1, Math.round(ih / 3));
    for (let i = 0; i <= nv; i++) {
        const y = bbas + 0.6 + (i * (ih - 1.2)) / nv;
        [-1, 1].forEach((s) => {
            const r = new THREE.Mesh(rv, mLaiton);
            r.position.set(s * (iw / 2 + lb / 2), y, lz + 0.15);
            coffret.add(r);
        });
    }
    const nh = Math.max(1, Math.round(iw / 3));
    for (let i = 0; i <= nh; i++) {
        const x = -iw / 2 + 0.6 + (i * (iw - 1.2)) / nh;
        [bbas - lb / 2 + 0.05, bbas + ih + lb / 2 - 0.05].forEach((y) => {
            const r = new THREE.Mesh(rv, mLaiton);
            r.position.set(x, y, lz + 0.15);
            coffret.add(r);
        });
    }
    // The glass and its reflection.
    const glass = new THREE.Mesh(new THREE.PlaneGeometry(iw, ih), mVerre);
    glass.position.set(0, bbas + ih / 2, zf - t * 0.35);
    glass.renderOrder = 2;
    coffret.add(glass);
    verre.push(glass);
    const [rc, rx] = cv(512, 512);
    const rg = rx.createLinearGradient(0, 0, 512, 512);
    [[0, 0], [0.18, 0], [0.26, 0.22], [0.31, 0.06], [0.36, 0], [0.6, 0], [0.64, 0.1], [0.7, 0], [1, 0]].forEach(
        ([o, al]) => rg.addColorStop(o, `rgba(255,248,235,${al})`)
    );
    rx.fillStyle = rg;
    rx.fillRect(0, 0, 512, 512);
    const refl = new THREE.Mesh(
        new THREE.PlaneGeometry(iw, ih),
        new THREE.MeshBasicMaterial({ map: texCanvas(rc), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending })
    );
    refl.position.copy(glass.position).z += 0.01;
    refl.renderOrder = 3;
    coffret.add(refl);
    verre.push(refl);

    coffret.add(lumieres(H, bbas, ih, iw, id, zb));
    return { w: W, h: H + 0.9, d: D, bas: bh < bw * 0.45 };
}

const key = new THREE.DirectionalLight(0xfff1dc, 2.2);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
key.shadow.bias = -0.0005;
scene.add(key, key.target);
const rim = new THREE.DirectionalLight(0x9fb6d6, 0.6);
scene.add(rim);
scene.add(new THREE.HemisphereLight(0xfff2dd, 0x2a1c13, 0.35));
const sol = new THREE.Mesh(new THREE.PlaneGeometry(1, 1), new THREE.ShadowMaterial({ opacity: 0.5 }));
sol.rotation.x = -Math.PI / 2;
sol.receiveShadow = true;
scene.add(sol);

// --- Loading ---------------------------------------------------------------------------------
function charger() {
    const texte = charge.dataset.texteCharge;
    return new Promise((ok, ko) =>
        new GLTFLoader().load(
            d.glb,
            (g) => {
                g.scene.traverse((o) => {
                    if (!o.isMesh) {
                        return;
                    }
                    o.castShadow = true;
                    o.receiveShadow = true;
                    (Array.isArray(o.material) ? o.material : [o.material]).forEach((mt) => {
                        mt.metalness = 0;
                        mt.roughness = 0.82;
                        mt.envMapIntensity = 0.5;
                        if (mt.map) {
                            mt.map.magFilter = THREE.NearestFilter;
                            mt.map.minFilter = THREE.NearestFilter;
                            mt.map.generateMipmaps = false;
                        }
                    });
                });
                ok(g.scene);
            },
            (ev) => {
                if (ev.total) {
                    charge.textContent = `${texte} ${Math.round((ev.loaded / ev.total) * 100)} %`;
                }
            },
            ko
        )
    );
}

let dims = null;
let EL = 0.2;
function cadrer() {
    const { w, h, d: dd } = dims;
    const big = Math.max(w, h * camera.aspect * 0.9, dd);
    const cy = h * 0.5;
    controls.target.set(0, cy, 0);
    // The sphere around the box fits in the field, in height as in width.
    const r = 0.5 * Math.hypot(w, h, dd);
    const vf = THREE.MathUtils.degToRad(camera.fov) / 2;
    const hf = Math.atan(Math.tan(vf) * camera.aspect);
    const dist = (r / Math.sin(Math.min(vf, hf))) * 0.92;
    EL = dims.bas ? 0.3 : 0.2; // a low build is looked at from higher up
    const az = 0.42;
    camera.position.set(Math.sin(az) * Math.cos(EL) * dist, cy + Math.sin(EL) * dist, Math.cos(az) * Math.cos(EL) * dist);
    camera.near = dist / 50;
    camera.far = dist * 6;
    camera.updateProjectionMatrix();
    controls.minDistance = dist * 0.45;
    controls.maxDistance = dist * 1.6;
    controls.update();
    const s = big * 2.2;
    key.position.set(-w * 0.9, h * 1.6, dd * 2.2 + w * 0.4);
    key.target.position.set(0, h * 0.3, 0);
    const sc = key.shadow.camera;
    sc.left = sc.bottom = -s / 2;
    sc.right = sc.top = s / 2;
    sc.near = 1;
    sc.far = s * 3;
    sc.updateProjectionMatrix();
    rim.position.set(w, h * 0.8, -dd * 2);
    sol.scale.set(s * 2, s * 2, 1);
}

function taille() {
    const w = window.innerWidth;
    const h = window.innerHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    if (dims) {
        cadrer();
    }
}
window.addEventListener("resize", taille);
taille();

document.getElementById("bVitre").addEventListener("click", (e) => {
    const on = e.currentTarget.getAttribute("aria-pressed") !== "true";
    e.currentTarget.setAttribute("aria-pressed", on);
    verre.forEach((v) => (v.visible = on));
});

// A slight sway while nobody touches anything; none at all under prefers-reduced-motion.
const reduit = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
let touche = reduit;
controls.addEventListener("start", () => (touche = true));
const t0 = performance.now();
renderer.setAnimationLoop(() => {
    if (!touche && dims) {
        const t = (performance.now() - t0) / 1000;
        const r = camera.position.distanceTo(controls.target);
        const az = 0.42 + Math.sin(t * 0.25) * 0.32;
        const el = EL + Math.sin(t * 0.17) * 0.05;
        camera.position.set(Math.sin(az) * Math.cos(el) * r, controls.target.y + Math.sin(el) * r, Math.cos(az) * Math.cos(el) * r);
    }
    controls.update();
    renderer.render(scene, camera);
});

(async () => {
    await Promise.all([
        document.fonts.load('700 40px Cinzel'),
        document.fonts.load('700 40px "JetBrains Mono"'),
        document.fonts.load('500 40px "JetBrains Mono"'),
    ]).catch(() => {});
    if (d.logo && !LOGO.complete) {
        await new Promise((r) => {
            LOGO.onload = LOGO.onerror = r;
        });
    }
    const model = await charger();
    dims = monter(model);
    cadrer();
    charge.hidden = true;
    window.__vitrinePrete = true;
})().catch((e) => {
    erreur("modele");
    console.error(e);
});
