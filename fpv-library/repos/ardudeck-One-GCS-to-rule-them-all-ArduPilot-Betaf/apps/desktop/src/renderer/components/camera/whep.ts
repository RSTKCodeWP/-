/**
 * Minimal WHEP client — plays a MediaMTX (or any WHEP) WebRTC stream into a
 * <video> element. recvonly; we POST our SDP offer and apply the answer.
 */

export async function playWhep(video: HTMLVideoElement, whepUrl: string): Promise<RTCPeerConnection> {
  const pc = new RTCPeerConnection({ iceServers: [] });
  pc.addTransceiver('video', { direction: 'recvonly' });
  pc.addTransceiver('audio', { direction: 'recvonly' });

  const stream = new MediaStream();
  pc.ontrack = (e) => {
    // Minimize the receiver's jitter buffer — the default targets a conservative
    // ~hundreds of ms, which is the bulk of the perceived delay on a clean link.
    // jitterBufferTarget is the modern API; playoutDelayHint is the fallback.
    const r = e.receiver as unknown as { jitterBufferTarget?: number | null; playoutDelayHint?: number };
    try { r.jitterBufferTarget = 0; } catch {/* unsupported */}
    try { r.playoutDelayHint = 0; } catch {/* unsupported */}
    stream.addTrack(e.track);
    video.srcObject = stream;
    void video.play().catch(() => {/* autoplay policy — user gesture will retry */});
  };

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  await waitForIce(pc);
  const sdp = pc.localDescription?.sdp ?? '';

  // The hub path can briefly not-exist or not-yet-be-publishing when we first
  // ask (source still connecting, or a dev StrictMode mount/unmount churn), so
  // a 404/425/503 is retried rather than treated as fatal.
  let res: Response | null = null;
  for (let attempt = 0; attempt < 10; attempt++) {
    res = await fetch(whepUrl, {
      method: 'POST',
      headers: { 'content-type': 'application/sdp' },
      body: sdp,
    });
    if (res.ok) break;
    if (res.status === 404 || res.status === 425 || res.status === 503) {
      await delay(500);
      continue;
    }
    break; // other statuses are real errors — don't spin
  }
  if (!res || !res.ok) {
    pc.close();
    throw new Error(`WHEP ${res?.status ?? 'no-response'} ${res?.statusText ?? ''}`.trim());
  }
  const answer = await res.text();
  await pc.setRemoteDescription({ type: 'answer', sdp: answer });
  return pc;
}

function delay(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

/** Resolve once ICE gathering completes (or after a short timeout). */
function waitForIce(pc: RTCPeerConnection): Promise<void> {
  if (pc.iceGatheringState === 'complete') return Promise.resolve();
  return new Promise((resolve) => {
    const done = () => {
      pc.removeEventListener('icegatheringstatechange', check);
      resolve();
    };
    const check = () => {
      if (pc.iceGatheringState === 'complete') done();
    };
    pc.addEventListener('icegatheringstatechange', check);
    // Trickle-free fallback: don't block forever on restrictive networks.
    setTimeout(done, 1500);
  });
}
