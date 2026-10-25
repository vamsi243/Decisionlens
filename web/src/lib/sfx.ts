import { usePrefs } from "@/state/prefs";

/**
 * Small tactile UI sounds, synthesised with the Web Audio API: no audio files, nothing to
 * download or license. Every sound is short and quiet (peak gain 0.02-0.06) and goes through
 * one master gain, so the mute toggle in the nav silences all of them.
 */

let ctx: AudioContext | null = null;
let master: GainNode | null = null;
let last = 0;

function audio(): { ac: AudioContext; out: GainNode } | null {
  if (!usePrefs.getState().sound || typeof window === "undefined") return null;
  try {
    if (!ctx) {
      const AC = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!AC) return null;
      ctx = new AC();
      master = ctx.createGain();
      master.gain.value = 0.8;
      master.connect(ctx.destination);
    }
    if (ctx.state === "suspended") void ctx.resume(); // browsers start it suspended until a gesture
    return { ac: ctx, out: master! };
  } catch {
    return null;
  }
}

/** One soft enveloped tone: quick attack, gentle exponential release. */
function tone(
  freq: number,
  { at = 0, dur = 0.08, gain = 0.04, type = "sine" as OscillatorType, to }: { at?: number; dur?: number; gain?: number; type?: OscillatorType; to?: number } = {},
) {
  const a = audio();
  if (!a) return;
  const t0 = a.ac.currentTime + at;
  const osc = a.ac.createOscillator();
  const env = a.ac.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, t0);
  if (to) osc.frequency.exponentialRampToValueAtTime(to, t0 + dur);
  env.gain.setValueAtTime(0.0001, t0);
  env.gain.exponentialRampToValueAtTime(gain, t0 + 0.008);
  env.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
  osc.connect(env).connect(a.out);
  osc.start(t0);
  osc.stop(t0 + dur + 0.02);
}

/** A short band-passed noise puff, for whooshes and ticks. */
function puff({ dur = 0.12, gain = 0.03, from = 900, to = 2400 }: { dur?: number; gain?: number; from?: number; to?: number } = {}) {
  const a = audio();
  if (!a) return;
  const t0 = a.ac.currentTime;
  const len = Math.ceil(a.ac.sampleRate * dur);
  const buf = a.ac.createBuffer(1, len, a.ac.sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < len; i++) data[i] = Math.random() * 2 - 1;
  const src = a.ac.createBufferSource();
  src.buffer = buf;
  const bp = a.ac.createBiquadFilter();
  bp.type = "bandpass";
  bp.Q.value = 1.2;
  bp.frequency.setValueAtTime(from, t0);
  bp.frequency.exponentialRampToValueAtTime(to, t0 + dur);
  const env = a.ac.createGain();
  env.gain.setValueAtTime(0.0001, t0);
  env.gain.exponentialRampToValueAtTime(gain, t0 + dur * 0.3);
  env.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
  src.connect(bp).connect(env).connect(a.out);
  src.start(t0);
}

/** Don't machine-gun: drop a sound that comes within `ms` of the previous one. */
function throttled(ms: number): boolean {
  const now = performance.now();
  if (now - last < ms) return true;
  last = now;
  return false;
}

export const sfx = {
  /** A button press: a soft, slightly falling blip. */
  tap: () => !throttled(40) && tone(620, { to: 520, dur: 0.06, gain: 0.035 }),
  /** Picking a player to follow: two rising notes. */
  select: () => {
    if (throttled(60)) return;
    tone(523.25, { dur: 0.09, gain: 0.04, type: "triangle" });
    tone(783.99, { at: 0.07, dur: 0.12, gain: 0.035, type: "triangle" });
  },
  /** Letting go of a player: the same notes, falling. */
  deselect: () => {
    if (throttled(60)) return;
    tone(783.99, { dur: 0.08, gain: 0.03, type: "triangle" });
    tone(523.25, { at: 0.06, dur: 0.1, gain: 0.025, type: "triangle" });
  },
  /** A panel sliding open, and closed. */
  open: () => !throttled(60) && puff({ dur: 0.14, gain: 0.025, from: 700, to: 2600 }),
  close: () => !throttled(60) && puff({ dur: 0.12, gain: 0.02, from: 2400, to: 700 }),
  /** A card passing by while scrolling the moments: a tiny wooden tick. */
  tick: () => !throttled(70) && tone(1320, { to: 980, dur: 0.025, gain: 0.018, type: "triangle" }),
  /** A switch (analyst/fan, follow-cam, sound). */
  toggle: () => !throttled(40) && tone(440, { to: 660, dur: 0.07, gain: 0.03, type: "triangle" }),
  /** A goal: a short, warm major arpeggio. */
  goal: () => {
    tone(523.25, { dur: 0.22, gain: 0.04 });
    tone(659.25, { at: 0.09, dur: 0.24, gain: 0.04 });
    tone(783.99, { at: 0.18, dur: 0.4, gain: 0.045 });
  },
  /** Any other big moment: one soft bell note. */
  moment: () => tone(880, { to: 870, dur: 0.35, gain: 0.03 }),
};

/** Sounds for preference changes, wherever they come from (board, cards, panel, chips, nav). */
export function watchPrefsForSound(): () => void {
  return usePrefs.subscribe((s, prev) => {
    if (s.player !== prev.player) (s.player ? sfx.select : sfx.deselect)();
    else if (s.follow !== prev.follow) (s.follow ? sfx.select : sfx.deselect)();
    else if (s.persona !== prev.persona || s.followCam !== prev.followCam) sfx.toggle();
    else if (s.sound && !prev.sound) sfx.toggle();
  });
}
