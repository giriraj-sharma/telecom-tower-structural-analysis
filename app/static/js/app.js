const fieldGroups = [
  { title: "Geometry", fields: ["tower_type", "height_m", "base_width_m", "top_width_m", "panel_height_m", "bracing_type"] },
  { title: "Steel members", fields: ["leg_section_type", "leg_dimension_mm", "leg_thickness_mm", "brace_section_type", "brace_dimension_mm", "brace_thickness_mm"] },
  { title: "Material", fields: ["steel_yield_strength_mpa", "steel_elastic_modulus_gpa", "steel_density_kg_m3"] },
  { title: "Wind loading", fields: ["wind_speed_kmh", "terrain_category", "gust_factor"] }
];

const fieldLabels = {
  tower_type: ["Tower type", ""], height_m: ["Tower height", "m"], base_width_m: ["Base width", "m"],
  top_width_m: ["Top width", "m"], panel_height_m: ["Panel height", "m"], bracing_type: ["Bracing pattern", ""],
  leg_section_type: ["Leg profile", ""], leg_dimension_mm: ["Leg size", "mm"], leg_thickness_mm: ["Leg thickness", "mm"],
  brace_section_type: ["Brace profile", ""], brace_dimension_mm: ["Brace size", "mm"], brace_thickness_mm: ["Brace thickness", "mm"],
  steel_yield_strength_mpa: ["Yield strength", "MPa"], steel_elastic_modulus_gpa: ["Elastic modulus", "GPa"],
  steel_density_kg_m3: ["Steel density", "kg/m3"], wind_speed_kmh: ["Basic wind speed", "km/h"],
  terrain_category: ["Terrain exposure", ""], gust_factor: ["Gust factor", ""]
};

const enumOptions = {
  tower_type: ["3-leg", "4-leg"], bracing_type: ["X-brace", "Warren", "K-brace"],
  leg_section_type: ["CHS", "Angle"], brace_section_type: ["Angle", "CHS"],
  terrain_category: ["Exposure B - Urban", "Exposure C - Open", "Exposure D - Coastal"]
};

const numericLimits = {
  height_m: [10, 120, 0.5], base_width_m: [1, 25, 0.1], top_width_m: [0.5, 10, 0.1], panel_height_m: [1, 6, 0.1],
  leg_dimension_mm: [30, 500, 0.1], leg_thickness_mm: [3, 50, 0.1], brace_dimension_mm: [20, 250, 0.1],
  brace_thickness_mm: [2, 30, 0.1], steel_yield_strength_mpa: [200, 700, 1], steel_elastic_modulus_gpa: [150, 220, 1],
  steel_density_kg_m3: [7000, 8500, 10], wind_speed_kmh: [50, 300, 1], gust_factor: [1, 1.6, 0.01]
};

const byId = (id) => document.getElementById(id);
const format = (value, digits = 2) => Number(value).toLocaleString(undefined, { maximumFractionDigits: digits });
let towerInput = null;
let analysisResult = null;
let optimizationResult = null;
let viewer = null;
let windChart = null;
let deflectionChart = null;
let toastTimer = null;

function renderFields(values) {
  const container = byId("field-groups");
  container.replaceChildren();
  fieldGroups.forEach((group) => {
    const section = document.createElement("section");
    section.className = "input-section";
    const heading = document.createElement("h2");
    heading.className = "panel-section-title";
    heading.textContent = group.title;
    const grid = document.createElement("div");
    grid.className = "form-grid";
    group.fields.forEach((key) => {
      const wrapper = document.createElement("div");
      wrapper.className = "form-group" + (key === "terrain_category" ? " full-width" : "");
      const label = document.createElement("label");
      label.htmlFor = `field-${key}`;
      label.textContent = `${fieldLabels[key][0]}${fieldLabels[key][1] ? ` (${fieldLabels[key][1]})` : ""}`;
      let input;
      if (enumOptions[key]) {
        input = document.createElement("select");
        enumOptions[key].forEach((option) => {
          const item = document.createElement("option");
          item.value = option;
          item.textContent = option;
          input.append(item);
        });
      } else {
        input = document.createElement("input");
        input.type = "number";
        [input.min, input.max, input.step] = numericLimits[key];
      }
      input.id = `field-${key}`;
      input.name = key;
      input.value = values[key];
      input.required = true;
      wrapper.append(label, input);
      grid.append(wrapper);
    });
    section.append(heading, grid);
    container.append(section);
  });
  setEquipment(values.equipment_items || []);
}

function setEquipment(items) {
  byId("equipment-json").value = JSON.stringify(items, null, 2);
  byId("equipment-count").textContent = `${items.length} items`;
}

function readForm() {
  const values = {};
  new FormData(byId("tower-form")).forEach((value, key) => {
    if (key !== "") values[key] = enumOptions[key] ? value : Number(value);
  });
  try {
    values.equipment_items = JSON.parse(byId("equipment-json").value);
  } catch {
    throw new Error("Equipment schedule must be valid JSON.");
  }
  if (!Array.isArray(values.equipment_items)) throw new Error("Equipment schedule must be a JSON array.");
  towerInput = values;
  return values;
}

async function request(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch { /* Keep the HTTP status when the response is not JSON. */ }
    throw new Error(message);
  }
  return response;
}

function showBusy(message) {
  byId("loading-message").textContent = message;
  byId("loading-overlay").style.display = "flex";
}

function hideBusy() {
  byId("loading-overlay").style.display = "none";
}

function notify(message, error = false) {
  const toast = byId("toast");
  toast.textContent = message;
  toast.classList.toggle("error", error);
  toast.classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("visible"), 3600);
}

async function loadPreset(key, run = true) {
  showBusy("Loading tower configuration...");
  try {
    const response = await request(`/api/presets/${encodeURIComponent(key)}`);
    const values = await response.json();
    renderFields(values);
    towerInput = values;
    document.querySelectorAll("[data-preset]").forEach((button) => button.classList.toggle("active", button.dataset.preset === key));
    byId("result-heading").textContent = `${format(values.height_m, 0)} m ${values.tower_type} lattice tower`;
    byId("input-state").textContent = "Preset loaded";
    byId("input-state").classList.add("connected");
    if (run) await analyze();
  } catch (error) {
    notify(error.message, true);
    byId("input-state").textContent = "API unavailable";
  } finally {
    hideBusy();
  }
}

function renderKpis(data) {
  const status = data.overall_status.toLowerCase();
  const items = [
    ["Structural status", data.overall_status, data.governing_load_combination, status],
    ["Peak utilization", `${format(data.max_utilization * 100, 1)}%`, data.critical_member.member_id, status],
    ["Base shear", format(data.base_shear_kn), "kN", ""],
    ["Overturning moment", format(data.overturning_moment_knm), "kN m", ""],
    ["Top deflection", format(data.max_deflection_mm), `${data.deflection_ratio} of height`, ""]
  ];
  byId("kpi-grid").replaceChildren(...items.map(([label, value, sub, tone]) => {
    const card = document.createElement("div");
    card.className = "kpi-card";
    const title = document.createElement("span"); title.className = "kpi-label"; title.textContent = label;
    const number = document.createElement("strong"); number.className = `kpi-value ${tone ? `status-${tone}` : ""}`; number.textContent = value;
    const caption = document.createElement("span"); caption.className = "kpi-sub"; caption.textContent = sub;
    card.append(title, number, caption);
    return card;
  }));
}

function statusBadge(status) {
  const badge = document.createElement("span");
  badge.className = `status-badge status-${String(status).toLowerCase()}`;
  badge.textContent = status;
  return badge;
}

function appendCell(row, value) {
  const cell = document.createElement("td");
  if (value instanceof Node) cell.append(value);
  else cell.textContent = value;
  row.append(cell);
}

function renderTables(data) {
  const members = data.critical_members_table || [];
  byId("member-count").textContent = `${members.length} critical members`;
  const memberRows = members.map((member) => {
    const row = document.createElement("tr");
    [member.member_id, member.member_type, `${format(member.elevation_m)} m`, member.section_description,
      `${format(member.axial_force_kn)} kN`, `${format(member.capacity_kn)} kN`, `${format(member.utilization_ratio * 100, 1)}%`]
      .forEach((value) => appendCell(row, value));
    appendCell(row, statusBadge(member.status));
    return row;
  });
  byId("members-body").replaceChildren(...memberRows);
  const combinationRows = data.load_combinations.map((combination) => {
    const row = document.createElement("tr");
    [combination.name, format(combination.base_shear_kn), format(combination.overturning_moment_knm),
      format(combination.max_deflection_mm), `${format(combination.max_leg_utilization * 100, 1)}%`,
      `${format(combination.max_brace_utilization * 100, 1)}%`].forEach((value) => appendCell(row, value));
    appendCell(row, statusBadge(combination.status));
    return row;
  });
  byId("combinations-body").replaceChildren(...combinationRows);
  const nodes = data.nodes.slice(0, 80).map((node) => {
    const row = document.createElement("tr");
    [node.id, format(node.x, 3), format(node.y, 3), format(node.z, 3)].forEach((value) => appendCell(row, value));
    return row;
  });
  byId("geometry-count").textContent = `${data.nodes.length} nodes · ${data.members.length} members`;
  byId("geometry-body").replaceChildren(...nodes);
}

function renderCalculations(data) {
  const values = [
    ["Basic wind speed", `${format(data.intermediate_calculations.basic_wind_speed_ms)} m/s`],
    ["Tower steel mass", `${format(data.intermediate_calculations.total_tower_steel_mass_kg, 0)} kg`],
    ["Equipment mass", `${format(data.intermediate_calculations.total_equipment_mass_kg, 0)} kg`],
    ["Total dead load", `${format(data.intermediate_calculations.total_dead_load_kn)} kN`],
    ["Wind shear", `${format(data.intermediate_calculations.total_wind_shear_kn)} kN`],
    ["Allowable deflection", `${format(data.intermediate_calculations.allowable_deflection_mm)} mm`],
    ["Base leg compression", `${format(data.intermediate_calculations.base_leg_compression_kn)} kN`],
    ["Base leg uplift", `${format(data.intermediate_calculations.base_leg_uplift_kn)} kN`],
    ["Estimated total cost", `$${format(data.cost_breakdown.total_estimated_cost_usd, 0)}`]
  ];
  const grid = byId("calculation-summary");
  grid.replaceChildren(...values.map(([label, value]) => {
    const item = document.createElement("div"); item.className = "calculation-item";
    const key = document.createElement("span"); key.textContent = label;
    const result = document.createElement("strong"); result.textContent = value;
    item.append(key, result);
    return item;
  }));
}

function renderCharts(data) {
  if (!window.Chart) return;
  const labels = data.panel_profiles.map((panel) => format(panel.elevation_mid_m, 0));
  const common = { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } },
    scales: { x: { title: { display: true, text: "Elevation (m)", color: "#94a3b8" }, ticks: { color: "#94a3b8" }, grid: { color: "#253044" } },
      y: { beginAtZero: true, ticks: { color: "#94a3b8" }, grid: { color: "#253044" } } } };
  windChart?.destroy();
  deflectionChart?.destroy();
  windChart = new Chart(byId("wind-chart"), { type: "bar", data: { labels, datasets: [{ data: data.panel_profiles.map((panel) => panel.total_wind_force_kn), backgroundColor: "rgba(6, 182, 212, 0.65)", borderColor: "#06b6d4", borderWidth: 1 }] }, options: common });
  deflectionChart = new Chart(byId("deflection-chart"), { type: "line", data: { labels, datasets: [{ data: data.panel_profiles.map((panel) => panel.deflection_mm), borderColor: "#f59e0b", backgroundColor: "rgba(245, 158, 11, 0.14)", fill: true, tension: 0.3, pointRadius: 2 }] }, options: common });
}

async function analyze() {
  let values;
  try { values = readForm(); }
  catch (error) { notify(error.message, true); return; }
  showBusy("Calculating structural response...");
  byId("input-state").textContent = "Analyzing";
  try {
    const response = await request("/api/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(values) });
    analysisResult = await response.json();
    optimizationResult = null;
    byId("result-heading").textContent = `${format(analysisResult.height_m, 0)} m ${analysisResult.tower_type} lattice tower`;
    byId("model-label").textContent = `${analysisResult.overall_status} · ${analysisResult.members.length} structural members`;
    byId("run-stamp").textContent = `Updated ${new Date().toLocaleTimeString()}`;
    byId("input-state").textContent = "Analysis current";
    renderKpis(analysisResult);
    renderTables(analysisResult);
    renderCalculations(analysisResult);
    renderCharts(analysisResult);
    if (!viewer && window.THREE) viewer = new Tower3DViewer("canvas-3d");
    if (viewer) { viewer.renderTower(analysisResult, values); viewer.resetCamera(values.height_m); }
    notify("Structural analysis complete.");
  } catch (error) {
    byId("input-state").textContent = "Analysis failed";
    notify(error.message, true);
  } finally { hideBusy(); }
}

function renderOptimization(data) {
  optimizationResult = data;
  byId("optimization-summary").textContent = data.tradeoff_summary;
  const cards = data.candidates.map((candidate) => {
    const card = document.createElement("article");
    card.className = `candidate-card${candidate.is_recommended ? " recommended" : ""}`;
    if (candidate.is_recommended) { const badge = document.createElement("span"); badge.className = "recommended-badge"; badge.textContent = "Recommended"; card.append(badge); }
    const title = document.createElement("h3"); title.className = "candidate-title"; title.textContent = candidate.name;
    const status = statusBadge(candidate.status);
    const metrics = document.createElement("div"); metrics.className = "candidate-metrics";
    [["Estimated cost", `$${format(candidate.estimated_cost_usd, 0)}`], ["Steel mass", `${format(candidate.steel_mass_kg, 0)} kg`],
      ["Peak utilization", `${format(candidate.max_utilization * 100, 1)}%`], ["Top deflection", `${format(candidate.max_deflection_mm)} mm`],
      ["Leg section", `${candidate.leg_dimension_mm} x ${candidate.leg_thickness_mm} mm`], ["Base width", `${format(candidate.base_width_m)} m`]]
      .forEach(([label, value]) => { const item = document.createElement("div"); item.className = "metric-item"; const key = document.createElement("span"); key.textContent = label; const result = document.createElement("strong"); result.textContent = value; item.append(key, result); metrics.append(item); });
    card.append(title, status, metrics);
    return card;
  });
  byId("optimization-grid").replaceChildren(...cards);
}

async function optimize() {
  let values;
  try { values = readForm(); }
  catch (error) { notify(error.message, true); return; }
  showBusy("Comparing design candidates...");
  try {
    const response = await request("/api/optimize", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(values) });
    renderOptimization(await response.json());
    selectTab("optimization");
    notify("Optimization comparison complete.");
  } catch (error) { notify(error.message, true); }
  finally { hideBusy(); }
}

async function exportFile(formatName) {
  let values;
  try { values = readForm(); }
  catch (error) { notify(error.message, true); return; }
  showBusy(`Generating ${formatName.toUpperCase()} export...`);
  try {
    const response = await request(`/api/export/${formatName}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(values) });
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = response.headers.get("content-disposition")?.match(/filename="?([^";]+)"?/)?.[1] || `tower-export.${formatName}`;
    document.body.append(link); link.click(); link.remove(); URL.revokeObjectURL(url);
    notify(`${formatName.toUpperCase()} export downloaded.`);
  } catch (error) { notify(error.message, true); }
  finally { hideBusy(); }
}

function selectTab(name) {
  document.querySelectorAll(".tab-btn").forEach((button) => button.classList.toggle("active", button.dataset.tab === name));
  document.querySelectorAll(".tab-content").forEach((section) => section.classList.toggle("active", section.id === `tab-${name}`));
  if (name === "model" && viewer) viewer.onWindowResize();
}

document.querySelectorAll("[data-preset]").forEach((button) => button.addEventListener("click", () => loadPreset(button.dataset.preset)));
document.querySelectorAll(".tab-btn").forEach((button) => button.addEventListener("click", () => selectTab(button.dataset.tab)));
byId("tower-form").addEventListener("submit", (event) => { event.preventDefault(); analyze(); });
byId("analyze-button").addEventListener("click", analyze);
byId("optimize-button").addEventListener("click", optimize);
byId("equipment-json").addEventListener("input", () => {
  try { byId("equipment-count").textContent = `${JSON.parse(byId("equipment-json").value).length} items`; }
  catch { byId("equipment-count").textContent = "Invalid JSON"; }
});
byId("export-menu-button").addEventListener("click", (event) => {
  const menu = byId("export-options");
  const expanded = event.currentTarget.getAttribute("aria-expanded") === "true";
  event.currentTarget.setAttribute("aria-expanded", String(!expanded));
  menu.hidden = expanded;
});
document.querySelectorAll("[data-export]").forEach((button) => button.addEventListener("click", () => {
  byId("export-options").hidden = true;
  byId("export-menu-button").setAttribute("aria-expanded", "false");
  exportFile(button.dataset.export);
}));
byId("rotate-button").addEventListener("click", (event) => {
  if (viewer) event.currentTarget.classList.toggle("selected", viewer.toggleAutoRotate());
});
byId("wind-button").addEventListener("click", (event) => {
  if (viewer) { const visible = viewer.toggleWind(); event.currentTarget.textContent = visible ? "Wind on" : "Wind off"; }
});
byId("camera-button").addEventListener("click", () => { if (viewer && towerInput) viewer.resetCamera(towerInput.height_m); });

loadPreset("40m");