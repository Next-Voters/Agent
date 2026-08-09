<script>
  let { statuses } = $props();

  function statusDetail(s) {
    if (s.status === "failed") {
      return s.error || (s.failures || []).join(", ") || "run failed";
    }
    if (s.status === "running" && s.started_at) {
      return `started ${new Date(s.started_at).toLocaleTimeString()}`;
    }
    return "waiting for worker";
  }
</script>

<div class="status-list">
  {#each statuses as s (s.region)}
    <div class="status-row">
      <span class="status {s.status}">{s.status}</span>
      <strong>{s.region}</strong>
      <span class="message detail">{statusDetail(s)}</span>
    </div>
  {/each}
</div>

<style>
  .status-list {
    margin-top: 0.75rem;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }

  .status-row {
    font-size: 0.9rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .detail {
    margin: 0;
  }
</style>
