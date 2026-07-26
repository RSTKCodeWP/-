<script lang="ts">
  import { addToast } from '../../lib/stores.svelte';
  import { t } from '../../lib/i18n.svelte';
  import { parseDFLog, getTimeSeries, computeFFT, type DFLog } from '../../lib/dflog';
  import Button from '$lib/components/ui/button/button.svelte';
  import { X, BarChart3 } from '@lucide/svelte';

  let { onclose }: { onclose: () => void } = $props();

  let log = $state<DFLog | null>(null);
  let source = $state('IMU.GyrX');
  let canvasEl: HTMLCanvasElement = $state(null!);
  let peakHz = $state(0);
  let logScale = $state(false);
  let rpmInput = $state('');
  let useHanning = $state(true);
  let useWelch = $state(true);

  // Notch recommendation: top 3 peaks
  let notchPeaks = $state<{ freq: number; mag: number; bw: number }[]>([]);

  const SOURCES = [
    { key: 'IMU.GyrX', label: 'fft.gyroX' },
    { key: 'IMU.GyrY', label: 'fft.gyroY' },
    { key: 'IMU.GyrZ', label: 'fft.gyroZ' },
    { key: 'IMU.AccX', label: 'fft.accelX' },
    { key: 'IMU.AccY', label: 'fft.accelY' },
    { key: 'IMU.AccZ', label: 'fft.accelZ' },
  ];

  function openFile() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.bin,.log';
    input.onchange = (e: Event) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev: ProgressEvent<FileReader>) => {
        try {
          log = parseDFLog(ev.target!.result as ArrayBuffer);
          addToast(`FFT: ${log.messages.length} messages`, 'success');
        } catch (err: unknown) {
          addToast('Parse error: ' + (err instanceof Error ? err.message : String(err)), 'error');
        }
      };
      reader.readAsArrayBuffer(file);
    };
    input.click();
  }

  /** Apply Hanning window: w[i] = 0.5 * (1 - cos(2*PI*i/N)) */
  function applyHanning(data: number[]): number[] {
    const N = data.length;
    const result = new Array(N);
    for (let i = 0; i < N; i++) {
      result[i] = data[i] * 0.5 * (1 - Math.cos((2 * Math.PI * i) / N));
    }
    return result;
  }

  /** Welch's method: split into 50%-overlapping segments, FFT each, average magnitudes */
  function welchFFT(values: number[], sampleRate: number, segmentSize: number): { freq: number[]; mag: number[] } {
    const step = segmentSize >> 1; // 50% overlap
    const segments: number[][] = [];
    for (let start = 0; start + segmentSize <= values.length; start += step) {
      let seg = values.slice(start, start + segmentSize);
      if (useHanning) seg = applyHanning(seg);
      segments.push(seg);
    }
    if (segments.length === 0) return { freq: [], mag: [] };

    // FFT each segment and collect magnitudes
    let avgFreq: number[] = [];
    let avgMag: number[] | null = null;
    for (const seg of segments) {
      const result = computeFFT(seg, sampleRate);
      if (result.freq.length === 0) continue;
      if (!avgMag) {
        avgFreq = result.freq;
        avgMag = result.mag.slice();
      } else {
        const len = Math.min(avgMag.length, result.mag.length);
        for (let i = 0; i < len; i++) {
          avgMag[i] += result.mag[i];
        }
      }
    }
    if (!avgMag) return { freq: [], mag: [] };
    // Average
    for (let i = 0; i < avgMag.length; i++) {
      avgMag[i] /= segments.length;
    }
    return { freq: avgFreq, mag: avgMag };
  }

  /** Detect top N peaks in the magnitude spectrum */
  function findPeaks(freq: number[], mag: number[], count: number): { freq: number; mag: number; bw: number }[] {
    if (mag.length < 3) return [];
    // Find all local maxima
    const peaks: { idx: number; val: number }[] = [];
    for (let i = 1; i < mag.length - 1; i++) {
      if (mag[i] > mag[i - 1] && mag[i] > mag[i + 1]) {
        peaks.push({ idx: i, val: mag[i] });
      }
    }
    peaks.sort((a, b) => b.val - a.val);
    const topPeaks = peaks.slice(0, count);

    return topPeaks.map((p) => {
      const peakFreq = freq[p.idx];
      // Estimate bandwidth at -3dB (half power)
      const threshold = p.val * 0.707;
      let lo = p.idx,
        hi = p.idx;
      while (lo > 0 && mag[lo] > threshold) lo--;
      while (hi < mag.length - 1 && mag[hi] > threshold) hi++;
      const bw = freq[hi] - freq[lo];
      return { freq: peakFreq, mag: p.val, bw: Math.max(bw, freq[1] - freq[0]) };
    });
  }

  $effect(() => {
    if (!canvasEl || !log) return;
    const [msgType, field] = source.split('.');
    const series = getTimeSeries(log, msgType, field);
    if (series.t.length < 64) return;

    const dt = series.t.length > 1 ? (series.t[series.t.length - 1] - series.t[0]) / (series.t.length - 1) : 0.001;
    const sampleRate = 1 / dt;

    // Compute FFT: either Welch's method or single-shot
    let freq: number[], mag: number[];
    if (useWelch) {
      // Use segment size = nearest power of 2 that gives ~8 segments
      const idealSeg = 1 << Math.floor(Math.log2(series.v.length / 4));
      const segSize = Math.max(64, Math.min(idealSeg, 1 << Math.floor(Math.log2(series.v.length))));
      const result = welchFFT(series.v, sampleRate, segSize);
      freq = result.freq;
      mag = result.mag;
    } else {
      let data = series.v;
      if (useHanning) data = applyHanning(data);
      const result = computeFFT(data, sampleRate);
      freq = result.freq;
      mag = result.mag;
    }
    if (freq.length === 0) return;

    // Find global peak
    let maxIdx = 0;
    for (let i = 1; i < mag.length; i++) {
      if (mag[i] > mag[maxIdx]) maxIdx = i;
    }
    peakHz = freq[maxIdx];

    // Find top 3 peaks for notch recommendation
    notchPeaks = findPeaks(freq, mag, 3);

    // Draw
    const ctx = canvasEl.getContext('2d')!;
    const w = (canvasEl.width = canvasEl.parentElement!.clientWidth);
    const h = canvasEl.height;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#0d1117';
    ctx.fillRect(0, 0, w, h);

    const maxFreqDisplay = Math.min(500, freq[freq.length - 1]);
    const maxMag = Math.max(...mag) || 1;

    // Vertical grid lines (frequency)
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 0.5;
    for (let f = 50; f <= maxFreqDisplay; f += 50) {
      const x = (f / maxFreqDisplay) * w;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
      ctx.fillStyle = '#555';
      ctx.font = '9px monospace';
      ctx.fillText(`${f}`, x + 2, h - 2);
    }

    // Horizontal grid lines (amplitude)
    ctx.strokeStyle = '#2a2a2a';
    for (let i = 1; i <= 4; i++) {
      let y: number;
      if (logScale) {
        const frac = i / 4;
        y = h - frac * (h - 20) - 10;
      } else {
        y = h - (i / 4) * (h - 20) - 10;
      }
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    // Y-axis labels
    ctx.fillStyle = '#555';
    ctx.font = '9px monospace';
    if (logScale) {
      const minLog = -2;
      const maxLog = Math.log10(maxMag);
      for (let i = 0; i <= 4; i++) {
        const logVal = minLog + (i / 4) * (maxLog - minLog);
        const y = h - (i / 4) * (h - 20) - 10;
        ctx.fillText(`${Math.pow(10, logVal).toPrecision(2)}`, 2, y - 2);
      }
    } else {
      for (let i = 0; i <= 4; i++) {
        const val = (i / 4) * maxMag;
        const y = h - (i / 4) * (h - 20) - 10;
        ctx.fillText(`${val.toPrecision(2)}`, 2, y - 2);
      }
    }

    // RPM harmonic markers
    const baseRpm = parseFloat(rpmInput);
    if (baseRpm > 0) {
      const baseHz = baseRpm / 60;
      const harmonicColors = ['#ff9800', '#ff5722', '#9c27b0', '#3f51b5'];
      for (let n = 1; n <= 4; n++) {
        const hFreq = baseHz * n;
        if (hFreq > maxFreqDisplay) break;
        const x = (hFreq / maxFreqDisplay) * w;
        ctx.strokeStyle = harmonicColors[n - 1];
        ctx.lineWidth = 1;
        ctx.setLineDash([6, 3]);
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = harmonicColors[n - 1];
        ctx.font = 'bold 9px monospace';
        ctx.fillText(`${n}x ${hFreq.toFixed(0)}Hz`, x + 3, h - 14 - n * 12);
      }
    }

    // Main FFT line
    ctx.strokeStyle = '#4fc3f7';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let i = 0; i < freq.length && freq[i] <= maxFreqDisplay; i++) {
      const x = (freq[i] / maxFreqDisplay) * w;
      let y: number;
      if (logScale) {
        const logVal = mag[i] > 0 ? Math.log10(mag[i]) : -6;
        const logMax = Math.log10(maxMag);
        const logMin = -2;
        const frac = (logVal - logMin) / (logMax - logMin);
        y = h - Math.max(0, Math.min(1, frac)) * (h - 20) - 10;
      } else {
        y = h - (mag[i] / maxMag) * (h - 20) - 10;
      }
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Peak marker
    const peakX = (peakHz / maxFreqDisplay) * w;
    ctx.strokeStyle = '#f44336';
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(peakX, 0);
    ctx.lineTo(peakX, h);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = '#f44336';
    ctx.font = 'bold 11px monospace';
    ctx.fillText(`${peakHz.toFixed(1)}Hz`, peakX + 4, 14);

    // Mark notch peaks (2nd and 3rd) with smaller markers
    for (let i = 1; i < notchPeaks.length; i++) {
      const np = notchPeaks[i];
      if (np.freq > maxFreqDisplay) continue;
      const nx = (np.freq / maxFreqDisplay) * w;
      ctx.strokeStyle = '#ffb74d';
      ctx.lineWidth = 0.8;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(nx, 0);
      ctx.lineTo(nx, h);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = '#ffb74d';
      ctx.font = '9px monospace';
      ctx.fillText(`${np.freq.toFixed(1)}Hz`, nx + 3, 14 + i * 14);
    }
  });
</script>

<div
  role="dialog"
  aria-modal="true"
  tabindex="-1"
  class="fixed inset-0 bg-black/60 backdrop-blur-sm z-[9999] flex items-center justify-center"
  onclick={onclose}
  onkeydown={(e) => {
    if (e.key === 'Escape') onclose();
  }}
>
  <div
    class="bg-card border border-border rounded-2xl overflow-hidden w-[750px] max-h-[85vh] shadow-2xl flex flex-col"
    role="presentation"
    onclick={(e) => e.stopPropagation()}
    onkeydown={(e) => e.stopPropagation()}
  >
    <div class="bg-gradient-to-r from-primary/20 to-primary/5 px-5 py-3 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-2">
        <BarChart3 size={16} class="text-primary" />
        <h3 class="text-base font-bold text-primary">{t('fft.title')}</h3>
      </div>
      <div class="flex items-center gap-2">
        <Button variant="default" size="sm" onclick={openFile}>{t('logview.open')}</Button>
        <Button variant="ghost" size="icon-xs" onclick={onclose} aria-label={t('error.close')}><X size={16} /></Button>
      </div>
    </div>

    <div class="px-5 py-3 flex-1 overflow-auto">
      {#if !log}
        <div class="text-center py-16 text-muted-foreground text-sm">{t('fft.noData')}</div>
      {:else}
        <!-- Source selector -->
        <div class="flex items-center gap-2 mb-3">
          <span class="text-xs font-semibold text-muted-foreground">{t('fft.source')}:</span>
          {#each SOURCES as src}
            <button
              class="px-2 py-0.5 text-[10px] rounded border cursor-pointer transition-all
              {source === src.key
                ? 'bg-primary text-primary-foreground border-primary'
                : 'text-muted-foreground border-border hover:text-foreground'}"
              onclick={() => (source = src.key)}>{t(src.label)}</button
            >
          {/each}
        </div>

        <!-- Controls row: toggles + RPM input -->
        <div class="flex items-center gap-3 mb-3 flex-wrap">
          <button
            class="px-2 py-0.5 text-[10px] rounded border cursor-pointer transition-all
            {useHanning
              ? 'bg-primary text-primary-foreground border-primary'
              : 'text-muted-foreground border-border hover:text-foreground'}"
            onclick={() => (useHanning = !useHanning)}>{t('fft.hanning')}</button
          >
          <button
            class="px-2 py-0.5 text-[10px] rounded border cursor-pointer transition-all
            {useWelch
              ? 'bg-primary text-primary-foreground border-primary'
              : 'text-muted-foreground border-border hover:text-foreground'}"
            onclick={() => (useWelch = !useWelch)}>{t('fft.welch')}</button
          >
          <button
            class="px-2 py-0.5 text-[10px] rounded border cursor-pointer transition-all
            {logScale
              ? 'bg-primary text-primary-foreground border-primary'
              : 'text-muted-foreground border-border hover:text-foreground'}"
            onclick={() => (logScale = !logScale)}>{t('fft.logScale')}</button
          >
          <span class="text-[10px] text-muted-foreground ml-2">{t('fft.rpmBase')}:</span>
          <input
            type="text"
            class="w-16 px-1.5 py-0.5 text-[10px] bg-background border border-border rounded font-mono text-foreground"
            placeholder={t('fft.rpmPlaceholder')}
            bind:value={rpmInput}
          />
        </div>

        <div class="border border-border rounded-lg overflow-hidden">
          <canvas bind:this={canvasEl} height="280" class="w-full"></canvas>
        </div>

        <!-- Notch filter recommendation panel -->
        {#if notchPeaks.length > 0}
          <div class="mt-3 p-3 bg-warning/10 border border-warning/30 rounded-lg">
            <p class="text-xs font-bold text-warning mb-2">{t('fft.notchRecommend')}</p>
            <div class="space-y-1.5">
              {#each notchPeaks as peak, i}
                <div class="flex items-center gap-3 text-[10px]">
                  <span class="text-muted-foreground font-semibold w-14"
                    >{t('fft.peakN').replace('{n}', String(i + 1))}</span
                  >
                  <span class="font-mono text-foreground">{peak.freq.toFixed(1)} Hz</span>
                  <span class="text-muted-foreground">{t('fft.notchBw')}:</span>
                  <span class="font-mono text-foreground">{peak.bw.toFixed(1)} Hz</span>
                </div>
              {/each}
            </div>
            {#if notchPeaks.length > 0}
              <div class="mt-2 pt-2 border-t border-warning/20">
                <p class="text-[10px] font-semibold text-muted-foreground mb-1">{t('fft.notchParam')}:</p>
                <div class="grid grid-cols-2 gap-x-4 gap-y-0.5 text-[10px] font-mono">
                  <span class="text-muted-foreground">INS_HNTCH_ENABLE</span><span class="text-foreground">1</span>
                  <span class="text-muted-foreground">INS_HNTCH_FREQ</span><span class="text-foreground"
                    >{notchPeaks[0].freq.toFixed(0)}</span
                  >
                  <span class="text-muted-foreground">INS_HNTCH_BW</span><span class="text-foreground"
                    >{notchPeaks[0].bw.toFixed(0)}</span
                  >
                  <span class="text-muted-foreground">INS_HNTCH_MODE</span><span class="text-foreground">0</span>
                  {#if notchPeaks.length > 1}
                    <span class="text-muted-foreground">INS_HNTC2_ENABLE</span><span class="text-foreground">1</span>
                    <span class="text-muted-foreground">INS_HNTC2_FREQ</span><span class="text-foreground"
                      >{notchPeaks[1].freq.toFixed(0)}</span
                    >
                    <span class="text-muted-foreground">INS_HNTC2_BW</span><span class="text-foreground"
                      >{notchPeaks[1].bw.toFixed(0)}</span
                    >
                  {/if}
                </div>
              </div>
            {/if}
          </div>
        {/if}
      {/if}
    </div>
  </div>
</div>
