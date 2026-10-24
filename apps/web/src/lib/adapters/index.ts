import { fixtureEvents } from "../fixtures";
import { DEMO_HOLD_INDEX, DEMO_HOLD_MESSAGE, DEMO_SESSION, LocalSimulator, demoBaseEvents } from "../demo/scenario";
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
  readonly label = "Demo scenario (synthetic)";
  readonly description = "Scripted four-agent scenario. Events and the judge response come from a local simulator, not the negotiation engine.";
  readonly sessionId = DEMO_SESSION;
  readonly localSynthetic = true;
  readonly replay: ReplayController;
  readonly judge: LocalSimulator;
  readonly actions: AdapterAction[];
  private h: AdapterHandlers | null = null;
  constructor() {
    this.replay = new ReplayController({
      events: demoBaseEvents,
      holds: { [DEMO_HOLD_INDEX]: DEMO_HOLD_MESSAGE },
      onEvent: (e) => this.h?.onEvent(e),
      onReset: () => {
        this.judge.resetCounters();
        this.h?.onReset();
      },
    });
    this.judge = new LocalSimulator(() => this.replay);
    this.actions = [
      {
        id: "remaining-accept",
        label: "Let remaining members accept",
        hint: "Scripted: appends acceptances then a confirmation, for showing the confirmed state.",
        run: () => this.judge.remainingMembersAccept(),
      },
    ];
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

/** Read-only SSE bridge to the realtime service / integrated backend. */
export class NetworkAdapter implements MissionAdapter {
  readonly kind = "network" as const;
  readonly label = "Live stream (SSE)";
  readonly description: string;
  readonly replay = null;
  readonly judge: JudgeAdapter;
  readonly actions: AdapterAction[] = [];
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
