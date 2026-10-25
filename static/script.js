/**
 * Website Health Monitor with Auto-Alerts - Frontend Application Logic
 */

document.addEventListener("DOMContentLoaded", () => {
  // Application State
  const state = {
    websites: [],
    history: [],
    alerts: [],
    summary: {},
    systemStatus: {},
    selectedChartSiteId: "all",
    selectedHistorySiteId: "all",
    siteToDelete: null,
    searchQuery: "",
    statusFilter: null, // 'online' | 'offline' | null
    refreshCountdown: 15,
    chartInstance: null,
    isCheckingAll: false,
    activeView: "overview",
  };

  // DOM Elements
  const elements = {
    // Topbar & Nav
    sidebar: document.getElementById("sidebar"),
    mobileToggle: document.getElementById("mobileMenuToggle"),
    seedDemoBtn: document.getElementById("seedDemoBtn"),
    checkAllBtn: document.getElementById("checkAllBtn"),
    openAddModalBtn: document.getElementById("openAddModalBtn"),
    siteSearchInput: document.getElementById("siteSearchInput"),
    resetFilterBtn: document.getElementById("resetFilterBtn"),
    sidebarSitesBadge: document.getElementById("sidebarSitesBadge"),
    sidebarHistoryBadge: document.getElementById("sidebarHistoryBadge"),
    sidebarAlertsBadge: document.getElementById("sidebarAlertsBadge"),
    countdownText: document.getElementById("countdownText"),
    schedulerIntervalText: document.getElementById("schedulerIntervalText"),
    smtpStatusPill: document.getElementById("smtpStatusPill"),
    smtpStatusText: document.getElementById("smtpStatusText"),
    smtpBanner: document.getElementById("smtpBanner"),
    smtpBannerText: document.getElementById("smtpBannerText"),
    dismissBannerBtn: document.getElementById("dismissBannerBtn"),
    pageHeading: document.getElementById("pageHeading"),
    pageSubheading: document.getElementById("pageSubheading"),

    // Sections
    sectionWebsites: document.getElementById("sectionWebsites"),
    sectionAnalytics: document.getElementById("sectionAnalytics"),
    sectionHistory: document.getElementById("sectionHistory"),
    sectionAlerts: document.getElementById("sectionAlerts"),
    metricsSection: document.getElementById("metricsSection"),

    // Metrics Cards
    statTotalSites: document.getElementById("statTotalSites"),
    statOnlineSites: document.getElementById("statOnlineSites"),
    statOfflineSites: document.getElementById("statOfflineSites"),
    statOnlinePercent: document.getElementById("statOnlinePercent"),
    statOfflineSub: document.getElementById("statOfflineSub"),
    statTotalAlerts: document.getElementById("statTotalAlerts"),
    statAvgResponseTime: document.getElementById("statAvgResponseTime"),

    // Tables & Feeds
    websitesTableBody: document.getElementById("websitesTableBody"),
    emptyWebsitesState: document.getElementById("emptyWebsitesState"),
    historyTableBody: document.getElementById("historyTableBody"),
    emptyHistoryState: document.getElementById("emptyHistoryState"),
    historyWebsiteSelect: document.getElementById("historyWebsiteSelect"),
    refreshHistoryBtn: document.getElementById("refreshHistoryBtn"),
    alertsFeed: document.getElementById("alertsFeed"),
    emptyAlertsState: document.getElementById("emptyAlertsState"),

    // Chart
    chartCanvas: document.getElementById("responseTimeChart"),
    chartSelect: document.getElementById("chartWebsiteSelect"),

    // Modals
    addModal: document.getElementById("addWebsiteModal"),
    closeAddModalBtn: document.getElementById("closeAddModalBtn"),
    cancelAddModalBtn: document.getElementById("cancelAddModalBtn"),
    addForm: document.getElementById("addWebsiteForm"),
    inputUrl: document.getElementById("inputUrl"),
    inputName: document.getElementById("inputName"),
    urlErrorMsg: document.getElementById("urlErrorMsg"),
    submitAddSiteBtn: document.getElementById("submitAddSiteBtn"),

    deleteModal: document.getElementById("deleteModal"),
    closeDeleteModalBtn: document.getElementById("closeDeleteModalBtn"),
    cancelDeleteBtn: document.getElementById("cancelDeleteBtn"),
    confirmDeleteBtn: document.getElementById("confirmDeleteBtn"),
    deleteSiteName: document.getElementById("deleteSiteName"),

    // Toasts
    toastContainer: document.getElementById("toastContainer"),
  };

  // ----------------------------------------------------------------------------
  // Initialization
  // ----------------------------------------------------------------------------
  async function init() {
    setupEventListeners();
    setupNavigation();

    // Initialize Chart with safety fallback
    try {
      initChart();
    } catch (err) {
      console.warn("Chart.js initialization deferred or failed:", err);
    }

    // Load initial data
    await fetchAllData();

    // Start auto-refresh timer
    startCountdownTimer();

    // Process URL hash if present
    handleHashNavigation();
  }

  // ----------------------------------------------------------------------------
  // Navigation & View Handling
  // ----------------------------------------------------------------------------
  function setupNavigation() {
    // Nav link click listeners
    document.querySelectorAll(".sidebar-nav .nav-item").forEach((item) => {
      item.addEventListener("click", (e) => {
        const view = item.dataset.view;
        if (view) {
          switchView(view);
        }
        if (window.innerWidth <= 900) {
          elements.sidebar.classList.remove("mobile-open");
        }
      });
    });

    window.addEventListener("hashchange", handleHashNavigation);
  }

  function handleHashNavigation() {
    const hash = (window.location.hash || "").replace("#", "").toLowerCase();
    if (["overview", "websites", "history", "alerts"].includes(hash)) {
      switchView(hash);
    }
  }

  function switchView(viewName) {
    state.activeView = viewName;

    // Update active nav item
    document.querySelectorAll(".sidebar-nav .nav-item").forEach((item) => {
      if (item.dataset.view === viewName) {
        item.classList.add("active");
      } else {
        item.classList.remove("active");
      }
    });

    // Scroll smoothly to target section
    let targetSection = null;
    let headingText = "Website Health Monitor";
    let subheadingText = "Real-time status tracking, latency metrics, and automated alerts";

    if (viewName === "websites") {
      targetSection = elements.sectionWebsites;
      headingText = "Monitored Websites";
      subheadingText = "Manage active endpoints, test connectivity, and inspect response status";
    } else if (viewName === "history") {
      targetSection = elements.sectionHistory;
      headingText = "Health Check History";
      subheadingText = "Historical check audit log, timestamps, and latency performance records";
    } else if (viewName === "alerts") {
      targetSection = elements.sectionAlerts;
      headingText = "Alert Incidents & Delivery";
      subheadingText = "Downtime and recovery event history with SMTP delivery status logs";
    } else {
      targetSection = elements.metricsSection;
      headingText = "Website Health Monitor";
      subheadingText = "Real-time status tracking, latency metrics, and automated alerts";
    }

    if (elements.pageHeading) elements.pageHeading.textContent = headingText;
    if (elements.pageSubheading) elements.pageSubheading.textContent = subheadingText;

    if (targetSection) {
      targetSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }
  window.switchView = switchView; // expose globally

  function filterSitesByStatus(status) {
    state.statusFilter = status;
    if (elements.resetFilterBtn) {
      elements.resetFilterBtn.style.display = "inline-flex";
      elements.resetFilterBtn.textContent = `Clear Filter (${status})`;
    }
    switchView("websites");
    renderWebsitesTable();
  }
  window.filterSitesByStatus = filterSitesByStatus;

  function resetSiteFilter() {
    state.statusFilter = null;
    state.searchQuery = "";
    if (elements.siteSearchInput) elements.siteSearchInput.value = "";
    if (elements.resetFilterBtn) elements.resetFilterBtn.style.display = "none";
    renderWebsitesTable();
  }
  window.resetSiteFilter = resetSiteFilter;

  // ----------------------------------------------------------------------------
  // Event Listeners
  // ----------------------------------------------------------------------------
  function setupEventListeners() {
    // Mobile sidebar toggle
    if (elements.mobileToggle) {
      elements.mobileToggle.addEventListener("click", () => {
        elements.sidebar.classList.toggle("mobile-open");
      });
    }

    // Seed Demo Data Button
    if (elements.seedDemoBtn) {
      elements.seedDemoBtn.addEventListener("click", handleSeedDemoData);
    }

    // Check All Button
    if (elements.checkAllBtn) {
      elements.checkAllBtn.addEventListener("click", handleCheckAll);
    }

    // Open/Close Add Modal
    if (elements.openAddModalBtn) {
      elements.openAddModalBtn.addEventListener("click", openAddModal);
    }
    window.openAddModal = openAddModal; // expose for empty state button

    if (elements.closeAddModalBtn) {
      elements.closeAddModalBtn.addEventListener("click", closeAddModal);
    }
    if (elements.cancelAddModalBtn) {
      elements.cancelAddModalBtn.addEventListener("click", closeAddModal);
    }

    // Add Website Form Submit
    if (elements.addForm) {
      elements.addForm.addEventListener("submit", handleAddWebsiteSubmit);
    }

    // Close Delete Modal
    if (elements.closeDeleteModalBtn) {
      elements.closeDeleteModalBtn.addEventListener("click", closeDeleteModal);
    }
    if (elements.cancelDeleteBtn) {
      elements.cancelDeleteBtn.addEventListener("click", closeDeleteModal);
    }
    if (elements.confirmDeleteBtn) {
      elements.confirmDeleteBtn.addEventListener("click", handleConfirmDelete);
    }

    // Close modals on clicking backdrop
    window.addEventListener("click", (e) => {
      if (e.target === elements.addModal) closeAddModal();
      if (e.target === elements.deleteModal) closeDeleteModal();
    });

    // Close modals on Escape key
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        closeAddModal();
        closeDeleteModal();
      }
    });

    // Dismiss SMTP banner
    if (elements.dismissBannerBtn) {
      elements.dismissBannerBtn.addEventListener("click", () => {
        elements.smtpBanner.style.display = "none";
      });
    }

    // Search filter input
    if (elements.siteSearchInput) {
      elements.siteSearchInput.addEventListener("input", (e) => {
        state.searchQuery = e.target.value.toLowerCase().trim();
        renderWebsitesTable();
      });
    }

    // Chart site selector dropdown
    if (elements.chartSelect) {
      elements.chartSelect.addEventListener("change", (e) => {
        state.selectedChartSiteId = e.target.value;
        updateChartData();
      });
    }

    // History site filter dropdown
    if (elements.historyWebsiteSelect) {
      elements.historyWebsiteSelect.addEventListener("change", async (e) => {
        state.selectedHistorySiteId = e.target.value;
        await fetchHistory(state.selectedHistorySiteId);
      });
    }

    // Refresh history button
    if (elements.refreshHistoryBtn) {
      elements.refreshHistoryBtn.addEventListener("click", async () => {
        await fetchHistory(state.selectedHistorySiteId);
        showToast("Health history refreshed.", "info");
      });
    }
  }

  // ----------------------------------------------------------------------------
  // API Fetch Functions
  // ----------------------------------------------------------------------------
  async function fetchAllData() {
    try {
      await Promise.allSettled([
        fetchSummary(),
        fetchWebsites(),
        fetchHistory(state.selectedHistorySiteId),
        fetchAlerts(),
        fetchSystemStatus(),
      ]);
    } catch (err) {
      console.error("Error loading dashboard data:", err);
    }
  }

  async function fetchSummary() {
    try {
      const res = await fetch("/api/summary");
      const json = await res.json();
      if (json.success) {
        state.summary = json.data;
        renderSummary();
      }
    } catch (err) {
      console.error("Failed to fetch summary:", err);
    }
  }

  async function fetchWebsites() {
    try {
      const res = await fetch("/api/websites");
      const json = await res.json();
      if (json.success) {
        state.websites = json.data || [];
        renderWebsitesTable();
        updateFilterDropdowns();
        if (elements.sidebarSitesBadge) {
          elements.sidebarSitesBadge.textContent = state.websites.length;
        }
      }
    } catch (err) {
      console.error("Failed to fetch websites:", err);
    }
  }

  async function fetchHistory(websiteId = "all") {
    try {
      let url = "/api/history?limit=50";
      if (websiteId && websiteId !== "all") {
        url = `/api/websites/${websiteId}/history?limit=50`;
      }

      const res = await fetch(url);
      const json = await res.json();
      if (json.success) {
        state.history = json.data || [];
        renderHistoryTable();
        updateChartData();
        if (elements.sidebarHistoryBadge) {
          elements.sidebarHistoryBadge.textContent = state.history.length;
        }
      }
    } catch (err) {
      console.error("Failed to fetch history:", err);
    }
  }

  async function fetchAlerts() {
    try {
      const res = await fetch("/api/alerts?limit=25");
      const json = await res.json();
      if (json.success) {
        state.alerts = json.data || [];
        renderAlertsFeed();
        if (elements.sidebarAlertsBadge) {
          elements.sidebarAlertsBadge.textContent = state.alerts.length;
        }
      }
    } catch (err) {
      console.error("Failed to fetch alerts:", err);
    }
  }

  async function fetchSystemStatus() {
    try {
      const res = await fetch("/api/system-status");
      const json = await res.json();
      if (json.success) {
        state.systemStatus = json.data;
        renderSystemStatus();
      }
    } catch (err) {
      console.error("Failed to fetch system status:", err);
    }
  }

  // ----------------------------------------------------------------------------
  // Countdown & Periodic Auto-Refresh
  // ----------------------------------------------------------------------------
  function startCountdownTimer() {
    setInterval(async () => {
      state.refreshCountdown -= 1;
      if (state.refreshCountdown <= 0) {
        state.refreshCountdown = 15;
        await fetchAllData();
      }
      if (elements.countdownText) {
        elements.countdownText.textContent = `Next: ${state.refreshCountdown}s`;
      }
    }, 1000);
  }

  // ----------------------------------------------------------------------------
  // Render Functions
  // ----------------------------------------------------------------------------
  function renderSummary() {
    const s = state.summary || {};
    const total = s.total_websites || 0;
    const online = s.online_websites || 0;
    const offline = s.offline_websites || 0;

    if (elements.statTotalSites) elements.statTotalSites.textContent = total;
    if (elements.statOnlineSites) elements.statOnlineSites.textContent = online;
    if (elements.statOfflineSites) elements.statOfflineSites.textContent = offline;
    if (elements.statTotalAlerts) elements.statTotalAlerts.textContent = s.total_alerts || 0;

    const avgMs = s.avg_response_time_ms;
    if (elements.statAvgResponseTime) {
      elements.statAvgResponseTime.textContent = avgMs !== null && avgMs !== undefined ? `${avgMs} ms` : "-- ms";
    }

    if (total > 0) {
      const percent = Math.round((online / total) * 100);
      if (elements.statOnlinePercent) elements.statOnlinePercent.textContent = `${percent}% Up`;
      if (elements.statOfflineSub) elements.statOfflineSub.textContent = `${offline} incident${offline === 1 ? "" : "s"}`;
    } else {
      if (elements.statOnlinePercent) elements.statOnlinePercent.textContent = "100% Up";
      if (elements.statOfflineSub) elements.statOfflineSub.textContent = "0 incidents";
    }
  }

  function renderSystemStatus() {
    const cfg = state.systemStatus || {};
    if (cfg.check_interval_seconds && elements.schedulerIntervalText) {
      elements.schedulerIntervalText.textContent = `Interval: ${cfg.check_interval_seconds}s`;
    }

    if (!elements.smtpStatusPill || !elements.smtpStatusText) return;

    if (cfg.smtp_configured) {
      elements.smtpStatusPill.className = "smtp-pill configured";
      elements.smtpStatusText.textContent = `Email: Active (${cfg.smtp_host || "SMTP"})`;
      if (elements.smtpBanner) elements.smtpBanner.style.display = "none";
    } else {
      elements.smtpStatusPill.className = "smtp-pill not-configured";
      elements.smtpStatusText.textContent = "Email: Not Configured";
      if (elements.smtpBanner) {
        elements.smtpBanner.style.display = "flex";
        if (elements.smtpBannerText) {
          elements.smtpBannerText.innerHTML =
            "SMTP email settings are not configured in <code>.env</code>. The health monitor functions fully and records all alerts in SQLite; set SMTP variables to receive real emails.";
        }
      }
    }
  }

  function renderWebsitesTable() {
    const tbody = elements.websitesTableBody;
    if (!tbody) return;
    tbody.innerHTML = "";

    const filtered = (state.websites || []).filter((site) => {
      // Status filter
      if (state.statusFilter && site.status !== state.statusFilter) {
        return false;
      }
      // Search query filter
      if (!state.searchQuery) return true;
      return (
        (site.name && site.name.toLowerCase().includes(state.searchQuery)) ||
        (site.url && site.url.toLowerCase().includes(state.searchQuery))
      );
    });

    if (filtered.length === 0) {
      if (elements.emptyWebsitesState) elements.emptyWebsitesState.style.display = "block";
      return;
    }

    if (elements.emptyWebsitesState) elements.emptyWebsitesState.style.display = "none";

    filtered.forEach((site) => {
      const tr = document.createElement("tr");
      tr.id = `site-row-${site.id}`;

      // Status Pill & Dot
      const statusClass = site.status || "unknown";
      const statusHtml = `
        <span class="status-pill ${statusClass}">
          <span class="status-indicator-dot ${statusClass}"></span>
          ${site.status}
        </span>
      `;

      // Site Name & URL
      const siteCell = `
        <div class="site-cell">
          <span class="site-title">${escapeHtml(site.name)}</span>
          <a href="${escapeHtml(site.url)}" target="_blank" rel="noopener noreferrer" class="site-url-link">
            <span>${escapeHtml(site.url)}</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:12px;height:12px;"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
          </a>
        </div>
      `;

      // Status Code
      let codeHtml = '<span class="code-badge">--</span>';
      if (site.status_code) {
        let codeClass = "code-2xx";
        if (site.status_code >= 300 && site.status_code < 400) codeClass = "code-3xx";
        else if (site.status_code >= 400 && site.status_code < 500) codeClass = "code-4xx";
        else if (site.status_code >= 500) codeClass = "code-5xx";

        codeHtml = `<span class="code-badge ${codeClass}">${site.status_code}</span>`;
      } else if (site.error_message) {
        codeHtml = `<span class="code-badge code-err" title="${escapeHtml(site.error_message)}">ERR</span>`;
      }

      // Latency
      let latencyHtml = '<span class="latency-pill">--</span>';
      if (site.response_time_ms !== null && site.response_time_ms !== undefined) {
        const ms = site.response_time_ms;
        let latClass = "fast";
        if (ms > 300) latClass = "medium";
        if (ms > 1000) latClass = "slow";
        latencyHtml = `<span class="latency-pill ${latClass}">${ms} ms</span>`;
      }

      // Last Checked
      const lastCheckedStr = site.last_checked ? formatRelativeTime(site.last_checked) : "Never";

      // Action Buttons: Check, History, Remove
      const actionsHtml = `
        <div class="action-buttons">
          <button class="btn btn-secondary btn-sm check-single-btn" data-id="${site.id}" title="Check health now">
            <svg class="spin-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/></svg>
            <span>Check</span>
          </button>
          <button class="btn btn-secondary btn-sm view-history-btn" data-id="${site.id}" data-name="${escapeHtml(site.name)}" title="Inspect historical checks">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
            <span>History</span>
          </button>
          <button class="btn-icon delete-btn delete-single-btn" data-id="${site.id}" data-name="${escapeHtml(site.name)}" title="Remove website">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:16px;height:16px;"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
          </button>
        </div>
      `;

      tr.innerHTML = `
        <td>${statusHtml}</td>
        <td>${siteCell}</td>
        <td>${codeHtml}</td>
        <td>${latencyHtml}</td>
        <td class="text-muted text-sm" title="${site.last_checked || ''}">${lastCheckedStr}</td>
        <td class="text-right">${actionsHtml}</td>
      `;

      tbody.appendChild(tr);
    });

    // Attach row button events
    tbody.querySelectorAll(".check-single-btn").forEach((btn) => {
      btn.addEventListener("click", () => handleCheckSingle(btn.dataset.id, btn));
    });

    tbody.querySelectorAll(".view-history-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const siteId = btn.dataset.id;
        if (elements.historyWebsiteSelect) {
          elements.historyWebsiteSelect.value = siteId;
        }
        if (elements.chartSelect) {
          elements.chartSelect.value = siteId;
          state.selectedChartSiteId = siteId;
        }
        state.selectedHistorySiteId = siteId;
        fetchHistory(siteId);
        switchView("history");
      });
    });

    tbody.querySelectorAll(".delete-single-btn").forEach((btn) => {
      btn.addEventListener("click", () => openDeleteModal(btn.dataset.id, btn.dataset.name));
    });
  }

  function renderHistoryTable() {
    const tbody = elements.historyTableBody;
    if (!tbody) return;
    tbody.innerHTML = "";

    if (!state.history || state.history.length === 0) {
      if (elements.emptyHistoryState) elements.emptyHistoryState.style.display = "block";
      return;
    }
    if (elements.emptyHistoryState) elements.emptyHistoryState.style.display = "none";

    state.history.forEach((h) => {
      const tr = document.createElement("tr");

      const timeFormatted = formatFullDateTime(h.checked_at);
      const statusClass = h.status === "online" ? "online" : "offline";

      // Status Code
      let codeHtml = '<span class="code-badge">--</span>';
      if (h.status_code) {
        const cClass = h.status_code < 400 ? "code-2xx" : (h.status_code < 500 ? "code-4xx" : "code-5xx");
        codeHtml = `<span class="code-badge ${cClass}">${h.status_code}</span>`;
      } else if (h.error_message) {
        codeHtml = `<span class="code-badge code-err">ERR</span>`;
      }

      // Latency
      let msHtml = '<span class="latency-pill">--</span>';
      if (h.response_time_ms !== null && h.response_time_ms !== undefined) {
        let latClass = "fast";
        if (h.response_time_ms > 300) latClass = "medium";
        if (h.response_time_ms > 1000) latClass = "slow";
        msHtml = `<span class="latency-pill ${latClass}">${h.response_time_ms} ms</span>`;
      }

      // Details / Error
      let detailsHtml = '<span class="text-muted text-sm">Response received successfully</span>';
      if (h.error_message) {
        detailsHtml = `<span class="text-danger text-sm" style="color:#ef4444;">${escapeHtml(h.error_message)}</span>`;
      } else if (h.status_code && h.status_code >= 400) {
        detailsHtml = `<span class="text-warning text-sm" style="color:#f59e0b;">HTTP ${h.status_code} returned by host</span>`;
      }

      tr.innerHTML = `
        <td class="text-muted text-sm font-mono">${timeFormatted}</td>
        <td>
          <div class="site-cell">
            <strong class="site-title">${escapeHtml(h.website_name || "Website")}</strong>
            <span class="text-muted text-sm">${escapeHtml(h.website_url || "")}</span>
          </div>
        </td>
        <td>
          <span class="status-pill ${statusClass}">
            <span class="status-indicator-dot ${statusClass}"></span>
            ${h.status}
          </span>
        </td>
        <td>${codeHtml}</td>
        <td>${msHtml}</td>
        <td>${detailsHtml}</td>
      `;

      tbody.appendChild(tr);
    });
  }

  function renderAlertsFeed() {
    const container = elements.alertsFeed;
    if (!container) return;
    container.innerHTML = "";

    if (!state.alerts || state.alerts.length === 0) {
      if (elements.emptyAlertsState) elements.emptyAlertsState.style.display = "block";
      return;
    }
    if (elements.emptyAlertsState) elements.emptyAlertsState.style.display = "none";

    state.alerts.forEach((alert) => {
      const item = document.createElement("div");
      const isDowntime = alert.alert_type === "downtime";
      item.className = `alert-item ${isDowntime ? "downtime" : "recovery"}`;

      const iconSvg = isDowntime
        ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`
        : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`;

      const typeLabel = isDowntime ? "DOWNTIME DETECTED" : "SERVICE RECOVERED";
      const reason = alert.error_message || (alert.status_code ? `HTTP ${alert.status_code}` : "Connection Failure");

      // Delivery Status
      let delClass = "skipped_no_smtp";
      let delText = "Email Skipped (No SMTP)";
      if (alert.delivery_status === "sent") {
        delClass = "sent";
        delText = "Email Dispatched";
      } else if (alert.delivery_status === "failed") {
        delClass = "failed";
        delText = `Email Failed: ${alert.delivery_error || "Error"}`;
      }

      item.innerHTML = `
        <div class="alert-type-icon">${iconSvg}</div>
        <div class="alert-content">
          <div class="alert-header">
            <span class="alert-title">${escapeHtml(alert.website_name)} &bull; ${typeLabel}</span>
            <span class="alert-time">${formatRelativeTime(alert.created_at)}</span>
          </div>
          <div class="alert-msg">${escapeHtml(reason)}</div>
          <div class="delivery-badge ${delClass}">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:11px;height:11px;"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
            <span>${delText}</span>
          </div>
        </div>
      `;

      container.appendChild(item);
    });
  }

  // ----------------------------------------------------------------------------
  // Chart.js Setup & Updates
  // ----------------------------------------------------------------------------
  function initChart() {
    if (!elements.chartCanvas) return;
    if (typeof Chart === "undefined") {
      console.warn("Chart.js is not loaded yet.");
      return;
    }

    const ctx = elements.chartCanvas.getContext("2d");
    if (!ctx) return;

    state.chartInstance = new Chart(ctx, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: "Response Time (ms)",
            data: [],
            borderColor: "#0284c7",
            backgroundColor: "rgba(2, 132, 199, 0.08)",
            borderWidth: 2,
            tension: 0.35,
            fill: true,
            pointBackgroundColor: "#0284c7",
            pointRadius: 4,
            pointHoverRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: "#0f172a",
            titleFont: { family: "Inter", size: 12 },
            bodyFont: { family: "Inter", size: 13, weight: "bold" },
            padding: 10,
            cornerRadius: 6,
            callbacks: {
              label: (context) => `Latency: ${context.parsed.y} ms`,
            },
          },
        },
        scales: {
          x: {
            grid: { color: "#f1f5f9" },
            ticks: { font: { family: "Inter", size: 11 }, color: "#94a3b8" },
          },
          y: {
            beginAtZero: true,
            grid: { color: "#e2e8f0" },
            ticks: {
              font: { family: "Inter", size: 11 },
              color: "#94a3b8",
              callback: (val) => `${val}ms`,
            },
          },
        },
      },
    });
  }

  function updateFilterDropdowns() {
    // 1. Update Chart Selector
    if (elements.chartSelect) {
      const curChartVal = state.selectedChartSiteId;
      elements.chartSelect.innerHTML = '<option value="all">All Websites</option>';
      (state.websites || []).forEach((site) => {
        const opt = document.createElement("option");
        opt.value = site.id;
        opt.textContent = site.name;
        elements.chartSelect.appendChild(opt);
      });
      elements.chartSelect.value = curChartVal;
    }

    // 2. Update History Filter Selector
    if (elements.historyWebsiteSelect) {
      const curHistVal = state.selectedHistorySiteId;
      elements.historyWebsiteSelect.innerHTML = '<option value="all">All Monitored Sites</option>';
      (state.websites || []).forEach((site) => {
        const opt = document.createElement("option");
        opt.value = site.id;
        opt.textContent = site.name;
        elements.historyWebsiteSelect.appendChild(opt);
      });
      elements.historyWebsiteSelect.value = curHistVal;
    }
  }

  function updateChartData() {
    if (!state.chartInstance) {
      try {
        initChart();
      } catch (e) {
        return;
      }
    }
    if (!state.chartInstance) return;

    let points = [];
    if (state.selectedChartSiteId === "all") {
      points = [...state.history].reverse();
    } else {
      const siteId = parseInt(state.selectedChartSiteId, 10);
      points = state.history.filter((h) => h.website_id === siteId).reverse();
    }

    // Take up to 30 latest data points
    const sliced = points.slice(-30);

    const labels = sliced.map((h) => formatSimpleTime(h.checked_at));
    const data = sliced.map((h) => h.response_time_ms || 0);

    state.chartInstance.data.labels = labels;
    state.chartInstance.data.datasets[0].data = data;
    state.chartInstance.update();
  }

  // ----------------------------------------------------------------------------
  // Actions: Add Website
  // ----------------------------------------------------------------------------
  function openAddModal() {
    if (elements.inputUrl) elements.inputUrl.value = "";
    if (elements.inputName) elements.inputName.value = "";
    if (elements.urlErrorMsg) {
      elements.urlErrorMsg.textContent = "";
      elements.urlErrorMsg.classList.remove("visible");
    }
    if (elements.addModal) {
      elements.addModal.classList.add("active");
      elements.addModal.setAttribute("aria-hidden", "false");
      setTimeout(() => {
        if (elements.inputUrl) elements.inputUrl.focus();
      }, 100);
    }
  }

  function closeAddModal() {
    if (elements.addModal) {
      elements.addModal.classList.remove("active");
      elements.addModal.setAttribute("aria-hidden", "true");
    }
  }

  async function handleAddWebsiteSubmit(e) {
    e.preventDefault();
    const rawUrl = elements.inputUrl.value.trim();
    const name = elements.inputName.value.trim();

    if (!rawUrl) {
      showUrlError("Please enter a valid website URL.");
      return;
    }

    const btn = elements.submitAddSiteBtn;
    const btnText = btn ? btn.querySelector(".btn-text") : null;
    const btnSpinner = btn ? btn.querySelector(".btn-spinner") : null;

    if (btn) btn.disabled = true;
    if (btnText) btnText.textContent = "Verifying & Checking...";
    if (btnSpinner) btnSpinner.style.display = "inline-block";
    if (elements.urlErrorMsg) elements.urlErrorMsg.classList.remove("visible");

    try {
      const response = await fetch("/api/websites", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: rawUrl, name: name }),
      });

      const json = await response.json();

      if (!response.ok || !json.success) {
        showUrlError(json.error || "Failed to add website.");
        return;
      }

      showToast(`Website '${json.data.name}' added successfully!`, "success");
      closeAddModal();
      await fetchAllData();
      switchView("websites");
    } catch (err) {
      showUrlError("Network connection error. Please try again.");
    } finally {
      if (btn) btn.disabled = false;
      if (btnText) btnText.textContent = "Add & Check Website";
      if (btnSpinner) btnSpinner.style.display = "none";
    }
  }

  function showUrlError(msg) {
    if (elements.urlErrorMsg) {
      elements.urlErrorMsg.textContent = msg;
      elements.urlErrorMsg.classList.add("visible");
    }
  }

  // ----------------------------------------------------------------------------
  // Actions: Check Single Website
  // ----------------------------------------------------------------------------
  async function handleCheckSingle(siteId, btn) {
    const icon = btn.querySelector(".spin-icon");
    const textSpan = btn.querySelector("span");
    btn.disabled = true;
    if (icon) icon.classList.add("spinning");
    if (textSpan) textSpan.textContent = "Checking";

    try {
      const res = await fetch(`/api/websites/${siteId}/check`, { method: "POST" });
      const json = await res.json();
      if (json.success) {
        showToast(json.message || "Health check completed.", "success");
        await fetchAllData();
      } else {
        showToast(json.error || "Check failed.", "error");
      }
    } catch (err) {
      showToast("Error executing health check.", "error");
    } finally {
      btn.disabled = false;
      if (icon) icon.classList.remove("spinning");
      if (textSpan) textSpan.textContent = "Check";
    }
  }

  // ----------------------------------------------------------------------------
  // Actions: Check All Websites
  // ----------------------------------------------------------------------------
  async function handleCheckAll() {
    if (state.isCheckingAll) return;
    state.isCheckingAll = true;

    const btn = elements.checkAllBtn;
    const icon = btn ? btn.querySelector(".spin-icon") : null;
    const span = btn ? btn.querySelector("span") : null;

    if (btn) btn.disabled = true;
    if (icon) icon.classList.add("spinning");
    if (span) span.textContent = "Checking All...";

    try {
      const res = await fetch("/api/websites/check-all", { method: "POST" });
      const json = await res.json();
      if (json.success) {
        showToast(json.message || "Checked all websites.", "success");
        await fetchAllData();
      } else {
        showToast("Failed to check all websites.", "error");
      }
    } catch (err) {
      showToast("Network error checking all sites.", "error");
    } finally {
      state.isCheckingAll = false;
      if (btn) btn.disabled = false;
      if (icon) icon.classList.remove("spinning");
      if (span) span.textContent = "Check All Now";
    }
  }

  // ----------------------------------------------------------------------------
  // Actions: Seed Demo Data
  // ----------------------------------------------------------------------------
  async function handleSeedDemoData() {
    const btn = elements.seedDemoBtn;
    if (!btn) return;
    const span = btn.querySelector("span");
    const originalText = span ? span.textContent : "Load Demo Data";
    btn.disabled = true;
    if (span) span.textContent = "Loading Demo...";

    try {
      const res = await fetch("/api/seed-demo", { method: "POST" });
      const json = await res.json();
      if (json.success) {
        showToast(json.message || "Demo dataset loaded!", "success");
        await fetchAllData();
      } else {
        showToast("Failed to load demo data.", "error");
      }
    } catch (err) {
      showToast("Network error loading demo data.", "error");
    } finally {
      btn.disabled = false;
      if (span) span.textContent = originalText;
    }
  }

  // ----------------------------------------------------------------------------
  // Actions: Delete Website
  // ----------------------------------------------------------------------------
  function openDeleteModal(siteId, siteName) {
    state.siteToDelete = { id: siteId, name: siteName };
    if (elements.deleteSiteName) elements.deleteSiteName.textContent = siteName || "this website";
    if (elements.deleteModal) {
      elements.deleteModal.classList.add("active");
      elements.deleteModal.setAttribute("aria-hidden", "false");
    }
  }

  function closeDeleteModal() {
    state.siteToDelete = null;
    if (elements.deleteModal) {
      elements.deleteModal.classList.remove("active");
      elements.deleteModal.setAttribute("aria-hidden", "true");
    }
  }

  async function handleConfirmDelete() {
    if (!state.siteToDelete) return;
    const { id, name } = state.siteToDelete;

    const btn = elements.confirmDeleteBtn;
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Deleting...";
    }

    try {
      const res = await fetch(`/api/websites/${id}`, { method: "DELETE" });
      const json = await res.json();
      if (json.success) {
        showToast(`Website '${name}' was removed.`, "info");
        closeDeleteModal();
        await fetchAllData();
      } else {
        showToast(json.error || "Failed to delete website.", "error");
      }
    } catch (err) {
      showToast("Network error during deletion.", "error");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = "Delete Website";
      }
    }
  }

  // ----------------------------------------------------------------------------
  // Toast Notifications
  // ----------------------------------------------------------------------------
  function showToast(message, type = "info") {
    if (!elements.toastContainer) return;
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;

    let iconSvg = "";
    if (type === "success") {
      iconSvg = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:18px;height:18px;color:#10b981;flex-shrink:0;"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`;
    } else if (type === "error") {
      iconSvg = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:18px;height:18px;color:#ef4444;flex-shrink:0;"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`;
    } else {
      iconSvg = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:18px;height:18px;color:#0284c7;flex-shrink:0;"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`;
    }

    toast.innerHTML = `${iconSvg}<span>${escapeHtml(message)}</span>`;
    elements.toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(50px)";
      setTimeout(() => toast.remove(), 250);
    }, 4000);
  }

  // ----------------------------------------------------------------------------
  // Helper Utilities
  // ----------------------------------------------------------------------------
  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function formatRelativeTime(dateString) {
    if (!dateString) return "Never";
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString;

    const now = new Date();
    const diffSec = Math.floor((now - date) / 1000);

    if (diffSec < 10) return "Just now";
    if (diffSec < 60) return `${diffSec}s ago`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHours = Math.floor(diffMin / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleDateString();
  }

  function formatSimpleTime(dateString) {
    if (!dateString) return "--";
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString;
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
  }

  function formatFullDateTime(dateString) {
    if (!dateString) return "--";
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString;
    return date.toISOString().replace("T", " ").substring(0, 19);
  }

  // Start the application
  init();
});
