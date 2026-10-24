/* Generated from contracts/schema/contracts.json — do not edit. Run `pnpm types`. */

export type Count = number;
export type Hi = number;
export type Lo = number;
export type Observed = number;
export type Predicted = number;
export type Bins = CalibrationBin[];
export type Brier = number;
export type Ece = number;
export type Model = string;
export type Samples = number;
export type BallHeightM = number | null;
export type BallSpeedMs = number | null;
export type X = number;
export type Y = number;
export type EventId = string;
export type FrameRef = number;
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Outcome".
 */
export type Outcome = "success" | "fail";
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Period".
 */
export type Period = "1H" | "2H";
export type PlayerId = string | null;
export type Pressure = number | null;
export type TMs = number;
export type Tags = string[];
export type TargetId = string | null;
export type TeamId = string | null;
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "EventType".
 */
export type EventType =
  | "pass"
  | "cross"
  | "shot"
  | "dribble"
  | "tackle"
  | "interception"
  | "aerial_duel"
  | "clearance"
  | "foul"
  | "possession_change"
  | "pressure"
  | "substitution"
  | "goal"
  | "knock"
  | "period_start"
  | "period_end";
export type DangerousTurnovers = number;
export type Duels = number;
export type Goals = number;
export type HsrM = number;
export type Index = number;
export type Pressures = number;
export type Shots = number;
export type WindowEndMs = number;
export type WindowStartMs = number;
export type Xg = number;
export type EventId1 = string | null;
export type End = number;
export type Start = number;
export type Importance = number;
export type MomentId = string;
/**
 * @minItems 1
 */
export type Players = [string, ...string[]];
export type TMs1 = number;
export type TeamId1 = string | null;
export type Title = string;
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "MomentType".
 */
export type MomentType =
  "aerial_duel" | "recovery_run" | "big_chance" | "line_breaking_pass" | "press_turnover" | "goal" | "fatigue_alert";
export type MatchId = string;
export type PeriodLengthMs = number;
export type Length = number;
export type Width = number;
export type Seed = number;
export type Synthetic = boolean;
/**
 * @minItems 2
 * @maxItems 2
 */
export type Teams = [TeamMeta, TeamMeta];
export type Primary = string;
export type Secondary = string;
export type Formation = string;
export type IsHome = boolean;
export type Name = string;
export type ShortName = string;
export type TeamId2 = string;
export type TrackingHz = number;
export type Venue = string;
export type TMs2 = number;
/**
 * @minItems 2
 * @maxItems 2
 */
export type Teams1 = [TeamStats, TeamStats];
export type AvgPassDistanceM = number;
export type AvgPassSpeedMs = number;
export type DistanceKm = number;
export type Goals1 = number;
export type Interceptions = number;
export type MaxShotSpeedMs = number;
export type PassAccuracy = number;
export type Passes = number;
export type PassesCompleted = number;
export type Possession = number;
export type Shots1 = number;
export type ShotsOnTarget = number;
export type TacklesWon = number;
export type TeamId3 = string;
export type Xg1 = number;
export type ActorId = string;
export type BestOptionId = string;
export type MomentId1 = string;
/**
 * @minItems 1
 * @maxItems 4
 */
export type Options = [Option] | [Option, Option] | [Option, Option, Option] | [Option, Option, Option, Option];
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "ActionKind".
 */
export type ActionKind = "pass" | "cross" | "shot" | "dribble" | "carry" | "clear" | "header" | "recovery_run";
export type Chosen = boolean;
export type OptionId = string;
export type PSuccess = number;
/**
 * @minItems 2
 */
export type Path = [Point, Point, ...Point[]];
export type High = number;
export type Low = number;
export type Median = number;
export type TargetId1 = string | null;
export type XtGain = number;
export type TMs3 = number;
export type Grounded = boolean;
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "OverlayKind".
 */
export type OverlayKind = "moment" | "options" | "what_if" | "stat" | "fatigue" | "recap";
export type MomentId2 = string | null;
export type OverlayId = string;
export type ShowForMs = number;
export type Source = string;
export type TMs4 = number;
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Archetype".
 */
export type Archetype =
  | "goalkeeper"
  | "aerial_cb"
  | "ball_playing_cb"
  | "overlapping_fb"
  | "deep_playmaker"
  | "box_to_box"
  | "pressing_forward"
  | "target_man"
  | "winger";
export type Name1 = string;
export type AccelMs2 = number;
export type HeightCm = number;
export type JumpReachCm = number;
export type MaxSpeedMs = number;
export type ReactionS = number;
export type PlayerId1 = string;
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Position".
 */
export type Position = "GK" | "CB" | "FB" | "DM" | "CM" | "AM" | "W" | "ST";
export type ShirtNumber = number;
export type Aerial = number;
export type Finishing = number;
export type Passing = number;
export type Tackle = number;
export type Starter = boolean;
export type TeamId4 = string;
export type OwnerId = string | null;
export type X1 = number;
export type Y1 = number;
export type Z = number;
export type Frame = number;
export type Id = string;
export type Vx = number;
export type Vy = number;
export type X2 = number;
export type Y2 = number;
export type Players1 = PlayerTrack[];
export type TMs5 = number;
export type ActorId1 = string;
export type PSuccess1 = number;
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "ProfileKind".
 */
export type ProfileKind = "actual" | "archetype" | "custom" | "substitute";
export type Label = string;
export type PlayerId2 = string | null;
export type Delta = number;
export type Factor = string;
export type Text1 = string;
export type Unit = string;
export type Drivers = Driver[];
export type GhostPath = Point[];
export type MomentId3 = string;
export type DistanceM = number;
export type Fatigue = number;
export type HsrM1 = number;
export type Accel = number;
export type Reaction = number;
export type Speed = number;
export type PlayerId3 = string;
export type RecentLoad = number;
export type Sprints = number;
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "PhysicalStatus".
 */
export type PhysicalStatus = "fit" | "tiring" | "fatigued" | "knock";
export type TMs6 = number;
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Persona".
 */
export type Persona = "analyst" | "fan";

/**
 * Bundle model so one schema carries every record as a shared $def.
 */
export interface Contracts {
  calibration_report: CalibrationReport;
  event: Event;
  intensity_point: IntensityPoint;
  key_moment: KeyMoment;
  match_meta: MatchMeta;
  match_stats: MatchStats;
  option_set: OptionSet;
  overlay: Overlay;
  player_profile: PlayerProfile;
  tracking_frame: TrackingFrame;
  what_if: WhatIf;
  workload_state: WorkloadState;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "CalibrationReport".
 */
export interface CalibrationReport {
  bins: Bins;
  brier: Brier;
  ece: Ece;
  model: Model;
  samples: Samples;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "CalibrationBin".
 */
export interface CalibrationBin {
  count: Count;
  hi: Hi;
  lo: Lo;
  observed: Observed;
  predicted: Predicted;
}
/**
 * One on-ball or match action. `outcome` is always from `player_id`'s point of view.
 *
 * pass / cross: player = passer, target = intended receiver; `end` is the intended point even
 *     when the pass fails (the interception event says where it was won).
 * shot: outcome success = goal; first tag is goal | saved | wide.
 * interception: player = the one who won the ball.
 * tackle: player = tackler, target = ball carrier.
 * dribble: player = carrier, target = defender being beaten (or not).
 * aerial_duel: player = the defending-side player (the team that did not deliver the ball),
 *     target = the attacker; success = the defender won it.
 * pressure: player = presser, target = carrier, `pressure` 0-1 from their distance.
 * foul: player = offender, target = fouled player.
 * substitution: player = player coming on, target = player going off.
 * possession_change: team/player = who now has the ball.
 * Scripted ground truth carries the tags `scripted` and `scripted:<moment type>`.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Event".
 */
export interface Event {
  ball_height_m?: BallHeightM;
  ball_speed_ms?: BallSpeedMs;
  end?: Point | null;
  event_id: EventId;
  frame_ref: FrameRef;
  outcome?: Outcome | null;
  period: Period;
  player_id?: PlayerId;
  pressure?: Pressure;
  start?: Point | null;
  t_ms: TMs;
  tags?: Tags;
  target_id?: TargetId;
  team_id?: TeamId;
  type: EventType;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Point".
 */
export interface Point {
  x: X;
  y: Y;
}
/**
 * Match intensity for one 5-minute window (0-100, computable live; see engine.metrics).
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "IntensityPoint".
 */
export interface IntensityPoint {
  dangerous_turnovers: DangerousTurnovers;
  duels: Duels;
  goals: Goals;
  hsr_m: HsrM;
  index: Index;
  pressures: Pressures;
  shots: Shots;
  window_end_ms: WindowEndMs;
  window_start_ms: WindowStartMs;
  xg: Xg;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "KeyMoment".
 */
export interface KeyMoment {
  event_id?: EventId1;
  frame_range: FrameRange;
  importance?: Importance;
  moment_id: MomentId;
  players: Players;
  t_ms: TMs1;
  team_id?: TeamId1;
  title?: Title;
  type: MomentType;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "FrameRange".
 */
export interface FrameRange {
  end: End;
  start: Start;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "MatchMeta".
 */
export interface MatchMeta {
  match_id: MatchId;
  period_length_ms?: PeriodLengthMs;
  pitch?: PitchSize;
  seed: Seed;
  synthetic?: Synthetic;
  teams: Teams;
  tracking_hz?: TrackingHz;
  venue?: Venue;
}
export interface PitchSize {
  length?: Length;
  width?: Width;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "TeamMeta".
 */
export interface TeamMeta {
  colours: TeamColours;
  formation: Formation;
  is_home: IsHome;
  name: Name;
  short_name: ShortName;
  team_id: TeamId2;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "TeamColours".
 */
export interface TeamColours {
  primary: Primary;
  secondary: Secondary;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "MatchStats".
 */
export interface MatchStats {
  t_ms: TMs2;
  teams: Teams1;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "TeamStats".
 */
export interface TeamStats {
  avg_pass_distance_m: AvgPassDistanceM;
  avg_pass_speed_ms: AvgPassSpeedMs;
  distance_km: DistanceKm;
  goals: Goals1;
  interceptions: Interceptions;
  max_shot_speed_ms: MaxShotSpeedMs;
  pass_accuracy: PassAccuracy;
  passes: Passes;
  passes_completed: PassesCompleted;
  possession: Possession;
  shots: Shots1;
  shots_on_target: ShotsOnTarget;
  tackles_won: TacklesWon;
  team_id: TeamId3;
  xg: Xg1;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "OptionSet".
 */
export interface OptionSet {
  actor_id: ActorId;
  best_option_id: BestOptionId;
  moment_id: MomentId1;
  options: Options;
  t_ms: TMs3;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Option".
 */
export interface Option {
  action: ActionKind;
  chosen?: Chosen;
  option_id: OptionId;
  p_success: PSuccess;
  path: Path;
  range: ProbRange;
  target: Point;
  target_id?: TargetId1;
  xt_gain: XtGain;
}
/**
 * Monte Carlo spread: median with 10th-90th percentile.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "ProbRange".
 */
export interface ProbRange {
  high: High;
  low: Low;
  median: Median;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Overlay".
 */
export interface Overlay {
  grounded?: Grounded;
  kind: OverlayKind;
  moment_id?: MomentId2;
  overlay_id: OverlayId;
  payload?: Payload;
  show_for_ms?: ShowForMs;
  source?: Source;
  t_ms: TMs4;
  text?: Text;
}
export interface Payload {
  [k: string]: unknown;
}
export interface Text {
  [k: string]: {
    [k: string]: string;
  };
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "PlayerProfile".
 */
export interface PlayerProfile {
  archetype: Archetype;
  name: Name1;
  physical: Physical;
  player_id: PlayerId1;
  position: Position;
  shirt_number: ShirtNumber;
  skill: Skill;
  starter: Starter;
  team_id: TeamId4;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Physical".
 */
export interface Physical {
  accel_ms2: AccelMs2;
  height_cm: HeightCm;
  jump_reach_cm: JumpReachCm;
  max_speed_ms: MaxSpeedMs;
  reaction_s: ReactionS;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Skill".
 */
export interface Skill {
  aerial: Aerial;
  finishing: Finishing;
  passing: Passing;
  tackle: Tackle;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "TrackingFrame".
 */
export interface TrackingFrame {
  ball: BallState;
  frame: Frame;
  period: Period;
  players: Players1;
  t_ms: TMs5;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "BallState".
 */
export interface BallState {
  owner_id?: OwnerId;
  x: X1;
  y: Y1;
  z: Z;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "PlayerTrack".
 */
export interface PlayerTrack {
  id: Id;
  vx: Vx;
  vy: Vy;
  x: X2;
  y: Y2;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "WhatIf".
 */
export interface WhatIf {
  actor_id: ActorId1;
  actual: Scenario;
  counterfactual: Scenario;
  drivers: Drivers;
  ghost_path?: GhostPath;
  moment_id: MomentId3;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Scenario".
 */
export interface Scenario {
  p_success: PSuccess1;
  profile: ProfileRef;
  range: ProbRange;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "ProfileRef".
 */
export interface ProfileRef {
  archetype?: Archetype | null;
  kind: ProfileKind;
  label: Label;
  player_id?: PlayerId2;
}
/**
 * One reason the counterfactual differs, e.g. factor=jump_reach, delta=+12, unit=cm.
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Driver".
 */
export interface Driver {
  delta: Delta;
  factor: Factor;
  text: Text1;
  unit: Unit;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "WorkloadState".
 */
export interface WorkloadState {
  distance_m: DistanceM;
  fatigue: Fatigue;
  hsr_m: HsrM1;
  modifiers?: Modifiers;
  player_id: PlayerId3;
  recent_load: RecentLoad;
  sprints: Sprints;
  status: PhysicalStatus;
  t_ms: TMs6;
}
/**
 * Multipliers applied to a player's physical profile (1.0 = fresh).
 */
export interface Modifiers {
  accel?: Accel;
  reaction?: Reaction;
  speed?: Speed;
}
/**
 * Multipliers applied to a player's physical profile (1.0 = fresh).
 *
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "Modifiers".
 */
export interface Modifiers1 {
  accel?: Accel;
  reaction?: Reaction;
  speed?: Speed;
}
/**
 * This interface was referenced by `Contracts`'s JSON-Schema
 * via the `definition` "PitchSize".
 */
export interface PitchSize1 {
  length?: Length;
  width?: Width;
}
