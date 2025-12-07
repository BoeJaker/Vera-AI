// -------------------------------------------------------------
//  Interactive Calendar - Widget → Compact → Full
//  Full JS file — NO external CSS required
// -------------------------------------------------------------

class InteractiveCalendar {
  constructor(selector, options = {}) {
    this.options = Object.assign({
      accent: "#4c8bf5",
      background: "#fff",
      foreground: "#111",
      radius: "16px",
      speed: "260ms",
      events: []
    }, options);

    this.mount = document.querySelector(selector);
    if (!this.mount) throw new Error("Calendar mount point not found.");

    this.mode = "widget"; 
    this.date = new Date();
    this.dragStartY = null;
    this.dragging = false;

    this.injectStyles();
    this.render();
    this.enableDrag();
  }

  // -------------------------------------------------------------
  //  STYLES (injected once)
  // -------------------------------------------------------------
  injectStyles() {
    if (document.querySelector("#interactive-calendar-style")) return;

    const style = document.createElement("style");
    style.id = "interactive-calendar-style";
    style.textContent = `

    /* BASE */
    .ic-container {
      width: 320px;
      font-family: system-ui, sans-serif;
      background: var(--bg, #fff);
      color: var(--fg, #111);
      border-radius: var(--radius, 16px);
      box-shadow: 0 6px 18px rgba(0,0,0,0.08);
      overflow: hidden;
      transition: transform var(--speed, 260ms) cubic-bezier(.17,.89,.32,1.28);
      touch-action: pan-y;
      user-select: none;
    }
    .ic-container.dragging {
      transform: scale(0.97);
    }

    /* WIDGET MODE */
    .ic-widget {
      padding: 14px 18px;
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .ic-widget-date {
      font-size: 1.5rem;
      font-weight: 700;
    }
    .ic-widget-info {
      opacity: 0.7;
    }

    /* COMPACT MODE */
    .ic-compact {
      padding: 18px;
      animation: ic-slideDown .35s cubic-bezier(.17,.89,.32,1.28);
    }

    /* FULL MODE */
    .ic-full {
      padding: 18px;
      overflow-y: auto;
      height: 90vh;
      max-height: 90vh;
      animation: ic-fullExpand .45s cubic-bezier(.17,.89,.32,1.28);
    }

    @keyframes ic-slideDown {
      from { opacity: 0; transform: translateY(-10px) scale(0.97); }
      to   { opacity: 1; transform: translateY(0) scale(1); }
    }

    @keyframes ic-fullExpand {
      from { opacity: 0; transform: translateY(-12px) scale(.97); }
      to   { opacity: 1; transform: translateY(0) scale(1); }
    }

    /* HEADER */
    .ic-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 1.1rem;
      margin-bottom: 12px;
      font-weight: 600;
    }
    .ic-header button {
      background: none;
      border: none;
      cursor: pointer;
      font-size: 1.3rem;
      opacity: 0.6;
      transition: opacity .2s ease;
    }
    .ic-header button:hover { opacity: 1; }

    /* GRID */
    .ic-grid {
      display: grid;
      grid-template-columns: repeat(7, 1fr);
      gap: 6px;
    }
    .ic-day {
      text-align: center;
      padding: 7px 0 14px;
      border-radius: 8px;
      cursor: pointer;
      position: relative;
      transition: background .2s ease, transform .2s ease;
    }
    .ic-day:hover {
      background: rgba(0, 0, 0, 0.07);
      transform: scale(1.04);
    }
    .ic-day.today {
      background: var(--accent, #4c8bf5);
      color: white;
    }

    /* EVENT DOT */
    .ic-dot {
      width: 6px;
      height: 6px;
      background: var(--accent, #4c8bf5);
      border-radius: 50%;
      margin: 4px auto 0;
    }

    /* POPOVER */
    .ic-popover {
      position: absolute;
      left: 50%;
      top: -8px;
      transform: translateX(-50%) translateY(-100%);
      padding: 6px 10px;
      background: var(--bg, white);
      border-radius: 10px;
      box-shadow: 0 4px 12px rgba(0,0,0,.18);
      font-size: 0.82rem;
      white-space: nowrap;
      opacity: 0;
      animation: ic-popIn .22s cubic-bezier(.17,.89,.32,1.28) forwards;
    }
    @keyframes ic-popIn {
      from { opacity: 0; transform: translateX(-50%) translateY(-115%) scale(.85); }
      to   { opacity: 1; transform: translateX(-50%) translateY(-100%) scale(1); }
    }

    /* FULL VIEW LAYOUT */
    .ic-full-layout {
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 24px;
      margin-top: 14px;
    }

    /* AGENDA */
    .ic-agenda {
      padding-left: 16px;
      border-left: 1px solid rgba(0,0,0,0.1);
      font-size: 0.9rem;
    }
    .ic-agenda-item {
      margin-bottom: 14px;
    }
    .ic-agenda-date {
      font-weight: 600;
      margin-bottom: 4px;
    }
    .ic-agenda-text {
      opacity: 0.75;
    }

    `;
    document.head.appendChild(style);
  }

  // -------------------------------------------------------------
  //  RENDER
  // -------------------------------------------------------------
  render() {
    this.mount.innerHTML = "";
    this.mount.className = "ic-container";

    // Set CSS variables
    this.mount.style.setProperty("--accent", this.options.accent);
    this.mount.style.setProperty("--bg", this.options.background);
    this.mount.style.setProperty("--fg", this.options.foreground);
    this.mount.style.setProperty("--radius", this.options.radius);
    this.mount.style.setProperty("--speed", this.options.speed);

    // WIDGET
    this.widget = this.buildWidget();
    this.mount.appendChild(this.widget);

    // COMPACT VIEW
    this.compact = this.buildCompact();
    this.compact.classList.add("hidden");
    this.mount.appendChild(this.compact);

    // FULL VIEW (with agenda)
    this.full = this.buildFull();
    this.full.classList.add("hidden");
    this.mount.appendChild(this.full);

    this.mount.onclick = (e) => {
      if (this.dragging) return;
      this.advanceMode();
    };
  }

  // -------------------------------------------------------------
  //  WIDGET
  // -------------------------------------------------------------
  buildWidget() {
    const wrap = document.createElement("div");
    wrap.className = "ic-widget";

    wrap.innerHTML = `
      <div class="ic-widget-date">${this.date.getDate()}</div>
      <div class="ic-widget-info">${this.todayEventText()}</div>
    `;

    return wrap;
  }

  // -------------------------------------------------------------
  //  COMPACT MONTH VIEW
  // -------------------------------------------------------------
  buildCompact() {
    const wrap = document.createElement("div");
    wrap.className = "ic-compact";

    wrap.appendChild(this.buildHeader());
    wrap.appendChild(this.buildGrid());

    return wrap;
  }

  // -------------------------------------------------------------
  //  FULL MONTH VIEW WITH AGENDA
  // -------------------------------------------------------------
  buildFull() {
    const wrap = document.createElement("div");
    wrap.className = "ic-full";

    const layout = document.createElement("div");
    layout.className = "ic-full-layout";

    layout.appendChild(this.buildGrid());
    layout.appendChild(this.buildAgenda());

    wrap.appendChild(this.buildHeader());
    wrap.appendChild(layout);

    return wrap;
  }

  // -------------------------------------------------------------
  //  HEADER
  // -------------------------------------------------------------
  buildHeader() {
    const wrap = document.createElement("div");
    wrap.className = "ic-header";

    wrap.innerHTML = `
      <button data-nav="-1">‹</button>
      <div>${this.date.toLocaleString("default",{month:"long"})} ${this.date.getFullYear()}</div>
      <button data-nav="1">›</button>
    `;

    wrap.querySelectorAll("button").forEach(btn => {
      btn.onclick = (e) => {
        e.stopPropagation();
        this.date.setMonth(this.date.getMonth() + Number(btn.dataset.nav));
        this.refresh();
      };
    });

    return wrap;
  }

  // -------------------------------------------------------------
  //  GRID WITH EVENT DOTS
  // -------------------------------------------------------------
  buildGrid() {
    const grid = document.createElement("div");
    grid.className = "ic-grid";

    const y = this.date.getFullYear();
    const m = this.date.getMonth();
    const first = new Date(y, m, 1).getDay();
    const days = new Date(y, m+1, 0).getDate();
    const today = new Date();

    for (let i = 0; i < first; i++) grid.appendChild(document.createElement("div"));

    for (let d = 1; d <= days; d++) {
      const day = document.createElement("div");
      day.className = "ic-day";
      day.textContent = d;

      if (d === today.getDate() && m === today.getMonth() && y === today.getFullYear())
        day.classList.add("today");

      const events = this.eventsFor(y,m,d);
      if (events.length) {
        const dot = document.createElement("div");
        dot.className = "ic-dot";
        day.appendChild(dot);

        day.onclick = (e) => {
          e.stopPropagation();
          this.showPopover(day, events);
        };
      }

      grid.appendChild(day);
    }

    return grid;
  }

  // -------------------------------------------------------------
  //  AGENDA LIST
  // -------------------------------------------------------------
  buildAgenda() {
    const box = document.createElement("div");
    box.className = "ic-agenda";

    const events = [...this.options.events].sort(
      (a,b) => new Date(a.date) - new Date(b.date)
    );

    if (!events.length) {
      box.textContent = "No upcoming events";
      return box;
    }

    events.forEach(ev => {
      const dt = new Date(ev.date);

      const item = document.createElement("div");
      item.className = "ic-agenda-item";
      item.innerHTML = `
        <div class="ic-agenda-date">${dt.toDateString()}</div>
        <div class="ic-agenda-text">${ev.text}</div>
      `;
      box.appendChild(item);
    });

    return box;
  }

  // -------------------------------------------------------------
  //  POPUP
  // -------------------------------------------------------------
  showPopover(el, events) {
    this.mount.querySelectorAll(".ic-popover").forEach(p => p.remove());

    const pop = document.createElement("div");
    pop.className = "ic-popover";
    pop.textContent = events.map(e => e.text).join(" • ");

    el.appendChild(pop);

    setTimeout(() => pop.remove(), 3500);
  }

  // -------------------------------------------------------------
  //  EVENTS HELPERS
  // -------------------------------------------------------------
  todayEventText() {
    const today = new Date().toDateString();
    const ev = this.options.events.find(e => new Date(e.date).toDateString() === today);
    return ev ? ev.text : "";
  }

  eventsFor(y,m,d) {
    return this.options.events.filter(e => {
      const dt = new Date(e.date);
      return dt.getFullYear() === y && dt.getMonth() === m && dt.getDate() === d;
    });
  }

  // -------------------------------------------------------------
  //  REFRESH ALL VIEWS
  // -------------------------------------------------------------
  refresh() {
    this.compact.innerHTML = "";
    this.compact.appendChild(this.buildHeader());
    this.compact.appendChild(this.buildGrid());

    this.full.innerHTML = "";
    const layout = document.createElement("div");
    layout.className = "ic-full-layout";
    layout.appendChild(this.buildGrid());
    layout.appendChild(this.buildAgenda());

    this.full.appendChild(this.buildHeader());
    this.full.appendChild(layout);
  }

  // -------------------------------------------------------------
  //  MODE SWITCHING (Widget → Compact → Full)
  // -------------------------------------------------------------
  advanceMode() {
    if (this.mode === "widget") this.openCompact();
    else if (this.mode === "compact") this.openFull();
    else this.closeToWidget();
  }

  openCompact() {
    this.widget.classList.add("hidden");
    this.compact.classList.remove("hidden");
    this.full.classList.add("hidden");
    this.mode = "compact";
  }

  openFull() {
    this.compact.classList.add("hidden");
    this.full.classList.remove("hidden");
    this.mode = "full";
  }

  closeToWidget() {
    this.full.classList.add("hidden");
    this.compact.classList.add("hidden");
    this.widget.classList.remove("hidden");
    this.mode = "widget";
  }

  // -------------------------------------------------------------
  //  DRAG DOWN TO EXPAND (Option C)
  // -------------------------------------------------------------
  enableDrag() {
    const start = (y) => { this.dragStartY = y; this.dragging = false; };
    const move = (y) => {
      if (!this.dragStartY) return;

      const delta = y - this.dragStartY;
      if (delta > 8) this.dragging = true;

      if (this.dragging && this.mode === "widget") {
        this.mount.classList.add("dragging");
        this.mount.style.transform = `translateY(${Math.min(delta, 100)}px) scale(.97)`;
      }
    };
    const end = (y) => {
      if (!this.dragStartY) return;

      const delta = y - this.dragStartY;
      this.mount.classList.remove("dragging");
      this.mount.style.transform = "";

      if (this.mode === "widget" && delta > 40) this.openCompact();
      else if (this.mode === "compact" && delta > 120) this.openFull();

      this.dragStartY = null;
      this.dragging = false;
    };

    // Mouse
    this.mount.addEventListener("mousedown", e => start(e.clientY));
    window.addEventListener("mousemove", e => move(e.clientY));
    window.addEventListener("mouseup", e => end(e.clientY));

    // Touch  
    this.mount.addEventListener("touchstart", e => start(e.touches[0].clientY));
    this.mount.addEventListener("touchmove", e => move(e.touches[0].clientY));
    this.mount.addEventListener("touchend", e => end(e.changedTouches[0].clientY));
  }
}
new InteractiveCalendar("#calendar-widget", {
  accent: "#6a5acd",
  events: [
    { date: "2025-12-03", text: "Design Review @ 3pm" },
    { date: "2025-12-04", text: "Product Release" },
    { date: new Date(), text: "Daily standup" }
  ]
});

// <div id="calendar-widget"></div>
// <script src="calendar.js"></script>