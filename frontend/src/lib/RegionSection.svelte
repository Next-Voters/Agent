<script>
  import ReportDetail from "./ReportDetail.svelte";

  let {
    region,
    reports,
    activeReportId,
    activeReport,
    detailError,
    onselect,
    ondelete,
  } = $props();

  const showsDetail = $derived(reports.some((r) => r.id === activeReportId));
</script>

<section class="card">
  <h2 class="region-title">
    {region}
    <span class="count">
      {reports.length} report{reports.length === 1 ? "" : "s"}
    </span>
  </h2>

  {#each reports as report (report.id)}
    <div
      class="report-row"
      class:selected={report.id === activeReportId}
      role="button"
      tabindex="0"
      onclick={() => onselect(report.id)}
      onkeydown={(e) => e.key === "Enter" && onselect(report.id)}
    >
      <span class="date">{report.report_date}</span>
      <span class="rid">Report #{report.id}</span>
      <button
        class="delete-btn"
        title="Delete report"
        onclick={(e) => {
          e.stopPropagation();
          ondelete(report.id);
        }}
      >
        Delete
      </button>
    </div>
  {/each}

  {#if showsDetail}
    <div class="detail">
      {#if detailError}
        <div class="error-box">{detailError}</div>
      {:else if !activeReport}
        <p class="empty">Loading report…</p>
      {:else}
        <ReportDetail report={activeReport} />
      {/if}
    </div>
  {/if}
</section>

<style>
  .region-title {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
  }

  .count {
    color: var(--muted);
    font-size: 0.85rem;
    font-weight: 400;
  }

  .report-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.5rem 0.6rem;
    border-radius: 8px;
    cursor: pointer;
    border: 1px solid transparent;
    font-size: 0.92rem;
  }

  .report-row:hover {
    background: var(--bg);
  }

  .report-row.selected {
    background: #eff6ff;
    border-color: #bfdbfe;
  }

  .date {
    font-weight: 600;
  }

  .rid {
    color: var(--muted);
    font-size: 0.82rem;
    margin-left: auto;
  }

  .delete-btn {
    font-size: 0.78rem;
    padding: 0.25rem 0.55rem;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: transparent;
    color: #b91c1c;
    cursor: pointer;
  }

  .delete-btn:hover {
    background: #fee2e2;
    border-color: #fca5a5;
  }

  .detail {
    border-top: 1px solid var(--border);
    margin-top: 0.75rem;
    padding-top: 1rem;
  }
</style>
