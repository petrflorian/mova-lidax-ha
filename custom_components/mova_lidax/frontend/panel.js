class MovaLidaxPanel extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  connectedCallback() {
    this.render();
  }

  entityId(domain, preferred, suffixes = []) {
    const states = this._hass?.states || {};
    if (states[preferred]) return preferred;
    for (const suffix of suffixes) {
      const found = Object.keys(states).find((entityId) => entityId.startsWith(`${domain}.lidax_ultra`) && entityId.endsWith(suffix));
      if (found) return found;
    }
    return preferred;
  }

  state(entityId) {
    const entity = this._hass?.states?.[entityId];
    if (!entity || entity.state === "unknown" || entity.state === "unavailable") return "N/A";
    return entity.state;
  }

  attr(entityId, key, fallback = null) {
    return this._hass?.states?.[entityId]?.attributes?.[key] ?? fallback;
  }

  call(domain, service, data = {}, target = {}) {
    this._hass.callService(domain, service, data, target);
  }

  renderHistory(historyEntity) {
    const rows = this.attr(historyEntity, "history", []) || [];
    if (!rows.length) {
      return `<div class="empty">Historie sečení zatím není načtená.</div>`;
    }
    return `
      <table>
        <thead>
          <tr>
            <th>Datum</th>
            <th>Mapa</th>
            <th>Plocha</th>
            <th>Délka</th>
            <th>Dokončení</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          ${rows.slice(0, 10).map((item) => {
            const rawDate = item.created_at || item.start_time;
            const date = rawDate ? new Date(rawDate).toLocaleString("cs-CZ", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "N/A";
            const status = item.status_code === 1 ? "Dokončeno" : `Kód ${item.status_code ?? "N/A"}`;
            return `
              <tr>
                <td>${date}</td>
                <td>${item.map_name || "N/A"}</td>
                <td>${item.mowed_area ?? "N/A"} m²</td>
                <td>${item.duration ?? "N/A"} min</td>
                <td>${item.completion_percent ?? "N/A"} %</td>
                <td>${status}</td>
              </tr>
            `;
          }).join("")}
        </tbody>
      </table>
    `;
  }

  render() {
    if (!this._hass) return;

    const mower = this.entityId("lawn_mower", "lawn_mower.lidax_ultra");
    const battery = this.entityId("sensor", "sensor.lidax_ultra");
    const state = this.entityId("sensor", "sensor.lidax_ultra_state", ["_state"]);
    const taskStatus = this.entityId("sensor", "sensor.lidax_ultra_task_status", ["_task_status"]);
    const select = this.entityId("select", "select.lidax_ultra");
    const activeMap = this.entityId("sensor", "sensor.lidax_ultra_active_map_ha", ["_active_map_ha"]);
    const progress = this.entityId("sensor", "sensor.lidax_ultra_current_mowing_progress", ["_current_mowing_progress"]);
    const mowedArea = this.entityId("sensor", "sensor.lidax_ultra_current_mowed_area", ["_current_mowed_area"]);
    const targetArea = this.entityId("sensor", "sensor.lidax_ultra_current_mowing_target_area", ["_current_mowing_target_area"]);
    const dnd = this.entityId("sensor", "sensor.lidax_ultra_do_not_disturb", ["_do_not_disturb"]);
    const dndStart = this.entityId("sensor", "sensor.lidax_ultra_do_not_disturb_start", ["_do_not_disturb_start"]);
    const dndEnd = this.entityId("sensor", "sensor.lidax_ultra_do_not_disturb_end", ["_do_not_disturb_end"]);
    const mapArea = this.entityId("sensor", "sensor.lidax_ultra_current_map_area", ["_current_map_area"]);
    const mapZones = this.entityId("sensor", "sensor.lidax_ultra_current_map_zones", ["_current_map_zones"]);
    const schedules = this.entityId("sensor", "sensor.lidax_ultra_current_map_schedules", ["_current_map_schedules"]);
    const history = this.entityId("sensor", "sensor.lidax_ultra_mowing_history", ["_mowing_history"]);
    const total = this.entityId("sensor", "sensor.lidax_ultra_total_mowed_area", ["_total_mowed_area"]);

    const options = this.attr(select, "options", []);
    const progressValue = Number.parseFloat(this.state(progress));
    const progressPercent = Number.isFinite(progressValue) ? Math.max(0, Math.min(progressValue, 100)) : 0;

    this.innerHTML = `
      <style>
        :host {
          display: block;
          min-height: 100vh;
          box-sizing: border-box;
          padding: 28px;
          color: var(--primary-text-color);
          background: radial-gradient(circle at top left, rgba(72, 149, 239, .16), transparent 34rem), var(--primary-background-color);
          font-family: var(--ha-font-family-body, sans-serif);
        }
        .wrap { max-width: 1180px; margin: 0 auto; }
        .hero {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 24px;
          margin-bottom: 24px;
        }
        .brand-logo {
          width: min(210px, 42vw);
          height: auto;
          opacity: .94;
        }
        h1 { margin: 0 0 8px; font-size: clamp(34px, 4vw, 56px); line-height: 1; }
        .subtitle { color: var(--secondary-text-color); font-size: 18px; margin-bottom: 24px; }
        .grid { display: grid; gap: 16px; grid-template-columns: repeat(4, minmax(0, 1fr)); }
        .wide { grid-column: span 2; }
        .full { grid-column: 1 / -1; }
        .card {
          border: 1px solid var(--divider-color);
          border-radius: 22px;
          background: color-mix(in srgb, var(--card-background-color) 90%, transparent);
          padding: 20px;
          box-shadow: var(--ha-card-box-shadow, none);
        }
        .label { color: var(--secondary-text-color); font-size: 14px; margin-bottom: 8px; }
        .value { font-size: 30px; font-weight: 750; overflow-wrap: anywhere; }
        .small { font-size: 18px; font-weight: 600; }
        .actions { display: flex; flex-wrap: wrap; gap: 10px; }
        button {
          border: 0;
          border-radius: 999px;
          padding: 12px 16px;
          font: inherit;
          font-weight: 700;
          color: var(--text-primary-color);
          background: var(--primary-color);
          cursor: pointer;
        }
        button.secondary { color: var(--primary-text-color); background: color-mix(in srgb, var(--primary-color) 14%, var(--card-background-color)); }
        .bar { height: 18px; border-radius: 999px; background: var(--divider-color); overflow: hidden; margin-top: 14px; }
        .bar > div { height: 100%; width: ${progressPercent}%; background: linear-gradient(90deg, #78d68b, #d4d879); }
        table { width: 100%; border-collapse: collapse; font-size: 15px; }
        th, td { padding: 10px 8px; border-bottom: 1px solid var(--divider-color); text-align: left; }
        th { color: var(--secondary-text-color); font-weight: 700; }
        .empty { color: var(--secondary-text-color); }
        @media (max-width: 900px) {
          :host { padding: 16px; }
          .hero { align-items: flex-start; flex-direction: column-reverse; gap: 12px; }
          .grid { grid-template-columns: 1fr; }
          .wide, .full { grid-column: auto; }
          .value { font-size: 24px; }
        }
      </style>
      <div class="wrap">
        <div class="hero">
          <div>
            <h1>LiDAX Ultra</h1>
            <div class="subtitle">Produkční přehled sekačky, map, DND, aktuálního průběhu a historie.</div>
          </div>
          <img class="brand-logo" src="/mova_lidax_static/logo.png" alt="MOVA">
        </div>

        <div class="grid">
          <div class="card">
            <div class="label">Sekačka</div>
            <div class="value">${this.state(mower)}</div>
          </div>
          <div class="card">
            <div class="label">Baterie</div>
            <div class="value">${this.state(battery)} %</div>
          </div>
          <div class="card">
            <div class="label">Stav</div>
            <div class="value small">${this.state(state)}</div>
          </div>
          <div class="card">
            <div class="label">Hláška úlohy</div>
            <div class="value small">${this.state(taskStatus)}</div>
          </div>

          <div class="card wide">
            <div class="label">Aktivní mapa</div>
            <div class="value">${this.state(select)}</div>
            <div class="subtitle">HA potvrzení: ${this.state(activeMap)}</div>
            <div class="actions">
              ${(options || []).map((option) => `<button class="secondary" data-map="${option}">${option}</button>`).join("")}
            </div>
          </div>
          <div class="card wide">
            <div class="label">Rychlé akce</div>
            <div class="actions">
              <button data-action="start">Start</button>
              <button class="secondary" data-action="pause">Pause</button>
              <button class="secondary" data-action="dock">Dock</button>
            </div>
          </div>

          <div class="card wide">
            <div class="label">Aktuální sečení</div>
            <div class="value">${this.state(progress)} %</div>
            <div class="bar"><div></div></div>
            <div class="subtitle">${this.state(mowedArea)} / ${this.state(targetArea)} m²</div>
          </div>
          <div class="card">
            <div class="label">Mapa</div>
            <div class="value small">${this.state(mapArea)} m²</div>
            <div class="subtitle">${this.state(mapZones)} zón</div>
          </div>
          <div class="card">
            <div class="label">Plány</div>
            <div class="value">${this.state(schedules)}</div>
          </div>
          <div class="card">
            <div class="label">DND</div>
            <div class="value small">${this.state(dnd)}</div>
            <div class="subtitle">${this.state(dndStart)} - ${this.state(dndEnd)}</div>
          </div>
          <div class="card">
            <div class="label">Celkem z historie</div>
            <div class="value small">${this.state(total)} m²</div>
          </div>

          <div class="card full">
            <div class="label">Poslední sečení</div>
            ${this.renderHistory(history)}
          </div>
        </div>
      </div>
    `;

    this.querySelectorAll("[data-map]").forEach((button) => {
      button.addEventListener("click", () => this.call("select", "select_option", { option: button.dataset.map }, { entity_id: select }));
    });
    this.querySelector("[data-action='start']")?.addEventListener("click", () => this.call("lawn_mower", "start_mowing", {}, { entity_id: mower }));
    this.querySelector("[data-action='pause']")?.addEventListener("click", () => this.call("lawn_mower", "pause", {}, { entity_id: mower }));
    this.querySelector("[data-action='dock']")?.addEventListener("click", () => this.call("lawn_mower", "dock", {}, { entity_id: mower }));
  }
}

customElements.define("mova-lidax-panel", MovaLidaxPanel);
