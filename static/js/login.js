/**
 * CineMatch AI - 3D Character Walking Animation Controller
 * Reproduces reference visual animation:
 * - 3D cartoon boy with red cap, glasses, dark hoodie, dark trousers, sneakers
 * - Walks naturally from left to right
 * - Stops beside the electric-blue glowing login card
 * - Natural idle movements upon arrival
 */

document.addEventListener('DOMContentLoaded', () => {
    initThreeScene();
    initLoginForm();
});

// ==========================================
// 1. THREE.JS 3D SCENE & ARTICULATED CHARACTER
// ==========================================
let scene, camera, renderer;
let characterGroup, headGroup, capGroup, eyesGroup;
let leftArmGroup, rightArmGroup, leftLegGroup, rightLegGroup, torsoGroup;
let leftLowerLeg, rightLowerLeg, leftForearm, rightForearm;
let particlesMesh, groundSpotlight;

let walkCycleTime = 0;
let idleTime = 0;
let walkBlend = 1.0; // 1.0 = walking, 0.0 = full idle
let isWalking = true;
let walkSpeed = 2.4; // smooth, realistic walking velocity
let startX = -10.5;  // offscreen left
let targetX = -1.1;  // directly beside login card, leaving center title unobstructed
let currentX = startX;

function initThreeScene() {
    const canvas = document.getElementById('threeCanvas');
    if (!canvas) return;

    // 1. Scene setup with transparent background so cinematic artwork shows through
    scene = new THREE.Scene();

    // 2. Camera setup
    camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 100);
    camera.position.set(0, 1.1, 10.2);

    // 3. Renderer with transparent background and antialiasing
    renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true });
    renderer.setClearColor(0x000000, 0); // 100% transparent canvas
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    // 4. Cinematic Lighting
    const ambientLight = new THREE.AmbientLight(0x1e293b, 1.2);
    scene.add(ambientLight);

    // Key Light
    const keyLight = new THREE.DirectionalLight(0xfff7ed, 1.5);
    keyLight.position.set(3, 7, 6);
    keyLight.castShadow = true;
    scene.add(keyLight);

    // Electric-Blue Rim / Accent Light (Left side)
    const rimLight = new THREE.PointLight(0x00f0ff, 4.5, 20);
    rimLight.position.set(-8, 3, 3);
    scene.add(rimLight);

    // Electric-Blue Fill Light (Right side)
    const fillLight = new THREE.PointLight(0x0070f3, 2.5, 15);
    fillLight.position.set(5, 1, 2);
    scene.add(fillLight);

    // Ground Spotlight directly where character stops
    groundSpotlight = new THREE.SpotLight(0x00f0ff, 2.2, 12, Math.PI / 4, 0.5, 1);
    groundSpotlight.position.set(targetX, 6, 0);
    groundSpotlight.target.position.set(targetX, -1.8, 0);
    scene.add(groundSpotlight);
    scene.add(groundSpotlight.target);

    // 5. Construct 3D Cartoon Boy
    createCartoonBoy();

    // 6. Subtle Electric-Blue Ambient Particles
    createCinematicParticles();

    // Resize handling
    window.addEventListener('resize', onWindowResize);

    // Mouse movement interaction for dynamic head tracking
    window.addEventListener('mousemove', onMouseMove);

    // Interactive replay: clicking anywhere outside the login form replays the walk animation
    window.addEventListener('click', (e) => {
        if (!e.target.closest('#loginFormWrapper') && !isWalking && walkBlend <= 0.05) {
            currentX = startX;
            isWalking = true;
            walkBlend = 1.0;
            idleTime = 0;
            if (characterGroup) {
                characterGroup.position.x = startX;
                characterGroup.rotation.y = Math.PI / 2;
            }
        }
    });

    // Animation Loop
    animate();
}

/**
 * 3D Cartoon Boy Character Construction
 * Appearance: Red cap, Glasses, Dark hoodie, Dark trousers, Sneakers.
 */
function createCartoonBoy() {
    characterGroup = new THREE.Group();
    characterGroup.position.set(startX, -1.8, 0);
    characterGroup.rotation.y = Math.PI / 2; // Facing right while walking
    characterGroup.scale.set(1.2, 1.2, 1.2);

    // Materials
    const skinMaterial = new THREE.MeshStandardMaterial({
        color: 0xffd1b3,
        roughness: 0.5,
        metalness: 0.05
    });

    const hoodieMaterial = new THREE.MeshStandardMaterial({
        color: 0x111827, // Dark Charcoal/Black hoodie
        roughness: 0.8,
        metalness: 0.1
    });

    const capMaterial = new THREE.MeshStandardMaterial({
        color: 0xd90429, // Red Cap
        roughness: 0.6,
        metalness: 0.05
    });

    const trousersMaterial = new THREE.MeshStandardMaterial({
        color: 0x1e293b, // Dark navy/slate trousers
        roughness: 0.85
    });

    const shoeWhiteMat = new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.4 });
    const shoeRedMat = new THREE.MeshStandardMaterial({ color: 0xef233c, roughness: 0.5 });
    const glassesFrameMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.2, metalness: 0.8 });

    // ----------------------------------------
    // TORSO (Dark Hoodie)
    // ----------------------------------------
    torsoGroup = new THREE.Group();
    torsoGroup.position.y = 1.35;

    // Main torso
    const torsoGeo = new THREE.CylinderGeometry(0.38, 0.34, 0.8, 16);
    const torsoMesh = new THREE.Mesh(torsoGeo, hoodieMaterial);
    torsoMesh.castShadow = true;
    torsoGroup.add(torsoMesh);

    // Front Kangaroo Pocket
    const pocketGeo = new THREE.BoxGeometry(0.36, 0.22, 0.18);
    const pocketMesh = new THREE.Mesh(pocketGeo, hoodieMaterial);
    pocketMesh.position.set(0, -0.15, 0.26);
    pocketMesh.rotation.x = 0.1;
    torsoGroup.add(pocketMesh);

    // Hoodie Neck Collar
    const collarGeo = new THREE.TorusGeometry(0.24, 0.09, 12, 24);
    const collarMesh = new THREE.Mesh(collarGeo, hoodieMaterial);
    collarMesh.position.set(0, 0.42, 0);
    collarMesh.rotation.x = Math.PI / 2;
    torsoGroup.add(collarMesh);

    // Drawstrings
    const stringGeo = new THREE.CylinderGeometry(0.012, 0.012, 0.25, 8);
    const leftString = new THREE.Mesh(stringGeo, shoeWhiteMat);
    leftString.position.set(-0.08, 0.25, 0.32);
    const rightString = new THREE.Mesh(stringGeo, shoeWhiteMat);
    rightString.position.set(0.08, 0.25, 0.32);
    torsoGroup.add(leftString);
    torsoGroup.add(rightString);

    // ----------------------------------------
    // HEAD & FACE
    // ----------------------------------------
    headGroup = new THREE.Group();
    headGroup.position.set(0, 0.72, 0);

    // Head base
    const headGeo = new THREE.SphereGeometry(0.36, 24, 24);
    headGeo.scale(1, 1.05, 1);
    const headMesh = new THREE.Mesh(headGeo, skinMaterial);
    headMesh.castShadow = true;
    headGroup.add(headMesh);

    // Ears
    const earGeo = new THREE.SphereGeometry(0.08, 12, 12);
    earGeo.scale(0.5, 1, 0.8);
    const leftEar = new THREE.Mesh(earGeo, skinMaterial);
    leftEar.position.set(-0.36, 0.02, 0);
    const rightEar = new THREE.Mesh(earGeo, skinMaterial);
    rightEar.position.set(0.36, 0.02, 0);
    headGroup.add(leftEar);
    headGroup.add(rightEar);

    // Hair peeking under the cap
    const hairMat = new THREE.MeshStandardMaterial({ color: 0x271e16, roughness: 0.9 });
    const hairFringeGeo = new THREE.BoxGeometry(0.32, 0.09, 0.12);
    const hairFringe = new THREE.Mesh(hairFringeGeo, hairMat);
    hairFringe.position.set(0, 0.2, 0.32);
    hairFringe.rotation.x = 0.2;
    headGroup.add(hairFringe);

    // Eyes
    eyesGroup = new THREE.Group();
    eyesGroup.position.set(0, 0.04, 0.32);

    const eyeWhiteGeo = new THREE.SphereGeometry(0.065, 16, 16);
    eyeWhiteGeo.scale(1, 1.15, 0.5);
    const eyeWhiteMat = new THREE.MeshBasicMaterial({ color: 0xffffff });

    const pupilGeo = new THREE.SphereGeometry(0.038, 12, 12);
    pupilGeo.scale(1, 1, 0.4);
    const pupilMat = new THREE.MeshBasicMaterial({ color: 0x0f172a });

    const leftEyeWhite = new THREE.Mesh(eyeWhiteGeo, eyeWhiteMat);
    leftEyeWhite.position.x = -0.12;
    const leftPupil = new THREE.Mesh(pupilGeo, pupilMat);
    leftPupil.position.set(-0.12, 0, 0.035);
    eyesGroup.add(leftEyeWhite);
    eyesGroup.add(leftPupil);

    const rightEyeWhite = new THREE.Mesh(eyeWhiteGeo, eyeWhiteMat);
    rightEyeWhite.position.x = 0.12;
    const rightPupil = new THREE.Mesh(pupilGeo, pupilMat);
    rightPupil.position.set(0.12, 0, 0.035);
    eyesGroup.add(rightEyeWhite);
    eyesGroup.add(rightPupil);

    headGroup.add(eyesGroup);

    // GLASSES
    const glassesGroup = new THREE.Group();
    glassesGroup.position.set(0, 0.04, 0.34);

    const frameGeo = new THREE.TorusGeometry(0.09, 0.016, 12, 24);
    const leftFrame = new THREE.Mesh(frameGeo, glassesFrameMat);
    leftFrame.position.x = -0.125;
    const rightFrame = new THREE.Mesh(frameGeo, glassesFrameMat);
    rightFrame.position.x = 0.125;

    const bridgeGeo = new THREE.BoxGeometry(0.08, 0.016, 0.016);
    const bridge = new THREE.Mesh(bridgeGeo, glassesFrameMat);
    bridge.position.y = 0.01;

    glassesGroup.add(leftFrame);
    glassesGroup.add(rightFrame);
    glassesGroup.add(bridge);
    headGroup.add(glassesGroup);

    // RED CAP
    capGroup = new THREE.Group();
    capGroup.position.set(0, 0.22, 0);

    const capDomeGeo = new THREE.SphereGeometry(0.385, 24, 16, 0, Math.PI * 2, 0, Math.PI * 0.52);
    const capDome = new THREE.Mesh(capDomeGeo, capMaterial);
    capDome.castShadow = true;
    capGroup.add(capDome);

    const visorGeo = new THREE.CylinderGeometry(0.42, 0.44, 0.035, 24, 1, false, -Math.PI * 0.28, Math.PI * 0.56);
    const visor = new THREE.Mesh(visorGeo, capMaterial);
    visor.position.set(0, 0.02, 0.26);
    visor.rotation.x = 0.15;
    visor.castShadow = true;
    capGroup.add(visor);

    const buttonGeo = new THREE.SphereGeometry(0.035, 12, 12);
    const buttonMesh = new THREE.Mesh(buttonGeo, shoeWhiteMat);
    buttonMesh.position.y = 0.38;
    capGroup.add(buttonMesh);

    capGroup.rotation.x = -0.12;
    headGroup.add(capGroup);

    torsoGroup.add(headGroup);

    // ----------------------------------------
    // ARMS
    // ----------------------------------------
    leftArmGroup = new THREE.Group();
    leftArmGroup.position.set(-0.44, 0.25, 0);

    const upperArmGeo = new THREE.CylinderGeometry(0.09, 0.08, 0.35, 12);
    const leftUpperArm = new THREE.Mesh(upperArmGeo, hoodieMaterial);
    leftUpperArm.position.y = -0.175;
    leftArmGroup.add(leftUpperArm);

    leftForearm = new THREE.Group();
    leftForearm.position.y = -0.35;
    const forearmGeo = new THREE.CylinderGeometry(0.08, 0.075, 0.32, 12);
    const leftForearmMesh = new THREE.Mesh(forearmGeo, hoodieMaterial);
    leftForearmMesh.position.y = -0.16;
    leftForearm.add(leftForearmMesh);

    const handGeo = new THREE.SphereGeometry(0.075, 12, 12);
    const leftHand = new THREE.Mesh(handGeo, skinMaterial);
    leftHand.position.y = -0.34;
    leftForearm.add(leftHand);

    leftArmGroup.add(leftForearm);
    torsoGroup.add(leftArmGroup);

    rightArmGroup = new THREE.Group();
    rightArmGroup.position.set(0.44, 0.25, 0);

    const rightUpperArm = new THREE.Mesh(upperArmGeo, hoodieMaterial);
    rightUpperArm.position.y = -0.175;
    rightArmGroup.add(rightUpperArm);

    rightForearm = new THREE.Group();
    rightForearm.position.y = -0.35;
    const rightForearmMesh = new THREE.Mesh(forearmGeo, hoodieMaterial);
    rightForearmMesh.position.y = -0.16;
    rightForearm.add(rightForearmMesh);

    const rightHand = new THREE.Mesh(handGeo, skinMaterial);
    rightHand.position.y = -0.34;
    rightForearm.add(rightHand);

    rightArmGroup.add(rightForearm);
    torsoGroup.add(rightArmGroup);

    characterGroup.add(torsoGroup);

    // ----------------------------------------
    // LEGS & SNEAKERS
    // ----------------------------------------
    leftLegGroup = new THREE.Group();
    leftLegGroup.position.set(-0.18, 0.95, 0);

    const thighGeo = new THREE.CylinderGeometry(0.12, 0.105, 0.42, 12);
    const leftThigh = new THREE.Mesh(thighGeo, trousersMaterial);
    leftThigh.position.y = -0.21;
    leftThigh.castShadow = true;
    leftLegGroup.add(leftThigh);

    leftLowerLeg = new THREE.Group();
    leftLowerLeg.position.y = -0.42;

    const calfGeo = new THREE.CylinderGeometry(0.105, 0.09, 0.4, 12);
    const leftCalf = new THREE.Mesh(calfGeo, trousersMaterial);
    leftCalf.position.y = -0.2;
    leftLowerLeg.add(leftCalf);

    const leftSneaker = createSneaker(shoeWhiteMat, shoeRedMat);
    leftSneaker.position.set(0, -0.42, 0.06);
    leftLowerLeg.add(leftSneaker);

    leftLegGroup.add(leftLowerLeg);
    characterGroup.add(leftLegGroup);

    rightLegGroup = new THREE.Group();
    rightLegGroup.position.set(0.18, 0.95, 0);

    const rightThigh = new THREE.Mesh(thighGeo, trousersMaterial);
    rightThigh.position.y = -0.21;
    rightThigh.castShadow = true;
    rightLegGroup.add(rightThigh);

    rightLowerLeg = new THREE.Group();
    rightLowerLeg.position.y = -0.42;

    const rightCalf = new THREE.Mesh(calfGeo, trousersMaterial);
    rightCalf.position.y = -0.2;
    rightLowerLeg.add(rightCalf);

    const rightSneaker = createSneaker(shoeWhiteMat, shoeRedMat);
    rightSneaker.position.set(0, -0.42, 0.06);
    rightLowerLeg.add(rightSneaker);

    rightLegGroup.add(rightLowerLeg);
    characterGroup.add(rightLegGroup);

    scene.add(characterGroup);
}

function createSneaker(whiteMat, redMat) {
    const sneakerGroup = new THREE.Group();

    const soleGeo = new THREE.BoxGeometry(0.18, 0.06, 0.36);
    const sole = new THREE.Mesh(soleGeo, whiteMat);
    sneakerGroup.add(sole);

    const bodyGeo = new THREE.BoxGeometry(0.17, 0.14, 0.32);
    const body = new THREE.Mesh(bodyGeo, redMat);
    body.position.set(0, 0.08, -0.01);
    sneakerGroup.add(body);

    const toeGeo = new THREE.SphereGeometry(0.085, 12, 12);
    toeGeo.scale(1, 0.7, 1);
    const toe = new THREE.Mesh(toeGeo, whiteMat);
    toe.position.set(0, 0.05, 0.14);
    sneakerGroup.add(toe);

    return sneakerGroup;
}

function createCinematicParticles() {
    const particleCount = 100;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);

    for (let i = 0; i < particleCount * 3; i += 3) {
        positions[i] = (Math.random() - 0.5) * 22;
        positions[i + 1] = (Math.random() - 0.5) * 14;
        positions[i + 2] = (Math.random() - 0.5) * 10;
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    const material = new THREE.PointsMaterial({
        color: 0x00f0ff,
        size: 0.05,
        transparent: true,
        opacity: 0.45,
        blending: THREE.AdditiveBlending
    });

    particlesMesh = new THREE.Points(geometry, material);
    scene.add(particlesMesh);
}

// ==========================================
// ==========================================
// 2. CONTINUOUS WALKING ANIMATION LOOP
// ==========================================
let clock = new THREE.Clock();
let mouseX = 0, mouseY = 0;

function animate() {
    requestAnimationFrame(animate);

    const delta = Math.min(clock.getDelta(), 0.08); // smooth delta
    const elapsed = clock.getElapsedTime();

    if (particlesMesh) {
        particlesMesh.rotation.y = elapsed * 0.012;
    }

    if (characterGroup) {
        // Phase 1: Walking across from left to right
        if (isWalking) {
            currentX += walkSpeed * delta;
            walkCycleTime += delta * 6.0;

            if (currentX >= targetX) {
                currentX = targetX;
                isWalking = false; // reached destination beside login card
            }
            characterGroup.position.x = currentX;

            // Character faces rightwards while walking
            const walkProgress = Math.min(1, Math.max(0, (currentX - startX) / (targetX - startX)));
            characterGroup.rotation.y = (Math.PI / 2) * (1 - walkProgress * 0.32);
        } else {
            // Phase 2: Stopping & smoothly transitioning into Idle animation
            characterGroup.position.x = targetX;

            // Gradually decrease walk blend to zero (smooth decel over ~0.7 seconds)
            if (walkBlend > 0) {
                walkBlend = Math.max(0, walkBlend - delta * 1.8);
                walkCycleTime += delta * 6.0 * walkBlend;
            } else {
                idleTime += delta;
            }

            // Smoothly rotate character to 3/4 cinematic angle facing the login card
            const targetRotY = Math.PI * 0.32;
            characterGroup.rotation.y += (targetRotY - characterGroup.rotation.y) * Math.min(1, delta * 3.0);
        }

        // Active biomechanical calculations
        const stride = Math.sin(walkCycleTime) * walkBlend;
        const bounce = Math.abs(Math.sin(walkCycleTime)) * 0.09 * walkBlend;
        const breath = Math.sin(idleTime * 2.2) * 0.025 * (1 - walkBlend);

        // 1. Legs Kinetics (Thighs & Bending Knees)
        leftLegGroup.rotation.x = stride * 0.62;
        rightLegGroup.rotation.x = -stride * 0.62;

        // Knees bend backward when foot lifts off ground during walking
        leftLowerLeg.rotation.x = stride < 0 ? (-stride * 0.72) : 0.04;
        rightLowerLeg.rotation.x = stride > 0 ? (stride * 0.72) : 0.04;

        // 2. Arms Dynamics (Opposing swing during walk, relaxed breathing in idle)
        leftArmGroup.rotation.x = -stride * 0.52;
        rightArmGroup.rotation.x = stride * 0.52;

        leftForearm.rotation.x = -Math.max(0, -stride * 0.36);
        rightForearm.rotation.x = -Math.max(0, stride * 0.36);

        // Lateral arm angle + gentle breathing sway in idle
        leftArmGroup.rotation.z = 0.12 + (Math.sin(idleTime * 2.2) * 0.015 * (1 - walkBlend));
        rightArmGroup.rotation.z = -0.12 - (Math.sin(idleTime * 2.2) * 0.015 * (1 - walkBlend));

        // 3. Torso Height & Sway (Step bounce during walk, chest breathing in idle)
        torsoGroup.position.y = 1.35 + bounce + breath;
        torsoGroup.rotation.z = Math.sin(walkCycleTime) * 0.035 * walkBlend;
        torsoGroup.rotation.x = Math.sin(idleTime * 2.2) * 0.012 * (1 - walkBlend);

        // 4. Head and Cap Motion
        if (headGroup) {
            // Nodding during walk + interactive cursor tracking + subtle idle look
            const targetHeadX = (mouseY * 0.18) + (Math.sin(walkCycleTime * 2) * 0.02 * walkBlend);
            const targetHeadY = (mouseX * 0.28) + (Math.sin(walkCycleTime) * 0.025 * walkBlend) + 0.05;
            headGroup.rotation.x += (targetHeadX - headGroup.rotation.x) * 0.1;
            headGroup.rotation.y += (targetHeadY - headGroup.rotation.y) * 0.1;
            headGroup.position.y = 0.72 + (Math.sin(walkCycleTime * 2) * 0.01 * walkBlend);
        }

        // 5. Natural Eye Blinking
        if (eyesGroup) {
            const blinkTimer = Math.sin(elapsed * 2.6);
            if (blinkTimer > 0.96) {
                eyesGroup.scale.y = 0.1;
            } else {
                eyesGroup.scale.y = 1.0;
            }
        }
    }

    renderer.render(scene, camera);
}

function onMouseMove(e) {
    mouseX = (e.clientX / window.innerWidth) * 2 - 1;
    mouseY = -(e.clientY / window.innerHeight) * 2 + 1;
}

function onWindowResize() {
    if (!camera || !renderer) return;
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);

    if (window.innerWidth < 992) {
        targetX = -100; // hide on mobile to prevent overlapping login form
    } else {
        targetX = -1.1; // directly beside login card
    }
}

// ==========================================
// 3. LOGIN FORM PASSWORD TOGGLE
// ==========================================
function initLoginForm() {
    const toggleBtn = document.getElementById('togglePasswordBtn');
    const pwdInput = document.getElementById('password');
    const toggleIcon = document.getElementById('togglePasswordIcon');

    if (toggleBtn && pwdInput) {
        toggleBtn.addEventListener('click', () => {
            if (pwdInput.type === 'password') {
                pwdInput.type = 'text';
                toggleIcon.classList.replace('fa-eye', 'fa-eye-slash');
            } else {
                pwdInput.type = 'password';
                toggleIcon.classList.replace('fa-eye-slash', 'fa-eye');
            }
        });
    }
}
