import type {
  Event,
  Hello,
  IntensityPoint,
  KeyMoment,
  MatchStats,
  MomentAnalysis,
  Overlay,
  ReplayStatus,
  TrackingFrame,
  WorkloadState,
} from "@/types/contracts";
import { useMatch } from "@/state/match";
import { HubConnectionBuilder, LogLevel } from "@microsoft/signalr";
import { api, wsUrl } from "./api";

type Message =
  | { type: "hello"; data: Hello }
  | { type: "frame"; data: TrackingFrame }
  | { type: "event"; data: Event }
  | { type: "stats"; data: MatchStats }
  | { type: "workload"; data: WorkloadState[] }
  | { type: "intensity"; data: IntensityPoint[] }
  | { type: "moment"; data: KeyMoment }
  | { type: "analysis"; data: MomentAnalysis }
  | { type: "status"; data: ReplayStatus }
  | { type: "overlay"; data: Overlay };

function dispatch(msg: Message) {
  const s = useMatch.getState();
  switch (msg.type) {
    case "frame":
      return s.frame(msg.data);
    case "hello":
      return s.hello(msg.data);
    case "event":
      return s.event(msg.data);
    case "stats":
      return s.setStats(msg.data);
    case "workload":
      return s.setWorkload(msg.data);
    case "intensity":
      return s.setIntensity(msg.data);
    case "moment":
      return s.moment(msg.data);
    case "analysis":
      return s.analysis(msg.data);
    case "status":
      return s.setStatus(msg.data);
    case "overlay":
      return s.overlay(msg.data);
    default:
      return undefined;
  }
}

let signalr: ReturnType<HubConnectionBuilder["build"]> | null = null;

/**
 * Azure: the low-rate messages (moments, analyses, cards, status) arrive over Azure SignalR
 * Service; frames stay on the service WebSocket. The token comes from our /negotiate endpoint.
 */
async function connectSignalR() {
  if (signalr) return;
  try {
    const first = await api.negotiate();
    signalr = new HubConnectionBuilder()
      .withUrl(first.url, { accessTokenFactory: async () => (await api.negotiate()).accessToken })
      .withAutomaticReconnect()
      .configureLogging(LogLevel.Warning)
      .build();
    signalr.on("message", (raw: string) => {
      try {
        dispatch(JSON.parse(raw) as Message);
      } catch {
        /* ignore malformed */
      }
    });
    await signalr.start();
  } catch {
    signalr = null; // REST fetches still fill moments and cards
  }
}

/** Connect to the stream and keep reconnecting with backoff. Returns a disconnect function. */
export function connectStream(): () => void {
  let ws: WebSocket | null = null;
  let closed = false;
  let retry = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;

  const open = () => {
    ws = new WebSocket(wsUrl());
    ws.onopen = () => {
      retry = 0;
      useMatch.getState().setConnected(true);
      api
        .config()
        .then((cfg) => {
          useMatch.getState().setServer(cfg);
          if (cfg.signalr) void connectSignalR();
        })
        .catch(() => undefined);
      api.moments(true).then(useMatch.getState().setAllMoments).catch(() => undefined);
      api.intensity().then(useMatch.getState().setIntensity).catch(() => undefined);
      api
        .overlays(true)
        .then((os) => os.forEach(useMatch.getState().overlay))
        .catch(() => undefined);
    };
    ws.onmessage = (ev) => {
      try {
        dispatch(JSON.parse(ev.data as string) as Message);
      } catch {
        /* a malformed message should never take the board down */
      }
    };
    ws.onclose = () => {
      useMatch.getState().setConnected(false);
      if (!closed) timer = setTimeout(open, Math.min(8000, 500 * 2 ** retry++));
    };
  };

  open();
  return () => {
    closed = true;
    clearTimeout(timer);
    ws?.close();
  };
}
