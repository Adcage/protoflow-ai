<template>
  <a-layout-footer class="global-footer">
    <div class="footer-content">
      <span class="copyright">&copy; 2026 AC AI Code Free</span>
      <a href="https://github.com/Adcage" target="_blank" rel="noopener noreferrer" class="github-link">
        <ExternalLink :size="18" />
      </a>
    </div>
  </a-layout-footer>
</template>

<script lang="ts" setup>
import { ExternalLink } from '@lucide/vue'
</script>

<style scoped>
.global-footer {
  background: var(--color-background);
  border-top: 1px solid var(--color-border);
  padding: var(--space-md) 0;
  margin-top: auto;
}

.footer-content {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-md);
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 var(--space-lg);
}

.copyright {
  color: var(--color-text-muted);
  font-size: 13px;
}

.github-link {
  display: flex;
  align-items: center;
  color: var(--color-text-muted);
  transition: color var(--transition-fast);
  cursor: pointer;
}

.github-link:hover {
  color: var(--color-text);
}
</style>
