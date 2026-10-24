import type {
  Event,
  Hello,
  IntensityPoint,
  KeyMoment,
  MatchStats,
  MomentAnalysis,
  ReplayStatus,
  TrackingFrame,
  WorkloadState,
} from "@/types/contracts";
import { useMatch } from "@/state/match";
import { api, WS_URL } from "./api";

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
  | { type: "overlay"; data: unknown };

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
    default:
      return undefined;
  }
}

/** Connect to the stream and keep reconnecting with backoff. Returns a disconnect function. */
export function connectStream(): () => void {
  let ws: WebSocket | null = null;
  let closed = false;
  let retry = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;

  const open = () => {
    ws = new WebSocket(WS_URL);
    ws.onopen = () => {
      retry = 0;
      useMatch.getState().setConnected(true);
      api.moments(true).then(useMatch.getState().setAllMoments).catch(() => undefined);
      api.intensity().then(useMatch.getState().setIntensity).catch(() => undefined);
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
