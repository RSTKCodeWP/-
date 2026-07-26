<script lang="ts">
  import { t } from '../../lib/i18n.svelte';
  import { apiUrl } from '../../lib/backend';
  import Button from '$lib/components/ui/button/button.svelte';
  import { Lock } from '@lucide/svelte';

  interface Props {
    onlogin: () => void;
  }
  let { onlogin }: Props = $props();

  let token = $state('');
  let error = $state('');
  let loading = $state(false);
  let inputEl: HTMLInputElement | undefined = $state();

  $effect(() => {
    inputEl?.focus();
  });

  async function submit() {
    if (!token.trim() || loading) return;
    loading = true;
    error = '';
    try {
      const res = await fetch(apiUrl('/api/auth/login'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token.trim() }),
      });
      const data = await res.json();
      if (data.ok) {
        localStorage.setItem('argus_auth_token', token.trim());
        onlogin();
      } else {
        error = t('auth.error');
      }
    } catch {
      error = t('auth.connFailed');
    } finally {
      loading = false;
    }
  }

  function onKey(e: KeyboardEvent) {
    if (e.key === 'Enter') submit();
  }
</script>

<div class="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm">
  <div
    class="bg-card border border-border rounded-xl shadow-2xl p-6 w-[360px] max-w-[90vw]"
    role="dialog"
    aria-modal="true"
    aria-labelledby="auth-title"
    tabindex="-1"
  >
    <div class="flex items-center gap-3 mb-4">
      <div class="shrink-0 w-10 h-10 rounded-full bg-primary/15 flex items-center justify-center">
        <Lock size={20} class="text-primary" />
      </div>
      <div>
        <h2 id="auth-title" class="text-sm font-bold text-foreground">{t('auth.title')}</h2>
        <p class="text-xs text-muted-foreground">{t('app.name')}</p>
      </div>
    </div>
    <label for="auth-token-input" class="block text-xs font-medium text-muted-foreground mb-1.5"
      >{t('auth.tokenLabel')}</label
    >
    <input
      id="auth-token-input"
      bind:this={inputEl}
      bind:value={token}
      type="password"
      placeholder={t('auth.tokenPlaceholder')}
      class="w-full px-3 py-2 text-sm bg-background border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/50"
      onkeydown={onKey}
      disabled={loading}
    />
    {#if error}
      <p class="text-xs text-destructive mt-2">{error}</p>
    {/if}
    <Button class="w-full mt-4" size="sm" onclick={submit} disabled={loading || !token.trim()}>
      {loading ? '...' : t('auth.login')}
    </Button>
  </div>
</div>
