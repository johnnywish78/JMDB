const state = {
  theme: localStorage.getItem("jmdb-theme") || "dark",
  page: "dashboard"
};

const pages = {
  dashboard: {
    title: "Dashboard",
    subtitle: "Your media library at a glance."
  },
  library: {
    title: "Library",
    subtitle: "Manage your movies, series and media."
  },
  search: {
    title: "Search",
    subtitle: "Search your local library and metadata providers."
  },
  lists: {
    title: "Lists",
    subtitle: "Collections and personal lists."
  },
  browser: {
    title: "Browser",
    subtitle: "Embedded web browser."
  },
  services: {
    title: "Services",
    subtitle: "External services and integrations."
  },
  settings: {
    title: "Settings",
    subtitle: "Configure JMDB."
  }
};

function applyTheme(theme) {
  if (theme === "system") {
    document.documentElement.removeAttribute("data-theme");
  } else {
    document.documentElement.dataset.theme = theme;
  }

  state.theme = theme;
  localStorage.setItem("jmdb-theme", theme);
}

function setActiveNav(page) {
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle(
      "active",
      button.dataset.page === page
    );
  });
}

function renderDashboard() {
  return `
    <div class="hero">
      <h2>Welcome to JMDB</h2>
      <p>
        The foundation is running. The library, metadata,
        players, integrations and the full JPNH-style browser
        will be added on top of this stable core.
      </p>
    </div>

    <div class="cards">
      <div class="card">
        <div class="card-label">Media</div>
        <div id="media-count" class="card-value">—</div>
      </div>

      <div class="card">
        <div class="card-label">Database</div>
        <div class="card-value">SQLite</div>
      </div>

      <div class="card">
        <div class="card-label">Backend</div>
        <div class="card-value">FastAPI</div>
      </div>

      <div class="card">
        <div class="card-label">Desktop</div>
        <div class="card-value">Electron</div>
      </div>
    </div>
  `;
}

function renderGeneric(page) {
  const item = pages[page];

  return `
    <div class="hero">
      <h2>${item.title}</h2>
      <p>
        ${item.subtitle}
      </p>
      <p>
        This module is part of the JMDB foundation and will be
        implemented in its dedicated build phase.
      </p>
    </div>
  `;
}

function renderSettings() {
  return `
    <div class="settings-section">
      <div class="setting-row">
        <div class="setting-info">
          <strong>Appearance</strong>
          <span>Choose the JMDB application theme.</span>
        </div>

        <select id="theme-select">
          <option value="dark">Dark</option>
          <option value="light">Light</option>
          <option value="system">System</option>
        </select>
      </div>
    </div>
  `;
}

async function checkBackend() {
  try {
    const baseUrl = await window.jmdb.backend.getUrl();

    const response = await fetch(`${baseUrl}/api/health`);

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();

    document.getElementById("status-dot")
      .classList.add("online");

    document.getElementById("status-text").textContent =
      "Backend online";

    const count = document.getElementById("media-count");

    if (count) {
      const statusResponse = await fetch(
        `${baseUrl}/api/system/status`
      );

      const status = await statusResponse.json();

      count.textContent = String(status.media_count);
    }

    return data;
  } catch (error) {
    document.getElementById("status-text").textContent =
      "Backend offline";

    console.error("JMDB backend check failed:", error);
  }
}

function render(page) {
  state.page = page;

  const info = pages[page];

  document.getElementById("page-title").textContent =
    info.title;

  document.getElementById("page-subtitle").textContent =
    info.subtitle;

  setActiveNav(page);

  const content = document.getElementById("content");

  if (page === "dashboard") {
    content.innerHTML = renderDashboard();
  } else if (page === "settings") {
    content.innerHTML = renderSettings();

    const select = document.getElementById("theme-select");
    select.value = state.theme;

    select.addEventListener("change", (event) => {
      applyTheme(event.target.value);
    });
  } else {
    content.innerHTML = renderGeneric(page);
  }

  checkBackend();
}

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => {
    render(button.dataset.page);
  });
});

document.getElementById("global-search")
  .addEventListener("click", () => {
    render("search");
  });

applyTheme(state.theme);
render("dashboard");
