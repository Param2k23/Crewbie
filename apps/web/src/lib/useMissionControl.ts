"use client";
import { useCallback, useEffect, useMemo, useReducer, useRef, useState, useSyncExternalStore } from "react";
import type { MissionAdapter } from "./adapters";
import { JudgeRequest, JudgeResponse, newRequestId } from "./adapters/judge";
import type { ConnectionStatus } from "./adapters/sse";
import { initialState, missionReducer } from "./events/reducer";
import type { ReplaySnapshot } from "./replay/controller";

export type JudgeUiState =
  | { phase: "idle" }
  | { phase: "pending"; request: JudgeRequest }
  | { phase: "answered"; request: JudgeRequest; response: JudgeResponse };

const NO_REPLAY: ReplaySnapshot = { cursor: 0, total: 0, playing: false, holdMessage: null, speed: 1 };
const noopSubscribe = () => () => {};

export function useMissionControl(adapter: MissionAdapter) {
  const [state, dispatch] = useReducer(missionReducer, undefined, initialState);
  const [status, setStatus] = useState<ConnectionStatus>("idle");
  const [malformed, setMalformed] = useState(0);
  const [judgeState, setJudgeState] = useState<JudgeUiState>({ phase: "idle" });
  const adapterRef = useRef(adapter);
  adapterRef.current = adapter;

  useEffect(() => {
    dispatch({ type: "reset" });
    setJudgeState({ phase: "idle" });
    setMalformed(0);
    const stop = adapter.connect({
      onSnapshot: (snapshot) => dispatch({ type: "snapshot", snapshot }),
      onEvent: (raw) => dispatch({ type: "ingest", raw }),
      onReset: () => {
        dispatch({ type: "reset" });
        setJudgeState({ phase: "idle" });
      },
      onStatus: setStatus,
      onMalformed: () => setMalformed((n) => n + 1),
    });
    return stop;
  }, [adapter]);

  const replay = useSyncExternalStore(
    adapter.replay?.subscribe ?? noopSubscribe,
    adapter.replay?.getSnapshot ?? (() => NO_REPLAY),
    () => NO_REPLAY,
  );

  /** Judge requests go to the adapter only. Success is never inferred from the response. */
  const submitJudge = useCallback(
    async (change: JudgeRequest["changed_constraint_ref"]) => {
      const a = adapterRef.current;
      if (!a.judge || state.view.sessionId === null) return;
      const request: JudgeRequest = { request_id: newRequestId(), session_id: state.view.sessionId, changed_constraint_ref: change, synthetic_confirmed: true };
      setJudgeState({ phase: "pending", request });
      let response: JudgeResponse;
      try {
        response = await a.judge.submit(request);
      } catch {
        response = { request_id: request.request_id, status: "unavailable", message: "Request failed before reaching the backend. Nothing was changed." };
      }
      setJudgeState({ phase: "answered", request, response });
    },
    [state.view.sessionId],
  );

  const reflectedInStream = useMemo(() => {
    if (judgeState.phase !== "answered" || judgeState.response.status !== "accepted") return false;
    const id = judgeState.request.request_id;
    return state.log.some((e) => e.payload.request_id === id);
  }, [judgeState, state.log]);

  /** Judge intervention is limited to sandbox data: every received event must be flagged synthetic. */
  const judgeBlockedReason: string | null = !adapter.judge
    ? "This source is read-only. Switch to Demo scenario or a live sandbox session."
    : state.view.sessionId === null
      ? "Waiting for the session to start."
      : !state.view.allSynthetic
        ? "Blocked: this session contains non-synthetic events. Judge changes only apply to synthetic sandbox profiles."
        : null;

  return { state, view: state.view, status, malformed, replay, judgeState, submitJudge, reflectedInStream, judgeBlockedReason, dispatch };
}
