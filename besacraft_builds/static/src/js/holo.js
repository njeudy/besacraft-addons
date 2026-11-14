// Hologram of the v2 pages: one build drawn as a projector grid that builds itself layer by
// layer. Two modes, set by `data-ac-holo`:
//   fond   fixed backdrop of the home and series pages, driven by the scroll;
//   hublot a porthole in the collections header, driven by time.
// The page picks the build on the server (`data-code`, and `data-serie` on a series page) and
// the positions come from /besacraft/holo. Decoration only: when WebGL is missing, the visitor
// prefers reduced motion or no build could be drawn, the finished build shows as a still picture
// (the `is-fixe` class) or the element is dropped (`is-vide`).
//
// A static ES module, not part of the frontend bundle: it `import`s three.js, which is vendored
// in ../../lib/three so that nothing is fetched from a CDN.

const holo = document.querySelector("[data-ac-holo]");
const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function fallback() {
    holo.classList.add(holo.querySelector(".ac-holo__fixe") ? "is-fixe" : "is-vide");
    document.querySelectorAll(".ac-lecture").forEach((el) => {
        if (!holo.contains(el)) {
            el.hidden = true;
        }
    });
}

async function fetchBuild() {
    const params = new URLSearchParams();
    if (holo.dataset.code) {
        params.set("code", holo.dataset.code);
    } else if (holo.dataset.serie) {
        params.set("serie", holo.dataset.serie);
    }
    try {
        const response = await fetch("/besacraft/holo?" + params.toString(), { credentials: "same-origin" });
        const data = (await response.json()).build;
        return data && data.taille && data.couches ? data : null;
    } catch (e) {
        return null;
    }
}

async function start() {
    if (!holo) {
        return;
    }
    if (reduced) {
        return fallback();
    }
    let THREE;
    try {
        THREE = await import("../../lib/three/three.module.min.js");
    } catch (e) {
        return fallback();
    }
    const canvas = holo.querySelector("canvas");
    let renderer;
    try {
        renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "low-power" });
    } catch (e) {
        return fallback();
    }
    const data = await fetchBuild();
    if (!data) {
        return fallback();
    }
    const mode = holo.dataset.acHolo;
    const root = holo.closest(".ac");
    const lecture = holo.querySelector(".ac-lecture") || root.querySelector(".ac-lecture");

    // Geometry: the exposed faces and their edges, each vertex tagged with the order its
    // block is laid in; the shader only shows the blocks already laid (the others as a plan).
    const [X, Y, Z] = data.taille;
    // The camera was tuned on a build of diagonal 56.6: other builds keep the same framing.
    const K = Math.max(0.45, Math.hypot(X, Y, Z) / 56.6);
    const occ = new Uint8Array(X * Y * Z);
    const blocks = [];
    data.couches.forEach((c, y) => {
        for (let i = 0; i + 1 < c.length; i += 2) {
            blocks.push([c[i], y, c[i + 1]]);
            occ[c[i] + X * (c[i + 1] + Z * y)] = 1;
        }
    });
    const has = (x, y, z) => x >= 0 && y >= 0 && z >= 0 && x < X && y < Y && z < Z && occ[x + X * (z + Z * y)] === 1;
    const FACES = [
        [[0, 1, 0], [[0, 1, 0], [1, 1, 0], [1, 1, 1], [0, 1, 1]], 1.0],
        [[0, -1, 0], [[0, 0, 0], [0, 0, 1], [1, 0, 1], [1, 0, 0]], 0.5],
        [[1, 0, 0], [[1, 0, 0], [1, 0, 1], [1, 1, 1], [1, 1, 0]], 0.7],
        [[-1, 0, 0], [[0, 0, 0], [0, 1, 0], [0, 1, 1], [0, 0, 1]], 0.7],
        [[0, 0, 1], [[0, 0, 1], [0, 1, 1], [1, 1, 1], [1, 0, 1]], 0.55],
        [[0, 0, -1], [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], 0.55],
    ];
    const fp = [], fi = [], fs = [], ep = [], ei = [];
    const layerOf = new Int16Array(blocks.length);
    blocks.forEach(([x, y, z], idx) => {
        layerOf[idx] = y;
        for (const [n, corners, shade] of FACES) {
            if (has(x + n[0], y + n[1], z + n[2])) {
                continue;
            }
            const v = corners.map((c) => [x + c[0] - X / 2, y + c[1] - Y / 2, z + c[2] - Z / 2]);
            for (const k of [0, 1, 2, 0, 2, 3]) {
                fp.push(...v[k]);
                fi.push(idx);
                fs.push(shade);
            }
            for (let k = 0; k < 4; k++) {
                ep.push(...v[k], ...v[(k + 1) % 4]);
                ei.push(idx, idx);
            }
        }
    });
    const geoF = new THREE.BufferGeometry();
    geoF.setAttribute("position", new THREE.Float32BufferAttribute(fp, 3));
    geoF.setAttribute("aIdx", new THREE.Float32BufferAttribute(fi, 1));
    geoF.setAttribute("aShade", new THREE.Float32BufferAttribute(fs, 1));
    const geoE = new THREE.BufferGeometry();
    geoE.setAttribute("position", new THREE.Float32BufferAttribute(ep, 3));
    geoE.setAttribute("aIdx", new THREE.Float32BufferAttribute(ei, 1));

    const uniforms = { uCount: { value: 0 }, uRecent: { value: 40 }, uColor: { value: new THREE.Color("#36CFC0") } };
    const vert = `attribute float aIdx; attribute float aShade; varying float vIdx; varying float vShade;
        void main(){ vIdx=aIdx; vShade=aShade; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }`;
    const matF = new THREE.ShaderMaterial({
        uniforms, vertexShader: vert, transparent: true, depthWrite: false,
        blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
        fragmentShader: `uniform float uCount; uniform float uRecent; uniform vec3 uColor; varying float vIdx; varying float vShade;
            void main(){ if(vIdx>=uCount) discard; float r=step(uCount-uRecent,vIdx);
              gl_FragColor=vec4(mix(uColor*vShade*.09, vec3(.55,1.,.95)*.22, r),1.0); }`,
    });
    const matE = new THREE.ShaderMaterial({
        uniforms,
        vertexShader: `attribute float aIdx; varying float vIdx; void main(){ vIdx=aIdx; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }`,
        transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
        fragmentShader: `uniform float uCount; uniform float uRecent; uniform vec3 uColor; varying float vIdx;
            void main(){ float built=step(vIdx,uCount-.5); float r=built*step(uCount-uRecent,vIdx);
              vec3 c = uColor*mix(.022, .42, built); c = mix(c, vec3(.8,1.,.98)*.9, r);
              gl_FragColor=vec4(c,1.0); }`,
    });
    const model = new THREE.Group();
    model.add(new THREE.Mesh(geoF, matF), new THREE.LineSegments(geoE, matE));
    // The projector grid under the build.
    const grid = new THREE.GridHelper(Math.max(X, Z) + 10, Math.max(X, Z) + 10, 0x36CFC0, 0x36CFC0);
    grid.material.transparent = true;
    grid.material.opacity = 0.08;
    grid.material.blending = THREE.AdditiveBlending;
    grid.material.depthWrite = false;
    grid.position.y = -Y / 2 - 0.02;
    model.add(grid);

    const scene = new THREE.Scene();
    scene.add(model);
    const camera = new THREE.PerspectiveCamera(32, 1, 1, 600);

    const total = blocks.length;
    // Height, not raw block count, drives the progress: a full first layer must not eat a
    // third of the page.
    const layerEnd = [];
    let acc = 0;
    data.couches.forEach((c) => { acc += c.length >> 1; layerEnd.push(acc); });
    const countAt = (p) => {
        const f = p * layerEnd.length, L = Math.floor(f);
        if (L >= layerEnd.length) {
            return total;
        }
        const a = L ? layerEnd[L - 1] : 0;
        return Math.round(a + (layerEnd[L] - a) * (f - L));
    };
    const cC = lecture && lecture.querySelector(".ac-lecture__c");
    const cJ = lecture && lecture.querySelector(".ac-lecture__jauge i");
    const eBuild = lecture && lecture.querySelector('[data-etat="build"]');
    const eDone = lecture && lecture.querySelector('[data-etat="done"]');
    const nLayers = lecture && lecture.querySelector("[data-holo-n]");
    if (nLayers) {
        nLayers.textContent = data.couches.length;
    }
    function readout(count, p) {
        if (!lecture) {
            return;
        }
        const layer = count > 0 ? layerOf[Math.min(total - 1, count - 1)] + 1 : 1;
        cC.textContent = layer;
        eBuild.hidden = p >= 0.995;
        eDone.hidden = p < 0.995;
        cJ.style.setProperty("--p", p.toFixed(3));
    }

    let W = 0, H = 0, wide = true;
    function resize() {
        if (mode === "fond") {
            W = window.innerWidth;
            H = window.innerHeight;
            wide = W > 1000;
        } else {
            W = holo.clientWidth;
            H = holo.clientHeight;
        }
        if (!W || !H) {
            return;
        }
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
        renderer.setSize(W, H, false);
        camera.aspect = W / H;
        if (mode === "fond" && wide) {
            // The subject sits to the right on wide screens, leaving the left column to the text.
            camera.setViewOffset(W, H, -W * 0.17, 0, W, H);
        } else {
            camera.clearViewOffset();
        }
        camera.updateProjectionMatrix();
    }
    resize();
    if (mode === "fond") {
        window.addEventListener("resize", resize);
    } else {
        new ResizeObserver(resize).observe(holo);
    }

    if (mode === "fond") {
        const START = 0.02;
        let target = START, current = START, spin = 0, last = performance.now(), visible = true;
        const blockers = [...root.querySelectorAll(
            ".ac-series, .ac-builds, .ac-shop__grille, .ac-credit, .ac-ep, .ac-autres, .ac-ep__vide")];
        const progress = () => {
            const max = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
            target = START + (1 - START) * Math.min(1, Math.max(0, window.scrollY / max));
        };
        window.addEventListener("scroll", progress, { passive: true });
        progress();
        const frame = (now) => {
            if (!visible) {
                return;
            }
            const dt = Math.min(0.1, (now - last) / 1000);
            last = now;
            current += (target - current) * (1 - Math.exp(-dt * 4));
            spin += dt * 0.06;
            const count = countAt(current);
            uniforms.uCount.value = count;
            const th = -0.9 + current * 2.4 + spin;
            const dist = ((wide ? 122 : 150) - current * 16) * K, el = 0.55 - current * 0.12;
            camera.position.set(Math.sin(th) * dist * Math.cos(el), Math.sin(el) * dist, Math.cos(th) * dist * Math.cos(el));
            camera.lookAt(0, -2 * K, 0);
            renderer.render(scene, camera);
            // Keep the hologram off the site's own header and footer: clip it to the visible
            // part of the page root.
            const r = root.getBoundingClientRect();
            holo.style.clipPath = `inset(${Math.max(0, r.top).toFixed(0)}px 0 ${Math.max(0, H - r.bottom).toFixed(0)}px 0)`;
            readout(count, current);
            if (lecture) {
                // The readout never sits on top of a card.
                const lr = { top: H - 100, left: W - 300 };
                const covered = blockers.some((el2) => {
                    const b = el2.getBoundingClientRect();
                    return b.bottom > lr.top && b.top < H && b.right > lr.left;
                });
                lecture.classList.toggle("is-on", r.bottom > H - 10 && r.top < H * 0.4 && !covered);
            }
            requestAnimationFrame(frame);
        };
        document.addEventListener("visibilitychange", () => {
            visible = !document.hidden;
            if (visible) {
                last = performance.now();
                requestAnimationFrame(frame);
            }
        });
        holo.classList.add("is-pret");
        requestAnimationFrame(frame);
    } else {
        // Time drives the height, layer by layer, then the finished build holds before the
        // next run. Only runs while the porthole is on screen.
        const BUILD = 16, HOLD = 4;
        let t = 0, spin = 0, last = performance.now(), onScreen = true, running = false;
        const frame = (now) => {
            if (!onScreen || document.hidden) {
                running = false;
                return;
            }
            const dt = Math.min(0.1, (now - last) / 1000);
            last = now;
            t = (t + dt) % (BUILD + HOLD);
            spin += dt * 0.12;
            const p = Math.min(1, t / BUILD);
            const count = countAt(p);
            uniforms.uCount.value = count;
            const th = -0.9 + spin, dist = (W / H > 1.6 ? 96 : 112) * K, el = 0.5;
            camera.position.set(Math.sin(th) * dist * Math.cos(el), Math.sin(el) * dist, Math.cos(th) * dist * Math.cos(el));
            camera.lookAt(0, -9 * K, 0);
            renderer.render(scene, camera);
            readout(count, p);
            requestAnimationFrame(frame);
        };
        const wake = () => {
            if (!running && onScreen && !document.hidden) {
                running = true;
                last = performance.now();
                requestAnimationFrame(frame);
            }
        };
        new IntersectionObserver(([e]) => { onScreen = e.isIntersecting; wake(); }).observe(holo);
        document.addEventListener("visibilitychange", wake);
        holo.classList.add("is-pret");
        wake();
    }
}

start();
