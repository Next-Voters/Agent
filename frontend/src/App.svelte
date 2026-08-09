<script>
  import { onMount } from "svelte";

  import RegionSection from "./lib/RegionSection.svelte";
  import StatusStrip from "./lib/StatusStrip.svelte";

  let regionsByType = $state({});
  let selectedByType = $state({});
  let starting = $state(false);
  let message = $state("");
  let messageIsError = $state(false);
  let statuses = $state([]);
  let reports = $state([]);
  let reportsError = $state("");
  let activeReportId = $state(null);
  let activeReport = $state(null);
  let detailError = $state("");

  // Only one region can be picked at a time, but each type gets its own
  // dropdown — picking in one clears any selection in the others.
  const selectedRegion = $derived(
    Object.values(selectedByType).find((value) => value) ?? "",
  );

  function selectFromType(type, value) {
    selectedByType = { [type]: value };
  }

  // Once a type has a region picked, the other types' dropdowns lock until
  // that selection is cleared back to its placeholder.
  function isLockedOut(type) {
    return Object.entries(selectedByType).some(([t, value]) => t !== type && value);
  }

  // Reports segregated into one section per city, newest first inside each.
  const regionSections = $derived.by(() => {
    const byRegion = new Map();
    for (const report of reports) {
      if (!byRegion.has(report.region)) byRegion.set(report.region, []);
      byRegion.get(report.region).push(report);
    }
    return [...byRegion.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([region, regionReports]) => ({ region, reports: regionReports }));
  });

  async function loadRegions() {
    try {
      const res = await fetch("/api/regions");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      regionsByType = (await res.json()).regions;
    } catch (err) {
      message = `Failed to load regions: ${err.message}`;
      messageIsError = true;
    }
  }

  async function startRun() {
    starting = true;
    message = "";
    messageIsError = false;
    try {
      const res = await fetch("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ region: selectedRegion }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      message = `Run started for ${selectedRegion}. The report appears below when it finishes.`;
      await refreshStatuses();
    } catch (err) {
      message = err.message;
      messageIsError = true;
    } finally {
      starting = false;
    }
  }

  async function refreshStatuses() {
    try {
      const res = await fetch("/api/runs");
      if (!res.ok) return;
      statuses = (await res.json()).runs;
    } catch {
      /* transient network error — retry on next poll */
    }
  }

  async function refreshReports() {
    try {
      const res = await fetch("/api/reports");
      if (!res.ok) {
        reportsError = "Failed to load reports from the database.";
        return;
      }
      reports = (await res.json()).reports;
      reportsError = "";
    } catch {
      /* transient network error — retry on next poll */
    }
  }

  async function deleteReport(reportId) {
    if (!confirm("Delete this report? This cannot be undone.")) return;
    try {
      const res = await fetch(`/api/reports/${reportId}`, { method: "DELETE" });
      if (!res.ok && res.status !== 404) throw new Error(`HTTP ${res.status}`);
      reports = reports.filter((r) => r.id !== reportId);
      if (activeReportId === reportId) {
        activeReportId = null;
        activeReport = null;
      }
    } catch (err) {
      reportsError = `Failed to delete report: ${err.message}`;
    }
  }

  async function selectReport(reportId) {
    if (activeReportId === reportId) {
      activeReportId = null;
      activeReport = null;
      return;
    }
    activeReportId = reportId;
    activeReport = null;
    detailError = "";
    try {
      const res = await fetch(`/api/reports/${reportId}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const report = await res.json();
      if (activeReportId === reportId) activeReport = report;
    } catch {
      detailError = "Failed to load this report.";
    }
  }

  onMount(() => {
    loadRegions();
    refreshReports();
    refreshStatuses();
    const timer = setInterval(() => {
      refreshReports();
      refreshStatuses();
    }, 5000);
    return () => clearInterval(timer);
  });
</script>

<main>
  <h1>Next Voters Agent</h1>
  <p class="subtitle">
    Research municipal legislation for a region and browse the saved reports.
  </p>

  <section class="card">
    <h2>Start a run</h2>
    <div class="run-form">
      {#if !Object.keys(regionsByType).length}
        <select disabled>
          <option value="">Loading regions…</option>
        </select>
      {/if}
      {#each Object.entries(regionsByType) as [type, typeRegions] (type)}
        <select
          value={selectedByType[type] ?? ""}
          disabled={isLockedOut(type)}
          onchange={(e) => selectFromType(type, e.currentTarget.value)}
        >
          <option value="">Select a {type}…</option>
          {#each typeRegions as region (region)}
            <option value={region}>{region}</option>
          {/each}
        </select>
      {/each}
      <button onclick={startRun} disabled={!selectedRegion || starting}>
        Run pipeline
      </button>
    </div>
    <p class="message" class:error={messageIsError}>{message}</p>
    <StatusStrip {statuses} />
  </section>

  {#if reportsError}
    <div class="error-box">{reportsError}</div>
  {:else if !regionSections.length}
    <p class="empty">No reports yet. Run the pipeline for a region to create one.</p>
  {/if}

  {#each regionSections as section (section.region)}
    <RegionSection
      region={section.region}
      reports={section.reports}
      {activeReportId}
      {activeReport}
      {detailError}
      onselect={selectReport}
      ondelete={deleteReport}
    />
  {/each}
</main>

<style>
  .subtitle {
    color: var(--muted);
    margin: 0 0 1.5rem;
    font-size: 0.95rem;
  }

  .run-form {
    display: flex;
    gap: 0.6rem;
    flex-wrap: wrap;
    align-items: center;
  }
</style>
