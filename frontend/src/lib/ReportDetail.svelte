<script>
  let { report } = $props();

  const topicEntries = $derived(Object.entries(report.topics || {}));
</script>

{#if !topicEntries.length}
  <p class="empty">This report has no items.</p>
{/if}

{#each topicEntries as [topic, items] (topic)}
  <div class="topic">
    <h3>{topic}</h3>
    {#each items as item, i (i)}
      <div class="item">
        <h4>{item.header}</h4>
        <ul>
          {#each item.bullets as bullet, j (j)}
            <li>{bullet}</li>
          {/each}
        </ul>
        {#if item.sources.length}
          <div class="sources">
            {#each item.sources as url (url)}
              <div><a href={url} target="_blank" rel="noopener">{url}</a></div>
            {/each}
          </div>
        {/if}
      </div>
    {/each}
  </div>
{/each}

<style>
  .topic {
    margin-bottom: 1.5rem;
  }

  .topic h3 {
    font-size: 1rem;
    margin: 0 0 0.6rem;
    text-transform: capitalize;
  }

  .item {
    border-left: 3px solid var(--accent);
    padding: 0.2rem 0 0.2rem 0.75rem;
    margin-bottom: 0.9rem;
  }

  .item h4 {
    margin: 0 0 0.3rem;
    font-size: 0.95rem;
  }

  .item ul {
    margin: 0;
    padding-left: 1.1rem;
    font-size: 0.9rem;
  }

  .sources {
    font-size: 0.85rem;
    margin-top: 0.5rem;
  }

  .sources a {
    color: var(--accent);
    word-break: break-all;
  }
</style>
