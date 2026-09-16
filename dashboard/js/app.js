/* Unified Automation Framework dashboard client (no build step, no dependencies). */
(function () {
  "use strict";

  var PREFS_KEY = "fw-dashboard-prefs-v1";
  var CATEGORIES = ["api", "ui", "api_ui", "e2e"];

  var state = {
    info: null,
    tests: [],
    grouped: {},
    selection: new Set(),
    activeCategory: "api",
    search: "",
    expanded: {},
    running: false,
    pollTimer: null,
    docsLoaded: false,
    lastResults: null,
  };

  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  /* ---------------- preferences ---------------- */
  function loadPrefs() {
    try {
      var prefs = JSON.parse(localStorage.getItem(PREFS_KEY) || "{}");
      if (prefs.browser) $("browserSelect").value = prefs.browser;
      if (prefs.headless === false) {
        document.querySelector('input[name="headlessMode"][value="headed"]').checked = true;
      }
      if (prefs.env) $("envSelect").value = prefs.env;
      if (prefs.device) $("deviceInput").value = prefs.device;
      if (prefs.workers) $("workersSelect").value = prefs.workers;
      if (Array.isArray(prefs.selection)) {
        state.selection = new Set(prefs.selection);
      }
      if (prefs.theme === "dark" || prefs.theme === "light") {
        document.documentElement.setAttribute("data-theme", prefs.theme);
      }
    } catch (e) { /* corrupted prefs: ignore */ }
  }
  function savePrefs() {
    try {
      localStorage.setItem(PREFS_KEY, JSON.stringify({
        browser: $("browserSelect").value,
        headless: document.querySelector('input[name="headlessMode"]:checked').value === "headless",
        env: $("envSelect").value,
        device: $("deviceInput").value,
        workers: $("workersSelect").value,
        selection: Array.prototype.slice.call(state.selection).slice(0, 2000),
        theme: document.documentElement.getAttribute("data-theme") || "",
      }));
    } catch (e) { /* storage unavailable: ignore */ }
  }

  /* ---------------- api ---------------- */
  function api(path, options) {
    options = options || {};
    options.headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});
    return fetch(path, options).then(function (res) {
      var isJson = (res.headers.get("content-type") || "").indexOf("application/json") !== -1;
      if (!isJson) {
        if (!res.ok) throw new Error("Request failed: " + res.status);
        return res;
      }
      return res.json().then(function (data) {
        if (!res.ok || data.ok === false) {
          throw new Error(data.error || ("Request failed: " + res.status));
        }
        return data;
      });
    });
  }
  function message(text, isError) {
    var el = $("actionMessage");
    el.textContent = text;
    el.style.color = isError ? "var(--fail)" : "var(--ok)";
  }

  function currentOptions() {
    return {
      browser: $("browserSelect").value,
      headless: document.querySelector('input[name="headlessMode"]:checked').value === "headless",
      environment: $("envSelect").value,
      device: $("deviceInput").value.trim(),
      workers: $("workersSelect").value,
    };
  }

  /* ---------------- info / tests ---------------- */
  function loadInfo() {
    return api("/api/info").then(function (data) {
      state.info = data;
      $("versionBadge").textContent = "v" + data.framework_version;
      var envSel = $("envSelect");
      envSel.innerHTML = "";
      data.environments.forEach(function (env) {
        var opt = document.createElement("option");
        opt.value = env; opt.textContent = env.toUpperCase();
        envSel.appendChild(opt);
      });
      try {
        var prefs = JSON.parse(localStorage.getItem(PREFS_KEY) || "{}");
        if (prefs.env) envSel.value = prefs.env;
      } catch (e) {}
      $("footerVersions").textContent =
        "Framework v" + data.framework_version + " · Python " + data.python_version +
        " · Playwright " + data.playwright_version + " · Pytest " + data.pytest_version +
        " · Backend " + data.backend;
      updateEnvInfo();
    });
  }

  function updateEnvInfo() {
    var o = currentOptions();
    $("envInfo").textContent =
      "Selected: browser=" + o.browser + " · mode=" + (o.headless ? "headless" : "headed") +
      " · env=" + (o.environment || "?").toUpperCase() +
      " · device=" + (o.device || "default viewport") +
      " · workers=" + (o.workers === "0" ? "serial" : o.workers) +
      " — these settings are passed to pytest/Playwright on every run.";
  }

  function loadTests(force) {
    var p = force ? api("/api/tests/refresh", { method: "POST" }) : api("/api/tests");
    return p.then(function (data) {
      state.tests = data.tests;
      state.grouped = data.grouped;
      var known = {};
      state.tests.forEach(function (t) { known[t.nodeid] = true; });
      state.selection.forEach(function (nodeid) {
        if (!known[nodeid]) state.selection.delete(nodeid);
      });
      renderCounts();
      renderTree();
      updateSelectedCount();
      savePrefs();
    }).catch(function (err) {
      $("testTree").innerHTML = '<p class="fail-text">Test discovery failed: ' + esc(err.message) + "</p>";
    });
  }

  function renderCounts() {
    CATEGORIES.forEach(function (cat) {
      var n = 0;
      var files = state.grouped[cat] || {};
      Object.keys(files).forEach(function (f) { n += files[f].length; });
      $("count-" + cat).textContent = n;
    });
  }

  function matchesSearch(t) {
    var q = state.search.trim().toLowerCase();
    if (!q) return true;
    var hay = (t.test_name + " " + t.file + " " + (t.class || "") + " " +
      t.category + " " + t.nodeid + " " + (t.markers || []).join(" ")).toLowerCase();
    return hay.indexOf(q) !== -1;
  }

  function renderTree() {
    var cat = state.activeCategory;
    var tree = $("testTree");
    var files = state.grouped[cat] || {};
    var names = Object.keys(files).sort();
    if (!names.length) {
      tree.innerHTML = '<p class="muted">No tests discovered in this category.</p>';
      $("searchCount").textContent = "";
      return;
    }
    var shown = 0, total = 0;
    var html = "";
    names.forEach(function (file) {
      var tests = files[file].filter(matchesSearch);
      total += files[file].length;
      shown += tests.length;
      if (!tests.length) return;
      var key = cat + "::" + file;
      var expanded = state.expanded[key] !== false;
      var selected = tests.filter(function (t) { return state.selection.has(t.nodeid); }).length;
      html += '<div class="file-node" data-file="' + esc(file) + '">' +
        '<div class="file-head">' +
        '<button type="button" class="twisty" data-twisty="' + esc(key) + '" aria-expanded="' + expanded + '" aria-label="' + (expanded ? "Collapse" : "Expand") + " " + esc(file) + '">' + (expanded ? "&#9660;" : "&#9654;") + "</button>" +
        '<input type="checkbox" data-filecheck="' + esc(key) + '" aria-label="Select all tests in ' + esc(file) + '"' +
        (selected === tests.length ? " checked" : "") + ">" +
        '<span class="file-name">' + esc(file.split("/").pop()) + "</span>" +
        '<span class="file-count">' + selected + "/" + tests.length + " selected</span>" +
        "</div>";
      if (expanded) {
        html += '<ul class="test-list">';
        tests.forEach(function (t) {
          var checked = state.selection.has(t.nodeid) ? " checked" : "";
          var markers = (t.markers || []).map(function (m) {
            return '<span class="marker">' + esc(m) + "</span>";
          }).join(" ");
          html += "<li>" +
            '<input type="checkbox" data-nodeid="' + esc(t.nodeid) + '" aria-label="Select ' + esc(t.test_name) + '"' + checked + ">" +
            '<span class="test-name">' + esc(t.test_name) + "</span>" +
            (t.class ? '<span class="test-class">' + esc(t.class) + "</span>" : "") +
            markers + "</li>";
        });
        html += "</ul>";
      }
      html += "</div>";
    });
    tree.innerHTML = html || '<p class="muted">No tests match the search.</p>';
    $("searchCount").textContent = state.search ? ("Matching: " + shown + " / " + total) : ("Total: " + total);

    tree.querySelectorAll("[data-twisty]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var key = btn.getAttribute("data-twisty");
        state.expanded[key] = state.expanded[key] === false;
        renderTree();
      });
    });
    tree.querySelectorAll("[data-filecheck]").forEach(function (box) {
      var key = box.getAttribute("data-filecheck");
      var file = key.split("::").slice(1).join("::");
      var tests = (state.grouped[cat][file] || []).filter(matchesSearch);
      var selected = tests.filter(function (t) { return state.selection.has(t.nodeid); }).length;
      box.indeterminate = selected > 0 && selected < tests.length;
      box.addEventListener("change", function () {
        tests.forEach(function (t) {
          if (box.checked) state.selection.add(t.nodeid);
          else state.selection.delete(t.nodeid);
        });
        updateSelectedCount(); savePrefs(); renderTree();
      });
    });
    tree.querySelectorAll("[data-nodeid]").forEach(function (box) {
      box.addEventListener("change", function () {
        var nodeid = box.getAttribute("data-nodeid");
        if (box.checked) state.selection.add(nodeid);
        else state.selection.delete(nodeid);
        updateSelectedCount(); savePrefs();
        syncFileChecks();
      });
    });
    syncCategoryToggle();
  }

  function syncFileChecks() {
    var cat = state.activeCategory;
    document.querySelectorAll("[data-filecheck]").forEach(function (box) {
      var key = box.getAttribute("data-filecheck");
      var file = key.split("::").slice(1).join("::");
      var tests = ((state.grouped[cat] || {})[file] || []).filter(matchesSearch);
      var selected = tests.filter(function (t) { return state.selection.has(t.nodeid); }).length;
      box.checked = tests.length > 0 && selected === tests.length;
      box.indeterminate = selected > 0 && selected < tests.length;
      var head = box.closest(".file-head");
      if (head) {
        var count = head.querySelector(".file-count");
        if (count) count.textContent = selected + "/" + tests.length + " selected";
      }
    });
    syncCategoryToggle();
  }

  function visibleTestsInCategory() {
    var files = state.grouped[state.activeCategory] || {};
    var out = [];
    Object.keys(files).forEach(function (f) {
      files[f].forEach(function (t) { if (matchesSearch(t)) out.push(t); });
    });
    return out;
  }

  function syncCategoryToggle() {
    var visible = visibleTestsInCategory();
    var selected = visible.filter(function (t) { return state.selection.has(t.nodeid); }).length;
    var box = $("categoryToggle");
    box.checked = visible.length > 0 && selected === visible.length;
    box.indeterminate = selected > 0 && selected < visible.length;
  }

  function updateSelectedCount() {
    $("selectedCount").textContent = state.selection.size;
    $("btnRunSelected").childNodes[0].textContent = "Run Selected (";
  }

  /* ---------------- tabs ---------------- */
  function switchTab(category) {
    state.activeCategory = category;
    document.querySelectorAll('[role="tab"]').forEach(function (tab) {
      var active = tab.getAttribute("data-category") === category;
      tab.setAttribute("aria-selected", active ? "true" : "false");
    });
    var isDocs = category === "docs";
    $("panel-tests").classList.toggle("hidden", isDocs);
    $("panel-docs").classList.toggle("hidden", !isDocs);
    if (isDocs) loadDocs();
    else renderTree();
  }

  /* ---------------- execution ---------------- */
  function setRunningUI(running) {
    state.running = running;
    ["btnRunSelected", "btnRunAll", "btnRunSmoke", "btnRunRegression",
     "btnRerunFailed", "btnRerunAll"].forEach(function (id) { $(id).disabled = running; });
    $("btnStop").disabled = !running;
  }

  function startPolling() {
    stopPolling();
    state.pollTimer = setInterval(pollStatus, 1000);
    pollStatus();
  }
  function stopPolling() {
    if (state.pollTimer) { clearInterval(state.pollTimer); state.pollTimer = null; }
  }

  function pollStatus() {
    api("/api/status").then(function (data) {
      if (data.state === "running" || data.state === "stopping") {
        renderLive(data.active, data.state);
        if (data.active && data.active.results) renderLiveResults(data.active.results);
      } else {
        if (state.running) {
          setRunningUI(false);
          stopPolling();
          renderLiveFinished(data.last_summary);
          refreshResults();
          loadHistory();
        } else {
          $("liveEmpty").classList.remove("hidden");
          $("liveArea").classList.add("hidden");
        }
      }
      if (data.log_tail) $("liveLog").textContent = data.log_tail.join("\n");
    }).catch(function () { /* backend momentarily unreachable: keep polling */ });
  }

  function fmtClock(epochSeconds) {
    if (!epochSeconds) return "-";
    var d = new Date(epochSeconds * 1000);
    function p(n) { return (n < 10 ? "0" : "") + n; }
    return p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds());
  }

  function renderLive(active, statusState) {
    if (!active) return;
    setRunningUI(true);
    $("liveEmpty").classList.add("hidden");
    $("liveArea").classList.remove("hidden");
    var pill = $("liveStatus");
    pill.textContent = statusState === "stopping" ? "stopping..." : "running";
    pill.className = "status-pill running";
    $("liveRunId").textContent = active.run_id;
    $("liveBrowser").textContent = active.browser;
    $("liveMode").textContent = active.headless ? "headless" : "headed";
    $("liveEnv").textContent = (active.environment || "").toUpperCase();
    var total = active.total == null ? "?" : active.total;
    $("liveProgress").textContent = active.finished + " / " + total;
    $("livePassed").textContent = active.counts.passed;
    $("liveFailed").textContent = active.counts.failed;
    $("liveSkipped").textContent = active.counts.skipped;
    $("liveErrors").textContent = active.counts.error;
    $("liveElapsed").textContent = formatDuration(active.elapsed);
    $("liveCommand").textContent = active.command || "";
    var pct = active.total ? Math.round((active.finished / active.total) * 100) : 0;
    $("progressBar").style.width = pct + "%";
    $("progressBarWrap").setAttribute("aria-valuenow", pct);
    var running = active.running_now || [];
    $("liveRunning").innerHTML = running.length
      ? running.map(function (n) { return "<li>" + esc(n) + "</li>"; }).join("")
      : "<li class='muted'>waiting for next test...</li>";
  }

  function renderLiveFinished(summary) {
    var pill = $("liveStatus");
    pill.textContent = summary ? summary.status : "finished";
    pill.className = "status-pill";
    message(summary ? ("Run " + summary.run_id + " " + summary.status +
      " — passed " + (summary.counts.passed || 0) +
      ", failed " + (summary.counts.failed || 0) +
      ", duration " + (summary.suite_duration_formatted || "")) : "Run finished.", false);
  }

  function formatDuration(seconds) {
    seconds = Math.max(0, seconds || 0);
    var ms = Math.round(seconds * 1000);
    var h = Math.floor(ms / 3600000), rem = ms % 3600000;
    var m = Math.floor(rem / 60000); rem = rem % 60000;
    var s = Math.floor(rem / 1000); var milli = rem % 1000;
    function p(n, l) { n = String(n); while (n.length < l) n = "0" + n; return n; }
    if (h) return p(h, 2) + ":" + p(m, 2) + ":" + p(s, 2) + "." + p(milli, 3);
    return p(m, 2) + ":" + p(s, 2) + "." + p(milli, 3);
  }

  function runPayload(mode) {
    var o = currentOptions();
    o.mode = mode;
    if (mode === "selected") {
      o.nodeids = Array.prototype.slice.call(state.selection);
      if (!o.nodeids.length) {
        message("No tests selected. Tick checkboxes in any tab first.", true);
        return null;
      }
    }
    return o;
  }

  function startRun(mode) {
    var payload = runPayload(mode);
    if (!payload) return;
    message("Starting " + mode + " run...", false);
    api("/api/run", { method: "POST", body: JSON.stringify(payload) }).then(function (data) {
      message("Run " + data.run_id + " started: " + data.command, false);
      setRunningUI(true);
      startPolling();
    }).catch(function (err) { message(err.message, true); });
  }

  /* ---------------- results ---------------- */
  function statusIcon(status) {
    return { passed: "&#10003;", failed: "&#10007;", error: "!", skipped: "&#9675;", interrupted: "&#10073;" }[status] || "?";
  }

  function renderResultsTable(results) {
    var body = $("resultsBody");
    if (!results || !results.length) {
      $("resultsEmpty").classList.remove("hidden");
      $("resultsWrap").classList.add("hidden");
      return;
    }
    $("resultsEmpty").classList.add("hidden");
    $("resultsWrap").classList.remove("hidden");
    body.innerHTML = results.map(function (r) {
      var short = r.nodeid.length > 90 ? r.nodeid.slice(0, 87) + "..." : r.nodeid;
      return "<tr>" +
        "<td class='mono' title='" + esc(r.nodeid) + "'>" + esc(short) + "</td>" +
        "<td>" + esc(r.category) + "</td>" +
        "<td><span class='status-" + esc(r.status) + "'>" + statusIcon(r.status) + " " + esc(r.status) + "</span></td>" +
        "<td class='mono'>" + esc(r.duration_formatted || formatDuration(r.duration)) + "</td>" +
        "<td class='mono'>" + esc(fmtClock(r.start_epoch)) + "</td>" +
        "<td class='mono'>" + esc(fmtClock(r.end_epoch)) + "</td>" +
        "<td class='failure-cell' title='" + esc(r.failure || "") + "'>" + esc((r.failure || "").slice(0, 220)) + "</td>" +
        "<td><button type='button' class='btn btn-ghost btn-sm' data-art='" + esc(r.nodeid) + "'>Artifacts</button></td>" +
        "</tr>";
    }).join("");
    body.querySelectorAll("[data-art]").forEach(function (btn) {
      btn.addEventListener("click", function () { openArtifacts(btn.getAttribute("data-art")); });
    });
  }

  function renderLiveResults(results) {
    renderResultsTable(results);
    $("resultsRunId").textContent = results.length ? "(live)" : "";
  }

  function refreshResults(runId) {
    var url = runId ? ("/api/results?run_id=" + encodeURIComponent(runId)) : "/api/results";
    return api(url).then(function (data) {
      state.lastResults = data.run;
      renderFullRun(data.run);
    }).catch(function (err) {
      if (!runId) {
        $("resultsEmpty").textContent = "No results yet.";
        $("summarySection").classList.add("hidden");
        $("failedSection").classList.add("hidden");
      } else message(err.message, true);
    });
  }

  function renderFullRun(run) {
    $("resultsRunId").textContent = "(" + run.run_id + " · " + run.status + ")";
    renderResultsTable(run.results || []);
    renderSummary(run);
    renderFailed(run.results || []);
  }

  function renderSummary(run) {
    var counts = run.counts || {};
    var stats = run.stats || {};
    var settings = run.settings || {};
    var byCat = stats.by_category || {};
    function cell(label, value) {
      return "<div><span class='label'>" + label + "</span><span class='mono'>" + esc(value) + "</span></div>";
    }
    var html =
      cell("Total tests", counts.total == null ? 0 : counts.total) +
      cell("Passed", counts.passed || 0) +
      cell("Failed", counts.failed || 0) +
      cell("Skipped", counts.skipped || 0) +
      cell("Errors", counts.error || 0) +
      cell("Interrupted", counts.interrupted || 0) +
      cell("Suite duration", run.suite_duration_formatted || "-") +
      cell("Average test", stats.average_duration_formatted || "-") +
      cell("Slowest", (stats.slowest_test || "-") + (stats.slowest_duration_formatted ? " (" + stats.slowest_duration_formatted + ")" : "")) +
      cell("Fastest", (stats.fastest_test || "-") + (stats.fastest_duration_formatted ? " (" + stats.fastest_duration_formatted + ")" : "")) +
      cell("API / UI / API+UI / E2E",
        (byCat.api || 0) + " / " + (byCat.ui || 0) + " / " + (byCat.api_ui || 0) + " / " + (byCat.e2e || 0)) +
      cell("Browser", (settings.browser || "-") + " (" + (settings.headless === false ? "headed" : "headless") + ")") +
      cell("Device", settings.device || "default viewport") +
      cell("Environment", (settings.environment || "-").toUpperCase());
    $("summaryGrid").innerHTML = html;
    $("summarySection").classList.remove("hidden");
  }

  function renderFailed(results) {
    var failed = results.filter(function (r) { return r.status === "failed" || r.status === "error"; });
    if (!failed.length) { $("failedSection").classList.add("hidden"); return; }
    $("failedSection").classList.remove("hidden");
    $("failedCount").textContent = failed.length;
    $("failedList").innerHTML = failed.map(function (r) {
      return "<li><code>" + esc(r.nodeid) + "</code><br>" +
        "<span class='muted small'>" + esc(r.category) + " · " + esc(r.duration_formatted || "") +
        " · " + esc(fmtClock(r.start_epoch)) + "</span>" +
        "<pre class='failure-cell'>" + esc((r.failure || "").slice(0, 800)) + "</pre></li>";
    }).join("");
  }

  /* ---------------- history ---------------- */
  function loadHistory() {
    return api("/api/history?limit=30").then(function (data) {
      var runs = data.runs || [];
      if (!runs.length) {
        $("historyEmpty").classList.remove("hidden");
        $("historyWrap").classList.add("hidden");
        return;
      }
      $("historyEmpty").classList.add("hidden");
      $("historyWrap").classList.remove("hidden");
      $("historyBody").innerHTML = runs.map(function (r) {
        var c = r.counts || {};
        return "<tr>" +
          "<td class='mono'>" + esc(r.run_id) + "</td>" +
          "<td>" + esc(r.date) + "</td>" +
          "<td>" + esc(r.status) + "</td>" +
          "<td class='mono'>" + esc(r.suite_duration_formatted || "-") + "</td>" +
          "<td>" + (c.total == null ? "-" : c.total) + "</td>" +
          "<td>" + (c.passed || 0) + "</td>" +
          "<td>" + (c.failed || 0) + "</td>" +
          "<td>" + (c.skipped || 0) + "</td>" +
          "<td>" + esc((r.environment || "").toUpperCase()) + "</td>" +
          "<td>" + esc(r.browser || "-") + "</td>" +
          "<td>" + (r.headless === false ? "headed" : "headless") + "</td>" +
          "<td><button type='button' class='btn btn-ghost btn-sm' data-view-run='" + esc(r.run_id) + "'>View</button></td>" +
          "</tr>";
      }).join("");
      $("historyBody").querySelectorAll("[data-view-run]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          refreshResults(btn.getAttribute("data-view-run"));
          document.getElementById("resultsHeading").scrollIntoView();
        });
      });
    }).catch(function () { /* history unavailable: non-fatal */ });
  }

  /* ---------------- artifacts modal ---------------- */
  function openArtifacts(nodeid) {
    $("artBody").innerHTML = "<p class='muted'>Loading artifacts...</p>";
    $("artModal").classList.remove("hidden");
    api("/api/artifacts/for-test?nodeid=" + encodeURIComponent(nodeid)).then(function (data) {
      var kinds = data.artifacts || {};
      var html = "<p class='mono small'>" + esc(nodeid) + "</p>";
      var any = false;
      Object.keys(kinds).forEach(function (kind) {
        var files = kinds[kind] || [];
        if (!files.length) return;
        any = true;
        html += "<h3>" + esc(kind) + "</h3>";
        files.forEach(function (name) {
          var url = "/api/artifacts/file?type=" + kind + "&name=" + encodeURIComponent(name);
          if (kind === "screenshots") {
            html += "<p><a href='" + url + "' target='_blank' rel='noopener'>" + esc(name) + "</a><br>" +
              "<img src='" + url + "' alt='Screenshot " + esc(name) + "' style='max-width:100%;border:1px solid var(--border);border-radius:8px'></p>";
          } else {
            html += "<p><a href='" + url + "' target='_blank' rel='noopener'>" + esc(name) + "</a> " +
              "<span class='muted small'>(open Allure report to view traces/videos inline)</span></p>";
          }
        });
      });
      if (!any) html += "<p class='muted'>No screenshots, videos or traces recorded for this test. " +
        "Screenshots are captured for UI failures; videos/traces follow the configured modes.</p>";
      $("artBody").innerHTML = html;
    }).catch(function (err) {
      $("artBody").innerHTML = "<p class='fail-text'>" + esc(err.message) + "</p>";
    });
  }

  /* ---------------- logs modal ---------------- */
  function openLogs() {
    $("logsModal").classList.remove("hidden");
    api("/api/logs").then(function (data) {
      var sel = $("logFileSelect");
      sel.innerHTML = "";
      (data.files || []).forEach(function (f) {
        var opt = document.createElement("option");
        opt.value = f.name; opt.textContent = f.name + " (" + f.size + " bytes)";
        sel.appendChild(opt);
      });
      if (!data.files || !data.files.length) {
        $("logContent").textContent = "No log files yet.";
        return;
      }
      loadLogContent();
    }).catch(function (err) { $("logContent").textContent = err.message; });
  }
  function loadLogContent() {
    var name = $("logFileSelect").value;
    if (!name) return;
    api("/api/logs/content?name=" + encodeURIComponent(name) + "&tail=2000").then(function (data) {
      $("logContent").textContent = (data.lines || []).join("\n") || "(empty log)";
    }).catch(function (err) { $("logContent").textContent = err.message; });
  }

  /* ---------------- docs ---------------- */
  function loadDocs() {
    if (state.docsLoaded) return;
    api("/api/documentation").then(function (data) {
      state.docsLoaded = true;
      var content = $("docsContent");
      content.innerHTML = data.html;
      content.querySelectorAll("pre").forEach(function (pre) {
        var btn = document.createElement("button");
        btn.type = "button"; btn.className = "copy-code"; btn.textContent = "Copy";
        btn.addEventListener("click", function () {
          copyText(pre.innerText).then(function () { btn.textContent = "Copied!"; });
          setTimeout(function () { btn.textContent = "Copy"; }, 1500);
        });
        pre.appendChild(btn);
      });
      var toc = $("docsToc");
      var headings = content.querySelectorAll("h1, h2, h3");
      if (!headings.length) { toc.innerHTML = "<p class='muted'>No sections.</p>"; return; }
      var html = "<ul>";
      headings.forEach(function (h, i) {
        if (!h.id) h.id = "doc-h" + i;
        html += "<li class='toc-" + h.tagName.toLowerCase() + "'><a href='#" + h.id + "'>" + esc(h.textContent) + "</a></li>";
      });
      toc.innerHTML = html + "</ul>";
    }).catch(function (err) {
      $("docsContent").innerHTML = "<p class='fail-text'>Documentation failed to load: " + esc(err.message) + "</p>";
    });
  }
  function searchDocs() {
    var q = $("docsSearch").value.trim().toLowerCase();
    var content = $("docsContent");
    content.querySelectorAll("mark").forEach(function (m) {
      m.replaceWith(document.createTextNode(m.textContent));
    });
    if (!q) return;
    var walker = document.createTreeWalker(content, NodeFilter.SHOW_TEXT);
    var nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    var first = null;
    nodes.forEach(function (node) {
      var idx = node.textContent.toLowerCase().indexOf(q);
      if (idx === -1 || node.parentElement.closest("button")) return;
      var before = node.textContent.slice(0, idx);
      var match = node.textContent.slice(idx, idx + q.length);
      var after = node.textContent.slice(idx + q.length);
      var mark = document.createElement("mark");
      mark.textContent = match;
      var parent = node.parentNode;
      parent.insertBefore(document.createTextNode(before), node);
      parent.insertBefore(mark, node);
      parent.insertBefore(document.createTextNode(after), node);
      parent.removeChild(node);
      if (!first) first = mark;
    });
    if (first) first.scrollIntoView({ block: "center" });
  }

  /* ---------------- clipboard ---------------- */
  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve) {
      var ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); } catch (e) {}
      document.body.removeChild(ta);
      resolve();
    });
  }

  /* ---------------- wiring ---------------- */
  function wire() {
    document.querySelectorAll('[role="tab"]').forEach(function (tab) {
      tab.addEventListener("click", function () { switchTab(tab.getAttribute("data-category")); });
    });
    $("searchInput").addEventListener("input", function (e) {
      state.search = e.target.value;
      renderTree();
    });
    $("btnClearSearch").addEventListener("click", function () {
      $("searchInput").value = ""; state.search = ""; renderTree();
    });
    $("btnExpandAll").addEventListener("click", function () {
      var files = state.grouped[state.activeCategory] || {};
      Object.keys(files).forEach(function (f) { state.expanded[state.activeCategory + "::" + f] = true; });
      renderTree();
    });
    $("btnCollapseAll").addEventListener("click", function () {
      var files = state.grouped[state.activeCategory] || {};
      Object.keys(files).forEach(function (f) { state.expanded[state.activeCategory + "::" + f] = false; });
      renderTree();
    });
    $("btnSelectCategory").addEventListener("click", function () {
      visibleTestsInCategory().forEach(function (t) { state.selection.add(t.nodeid); });
      updateSelectedCount(); savePrefs(); renderTree();
    });
    $("btnDeselectCategory").addEventListener("click", function () {
      visibleTestsInCategory().forEach(function (t) { state.selection.delete(t.nodeid); });
      updateSelectedCount(); savePrefs(); renderTree();
    });
    $("categoryToggle").addEventListener("change", function (e) {
      visibleTestsInCategory().forEach(function (t) {
        if (e.target.checked) state.selection.add(t.nodeid);
        else state.selection.delete(t.nodeid);
      });
      updateSelectedCount(); savePrefs(); renderTree();
    });

    ["browserSelect", "envSelect", "deviceInput", "workersSelect"].forEach(function (id) {
      $(id).addEventListener("change", function () { updateEnvInfo(); savePrefs(); });
    });
    document.querySelectorAll('input[name="headlessMode"]').forEach(function (r) {
      r.addEventListener("change", function () { updateEnvInfo(); savePrefs(); });
    });
    $("themeToggle").addEventListener("click", function () {
      var cur = document.documentElement.getAttribute("data-theme");
      document.documentElement.setAttribute("data-theme", cur === "dark" ? "light" : "dark");
      savePrefs();
    });

    $("btnRunSelected").addEventListener("click", function () { startRun("selected"); });
    $("btnRunAll").addEventListener("click", function () { startRun("all"); });
    $("btnRunSmoke").addEventListener("click", function () { startRun("smoke"); });
    $("btnRunRegression").addEventListener("click", function () { startRun("regression"); });
    function rerunFailed() {
      var o = currentOptions();
      message("Rerunning failed tests...", false);
      api("/api/rerun-failed", { method: "POST", body: JSON.stringify(o) }).then(function (data) {
        message("Rerunning " + data.reran.length + " failed test(s): " + data.command, false);
        setRunningUI(true); startPolling();
      }).catch(function (err) { message(err.message, true); });
    }
    $("btnRerunFailed").addEventListener("click", rerunFailed);
    $("btnRerunFailed2").addEventListener("click", rerunFailed);
    $("btnRerunAll").addEventListener("click", function () {
      var o = currentOptions();
      message("Rerunning previous execution...", false);
      api("/api/rerun-all", { method: "POST", body: JSON.stringify(o) }).then(function (data) {
        message("Rerunning " + data.reran_count + " test(s): " + data.command, false);
        setRunningUI(true); startPolling();
      }).catch(function (err) { message(err.message, true); });
    });
    $("btnStop").addEventListener("click", function () {
      if (!window.confirm("Stop the current execution? Already-finished results are preserved.")) return;
      api("/api/stop", { method: "POST" }).then(function (data) {
        message(data.message || "Stop requested.", false);
      }).catch(function (err) { message(err.message, true); });
    });
    $("btnRefreshTests").addEventListener("click", function () {
      message("Refreshing test discovery...", false);
      loadTests(true).then(function () { message("Test discovery refreshed.", false); });
    });
    $("btnClearSelection").addEventListener("click", function () {
      state.selection.clear();
      updateSelectedCount(); savePrefs(); renderTree();
    });
    $("btnCopyCommand").addEventListener("click", function () {
      var o = currentOptions();
      o.nodeids = Array.prototype.slice.call(state.selection);
      if (!o.nodeids.length) {
        message("No tests selected — generating the Run All command for these options.", false);
      }
      api("/api/command", { method: "POST", body: JSON.stringify(o) }).then(function (data) {
        copyText(data.command).then(function () {
          message("Copied: " + data.command, false);
        });
      }).catch(function (err) { message(err.message, true); });
    });
    $("btnCopyFailed").addEventListener("click", function () {
      var failed = ((state.lastResults || {}).results || [])
        .filter(function (r) { return r.status === "failed" || r.status === "error"; })
        .map(function (r) { return r.nodeid; });
      if (!failed.length) { message("No failed tests to copy.", true); return; }
      copyText(failed.join("\n")).then(function () {
        message("Copied " + failed.length + " failed test name(s).", false);
      });
    });
    $("btnAllure").addEventListener("click", function () {
      var btn = $("btnAllure");
      btn.disabled = true;
      message("Generating Allure report...", false);
      api("/api/allure/generate", { method: "POST" }).then(function (data) {
        message("Report ready (engine: " + data.engine + "). " + (data.message || "Opening..."), false);
        window.open(data.url || "/api/allure/", "_blank", "noopener");
      }).catch(function (err) {
        message(err.message, true);
      }).then(function () { btn.disabled = false; });
    });
    $("btnRefreshResults").addEventListener("click", function () { refreshResults(); });
    $("btnRefreshHistory").addEventListener("click", function () { loadHistory(); });
    $("btnLogs").addEventListener("click", openLogs);
    $("btnCloseLogs").addEventListener("click", function () { $("logsModal").classList.add("hidden"); });
    $("btnReloadLog").addEventListener("click", loadLogContent);
    $("btnCloseArt").addEventListener("click", function () { $("artModal").classList.add("hidden"); });
    [$("logsModal"), $("artModal")].forEach(function (modal) {
      modal.addEventListener("click", function (e) {
        if (e.target === modal) modal.classList.add("hidden");
      });
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        $("logsModal").classList.add("hidden");
        $("artModal").classList.add("hidden");
      }
    });
    $("btnClearResults").addEventListener("click", function () {
      if (!window.confirm("Clear generated screenshots, videos, traces, live files and Allure results? Execution history is preserved.")) return;
      api("/api/cleanup", { method: "POST", body: JSON.stringify({ action: "results" }) }).then(function (data) {
        message("Cleared " + data.removed + " generated artifact(s).", false);
      }).catch(function (err) { message(err.message, true); });
    });
    $("btnDlComplete").addEventListener("click", function () {
      message("Building complete framework ZIP...", false);
      window.location.href = "/api/download/complete";
      setTimeout(function () { message("Complete framework ZIP download started.", false); }, 1500);
    });
    $("btnDlNoExamples").addEventListener("click", function () {
      message("Building no-examples framework ZIP...", false);
      window.location.href = "/api/download/no-examples";
      setTimeout(function () { message("No-examples framework ZIP download started.", false); }, 1500);
    });
    $("docsSearch").addEventListener("input", searchDocs);
  }

  /* ---------------- boot ---------------- */
  document.addEventListener("DOMContentLoaded", function () {
    loadPrefs();
    wire();
    loadInfo().then(function () {
      updateEnvInfo();
      return loadTests(false);
    }).then(function () {
      refreshResults();
      loadHistory();
      pollStatus();
      setInterval(function () { if (!state.running) pollStatus(); }, 5000);
    }).catch(function (err) {
      message("Dashboard backend unreachable: " + err.message, true);
    });
  });
})();
