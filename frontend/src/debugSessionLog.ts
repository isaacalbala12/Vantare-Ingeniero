/** NDJSON debug logs for agent session 69c028 (TTS pipeline audit). */

export function debugSessionLog(

  location: string,

  message: string,

  data: Record<string, unknown>,

  hypothesisId: string,

  runId = "pre-fix",

): void {

  const payload = JSON.stringify({

    sessionId: "69c028",

    location,

    message,

    data,

    hypothesisId,

    runId,

    timestamp: Date.now(),

  });

  // #region agent log

  fetch("http://127.0.0.1:7939/ingest/20432f56-948e-4647-80fd-59ef4be49b3b", {

    method: "POST",

    headers: {

      "Content-Type": "application/json",

      "X-Debug-Session-Id": "69c028",

    },

    body: payload,

  }).catch(() => {});

  fetch("http://127.0.0.1:8008/debug/ingest", {

    method: "POST",

    headers: { "Content-Type": "application/json" },

    body: payload,

  }).catch(() => {});

  // #endregion

}

