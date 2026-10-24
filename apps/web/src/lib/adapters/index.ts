import { fixtureEvents } from "../fixtures";
import { SCENARIOS } from "../demo/scenarios";
import { LocalSimulator } from "../demo/simulator";
import type { PlanPreview, PlanningIntent, ScenarioDef, WindowPreset } from "../demo/types";
import { ReplayController } from "../replay/controller";
import { HttpJudgeAdapter, JudgeAdapter } from "./judge";
import { ConnectionStatus, connectSse, normalizeBaseUrl } from "./sse";

export interface AdapterHandlers {
  onEvent: (raw: unknown) => void;
  onReset: () => void;
  onStatus: (s: ConnectionStatus) => void;
  onMalformed: () => void;
}

export interface AdapterAction {
  id: string;
  label: string;
  hint: string;
  run: () => void;
}

/**
 * Everything MissionControl needs from a data source. `connect` wires the source to the
 * reducer; no adapter writes UI state itself.
 */
export interface JudgeOptions {
  members: readonly string[];
  windows: Pick<WindowPreset, "id" | "label">[];
}

export interface MissionAdapter {
  readonly kind: "fixture" | "demo" | "network";
  readonly label: string;
  readonly description: string;
  readonly sessionId: string;
  /** Present for replayable sources (fixture/demo). Live streams are push-only. */
  readonly replay: ReplayController | null;
  /** Null means judge intervention is unavailable for this source. */
  readonly judge: JudgeAdapter | null;
  readonly actions: AdapterAction[];
  /** Planning intent (activity, horizon, options). Only scenario-backed sources know it. */
  readonly intent: PlanningIntent | null;
  /** Public sanitized itinerary previews by version; empty when the stream does not supply them. */
  previews(): Record<number, PlanPreview>;
  readonly judgeOptions: JudgeOptions;
  /** The stream carries synthetic data only because we generated it locally. */
  readonly localSynthetic: boolean;
  connect(h: AdapterHandlers): () => void;
}

export const FIXTURE_SESSION = "session_trip_001";

/** Canonical agent_events.json replayed as-is. Read-only; no judge. */
export class FixtureAdapter implements MissionAdapter {
  readonly kind = "fixture" as const;
  readonly label = "Fixture replay";
  readonly description = "Replays docs/implementation/fixtures/agent_events.json unchanged. Recorded synthetic events, no live backend.";
  readonly sessionId = FIXTURE_SESSION;
  readonly judge = null;
  readonly actions: AdapterAction[] = [];
  readonly intent = null;
  readonly judgeOptions: JudgeOptions = { members: [], windows: [] };
  previews() { return {}; }
  readonly localSynthetic = true;
  readonly replay: ReplayController;
  private h: AdapterHandlers | null = null;
  constructor() {
    this.replay = new ReplayController({
      events: fixtureEvents,
      onEvent: (e) => this.h?.onEvent(e),
      onReset: () => this.h?.onReset(),
    });
  }
  connect(h: AdapterHandlers) {
    this.h = h;
    h.onStatus("open");
    return () => {
      this.replay.dispose();
      this.h = null;
    };
  }
}

/** Explicit demo mode: scripted four-agent scenario plus a labeled local simulator for judge requests. */
export class DemoAdapter implements MissionAdapter {
  readonly kind = "demo" as const;
  readonly label: string;
  readonly description = "Scripted four-agent scenario. Events and the judge response come from a local simulator, not the negotiation engine.";
  readonly sessionId: string;
  readonly intent: PlanningIntent;
  readonly judgeOptions: JudgeOptions;
  readonly localSynthetic = true;
  readonly replay: ReplayController;
  readonly judge: LocalSimulator;
  readonly actions: AdapterAction[];
  private h: AdapterHandlers | null = null;
  constructor(readonly def: ScenarioDef = SCENARIOS.quick) {
    this.label = `${def.label} (synthetic demo)`;
    this.sessionId = def.session;
    this.intent = def.intent;
    this.judgeOptions = { members: def.members, windows: def.windows };
    this.replay = new ReplayController({
      events: def.baseEvents,
      holds: { [def.baseEvents.length]: def.holdMessage },
      onEvent: (e) => this.h?.onEvent(e),
      onReset: () => {
        this.judge.resetState();
        this.h?.onReset();
      },
    });
    this.judge = new LocalSimulator(def, () => this.replay);
    this.actions = [
      {
        id: "remaining-accept",
        label: "Let remaining members accept",
        hint: "Scripted: appends acceptances then a confirmation, for showing the confirmed state.",
        run: () => this.judge.remainingMembersAccept(),
      },
    ];
  }
  previews() { return this.judge.previews; }
  connect(h: AdapterHandlers) {
    this.h = h;
    h.onStatus("open");
    return () => {
      this.replay.dispose();
      this.h = null;
    };
  }
}

/** Read-only SSE bridge to the realtime service / integrated backend. */
export class NetworkAdapter implements MissionAdapter {
  readonly kind = "network" as const;
  readonly label = "Live stream (SSE)";
  readonly description: string;
  readonly replay = null;
  readonly judge: JudgeAdapter;
  readonly actions: AdapterAction[] = [];
  readonly intent = null;
  readonly judgeOptions: JudgeOptions = {
    members: [],
    windows: [{ id: "blocks_current_day", label: "Member becomes unavailable on the planned day" }, { id: "blocks_all_days", label: "Member becomes unavailable on every candidate day" }],
  };
  previews() { return {}; }
  readonly localSynthetic = false;
  private constructor(readonly baseUrl: string, readonly sessionId: string) {
    this.description = `GET ${baseUrl}/v1/sessions/${sessionId}/events (read-only)`;
    this.judge = new HttpJudgeAdapter(baseUrl);
  }
  static create(baseUrlInput: string, sessionId: string): NetworkAdapter | null {
    const base = normalizeBaseUrl(baseUrlInput);
    if (!base || !/^[A-Za-z0-9_.:-]{1,64}$/.test(sessionId)) return null;
    return new NetworkAdapter(base, sessionId);
  }
  connect(h: AdapterHandlers) {
    h.onReset();
    return connectSse(this.baseUrl, this.sessionId, { onEvent: h.onEvent, onStatus: h.onStatus, onMalformed: h.onMalformed });
  }
}
