/**
 * Tower3DViewer - WebGL Three.js Visualizer for Telecom Lattice Towers
 */
class Tower3DViewer {
  constructor(canvasContainerId) {
    this.container = document.getElementById(canvasContainerId);
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.controls = null;
    this.towerGroup = null;
    this.windVectorsGroup = null;
    this.appurtenancesGroup = null;
    this.stressMode = true;
    this.showWind = true;
    this.autoRotate = false;
    
    this.init();
  }

  init() {
    const width = this.container.clientWidth || 800;
    const height = this.container.clientHeight || 540;

    // Scene
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x0a0f1d);
    this.scene.fog = new THREE.FogExp2(0x0a0f1d, 0.008);

    // Camera
    this.camera = new THREE.PerspectiveCamera(45, width / height, 0.5, 500);
    this.camera.position.set(30, 25, 45);

    // Renderer
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.container.appendChild(this.renderer.domElement);

    // Controls
    if (THREE.OrbitControls) {
      this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
      this.controls.enableDamping = true;
      this.controls.dampingFactor = 0.05;
      this.controls.target.set(0, 18, 0);
    }

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    this.scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight1.position.set(40, 60, 40);
    this.scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x38bdf8, 0.4);
    dirLight2.position.set(-40, 20, -40);
    this.scene.add(dirLight2);

    // Ground Grid & Foundation Pad
    const gridHelper = new THREE.GridHelper(80, 40, 0x0284c7, 0x1e293b);
    gridHelper.position.y = -0.05;
    this.scene.add(gridHelper);

    // Groups
    this.towerGroup = new THREE.Group();
    this.windVectorsGroup = new THREE.Group();
    this.appurtenancesGroup = new THREE.Group();
    this.scene.add(this.towerGroup);
    this.scene.add(this.windVectorsGroup);
    this.scene.add(this.appurtenancesGroup);

    // Window Resize Handler
    window.addEventListener('resize', () => this.onWindowResize());

    // Animation Loop
    this.animate();
  }

  onWindowResize() {
    if (!this.container || !this.renderer || !this.camera) return;
    const width = this.container.clientWidth;
    const height = this.container.clientHeight;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  }

  animate() {
    requestAnimationFrame(() => this.animate());
    if (this.controls) {
      if (this.autoRotate) {
        this.towerGroup.rotation.y += 0.003;
        this.windVectorsGroup.rotation.y += 0.003;
        this.appurtenancesGroup.rotation.y += 0.003;
      }
      this.controls.update();
    }
    this.renderer.render(this.scene, this.camera);
  }

  resetCamera(towerHeight = 40) {
    if (this.controls) {
      this.controls.reset();
      this.controls.target.set(0, towerHeight * 0.45, 0);
    }
    const dist = towerHeight * 1.2;
    this.camera.position.set(dist * 0.7, towerHeight * 0.5, dist * 0.9);
    this.camera.lookAt(0, towerHeight * 0.45, 0);
  }

  toggleAutoRotate() {
    this.autoRotate = !this.autoRotate;
    return this.autoRotate;
  }

  toggleWind() {
    this.showWind = !this.showWind;
    this.windVectorsGroup.visible = this.showWind;
    return this.showWind;
  }

  toggleStressMode() {
    this.stressMode = !this.stressMode;
    return this.stressMode;
  }

  getStressColor(utilization) {
    if (!this.stressMode) return 0x38bdf8;
    if (utilization >= 1.0) return 0xef4444; // FAIL / Overloaded
    if (utilization >= 0.85) return 0xf59e0b; // WARNING
    if (utilization >= 0.70) return 0xeab308; // MODERATE
    return 0x10b981; // SAFE
  }

  renderTower(analysisData, towerInput) {
    // Clear previous elements
    while (this.towerGroup.children.length > 0) {
      this.towerGroup.remove(this.towerGroup.children[0]);
    }
    while (this.windVectorsGroup.children.length > 0) {
      this.windVectorsGroup.remove(this.windVectorsGroup.children[0]);
    }
    while (this.appurtenancesGroup.children.length > 0) {
      this.appurtenancesGroup.remove(this.appurtenancesGroup.children[0]);
    }

    if (!analysisData || !analysisData.nodes) return;

    const nodeMap = {};
    analysisData.nodes.forEach(n => {
      // In Three.js: X is horizontal, Y is UP (elevation Z in engineering), Z is depth (Y in engineering)
      nodeMap[n.id] = new THREE.Vector3(n.x, n.z, n.y);
    });

    // 1. Render Foundation Concrete Pad
    const bHalf = (towerInput.base_width_m || 4.5) / 2.0 + 0.6;
    const padGeo = new THREE.BoxGeometry(bHalf * 2, 0.4, bHalf * 2);
    const padMat = new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.8 });
    const padMesh = new THREE.Mesh(padGeo, padMat);
    padMesh.position.y = -0.2;
    this.towerGroup.add(padMesh);

    // 2. Render Structural Members
    analysisData.members.forEach(m => {
      const pStart = nodeMap[m.start_node];
      const pEnd = nodeMap[m.end_node];
      if (!pStart || !pEnd) return;

      const colorHex = this.getStressColor(m.utilization);
      const isLeg = m.type === "leg";
      const radius = isLeg ? 0.09 : 0.045;

      const dir = new THREE.Vector3().subVectors(pEnd, pStart);
      const length = dir.length();
      const halfPos = new THREE.Vector3().addVectors(pStart, pEnd).multiplyScalar(0.5);

      const cylinderGeo = new THREE.CylinderGeometry(radius, radius, length, 8);
      const cylinderMat = new THREE.MeshStandardMaterial({
        color: colorHex,
        roughness: 0.4,
        metalness: 0.6
      });

      const memberMesh = new THREE.Mesh(cylinderGeo, cylinderMat);
      memberMesh.position.copy(halfPos);

      // Orientation quaternion
      const up = new THREE.Vector3(0, 1, 0);
      const normDir = dir.clone().normalize();
      const quat = new THREE.Quaternion().setFromUnitVectors(up, normDir);
      memberMesh.quaternion.copy(quat);

      this.towerGroup.add(memberMesh);
    });

    // 3. Render Equipment & Antennas
    if (towerInput.equipment_items) {
      towerInput.equipment_items.forEach(eq => {
        const elev = eq.elevation_m;
        const isDish = eq.name.toLowerCase().includes("dish") || eq.name.toLowerCase().includes("microwave");

        if (isDish) {
          // Parabolic Dish Representation
          const dishGeo = new THREE.SphereGeometry(0.7, 16, 8, 0, Math.PI * 2, 0, Math.PI * 0.4);
          const dishMat = new THREE.MeshStandardMaterial({ color: 0xe2e8f0, roughness: 0.3 });
          const dishMesh = new THREE.Mesh(dishGeo, dishMat);
          dishMesh.rotation.x = Math.PI / 2;
          dishMesh.position.set(1.5, elev, 0);
          this.appurtenancesGroup.add(dishMesh);
        } else {
          // Sector Antennas (3 sectors spaced 120 degrees)
          for (let s = 0; s < 3; s++) {
            const angle = (s * 2 * Math.PI) / 3;
            const radiusOffset = 1.0;
            const antGeo = new THREE.BoxGeometry(0.2, 1.4, 0.3);
            const antMat = new THREE.MeshStandardMaterial({ color: 0x38bdf8, roughness: 0.5 });
            const antMesh = new THREE.Mesh(antGeo, antMat);
            antMesh.position.set(radiusOffset * Math.cos(angle), elev, radiusOffset * Math.sin(angle));
            antMesh.rotation.y = angle;
            this.appurtenancesGroup.add(antMesh);
          }
        }
      });
    }

    // 4. Render Wind Vector Arrows
    if (analysisData.panel_profiles) {
      const maxWindForce = Math.max(...analysisData.panel_profiles.map(p => p.total_wind_force_kn));
      analysisData.panel_profiles.forEach(p => {
        const elev = p.elevation_mid_m;
        const force = p.total_wind_force_kn;
        const arrowLength = Math.max(1.5, (force / Math.max(1, maxWindForce)) * 5.0);

        const fromPos = new THREE.Vector3(-arrowLength - p.face_width_m * 0.7, elev, 0);
        const toDir = new THREE.Vector3(1, 0, 0);

        const arrowHelper = new THREE.ArrowHelper(
          toDir,
          fromPos,
          arrowLength,
          0x06b6d4,
          0.8,
          0.4
        );
        this.windVectorsGroup.add(arrowHelper);
      });
    }

    // 5. Adjust Camera target to tower center
    if (this.controls) {
      this.controls.target.set(0, towerInput.height_m * 0.45, 0);
    }
  }
}
