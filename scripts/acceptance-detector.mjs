const mockedResetTitle =
  "workspace notes: failed reset preserves notes and successful reset clears captured incident";
const mockedResetPath = "/api/demo/scenarios/kafka-pricing-lag/reset";

function safeUrl(value) {
  try {
    const url = new URL(value);
    return url.origin + url.pathname;
  } catch {
    return "unparseable-url";
  }
}

export function isExpectedMockReset(response) {
  try {
    return (
      response.status === 500 &&
      response.method === "POST" &&
      response.testId === mockedResetTitle &&
      new URL(response.url).pathname === mockedResetPath &&
      response.mockedResetProof?.fulfilled === true &&
      response.mockedResetProof.detail === "Reset failed"
    );
  } catch {
    return false;
  }
}

// Separate, exact legacy negative-path fixture; the reset500 predicate is unchanged.
export function isExpectedScenarioOutage(response) {
  try {
    return response.status === 503 && response.method === "GET" &&
      response.testId === "the console recovers when its initial scenario request is temporarily unavailable" &&
      new URL(response.url).pathname === "/api/scenarios" &&
      response.mockedScenarioProof?.fulfilled === true &&
      response.mockedScenarioProof.detail === "Temporary synthetic test outage";
  } catch { return false; }
}

export function createAcceptanceDetector({
  onFailure = () => {},
  now = () => new Date().toISOString(),
} = {}) {
  let failure = null,
    stopStartedAt = null,
    stoppedAt = null,
    expectedMockResponses = 0, expectedScenarioResponses = 0;
  const pending = new Map();
  function fail(kind, details = {}) {
    if (failure) return;
    failure = { kind, detectedAt: now(), ...details };
    onFailure(failure);
  }
  function inspect(source, line) {
    if (source.startsWith("backend")) {
      if (/QueuePool limit\b/.test(line)) return fail("backend-pool-timeout");
      if (
        /Exception in ASGI application|Exception terminating connection|Error closing cursor|Exception during reset or similar|Application shutdown failed|(?:Task|Future) exception was never retrieved|Task was destroyed but it is pending|Traceback \(most recent call last\)|\bCancelledError\b/.test(
          line,
        )
      )
        return fail("backend-error");
      const access = line.match(
        /"(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+([^"\s]+)\s+HTTP\/[^"\s]+"\s+(5\d\d)\b/,
      );
      if (access)
        return fail("backend-http-5xx", {
          method: access[1],
          path: access[2].split("?")[0],
          status: Number(access[3]),
        });
      const start = line.indexOf("{");
      if (start >= 0) {
        try {
          const event = JSON.parse(line.slice(start));
          if (event.logger === "creditops.sse" && ["sse_cleanup_deadline", "sse_cleanup_failed", "sse_read_failed", "sse_shutdown_incomplete"].includes(event.event))
            fail("backend-sse-cleanup", { event: event.event });
          if (event.event === "http_request" && event.status >= 500)
            fail("backend-http-5xx", { status: event.status });
        } catch {
          /* A split JSON line is inspected again when its remaining bytes arrive. */
        }
      }
    }
    if (source.startsWith("frontend")) {
      if (/\b(?:GET|POST|HEAD)\s+\S+\s+5\d\d\b/.test(line))
        return fail("frontend-http-5xx");
      if (
        /\b(?:Error|TypeError|ReferenceError|SyntaxError|UnhandledPromiseRejection|uncaughtException)\s*:|Unhandled (?:error|rejection)|FATAL|⨯/i.test(
          line,
        )
      )
        fail("frontend-error");
    }
  }
  return {
    observeResponse(response) {
      if (response.status < 500) return;
      if (isExpectedMockReset(response)) {
        expectedMockResponses += 1;
        return;
      }
      if (isExpectedScenarioOutage(response)) { expectedScenarioResponses += 1; return; }
      fail("browser-http-5xx", {
        status: response.status,
        method: response.method,
        url: safeUrl(response.url),
        testId: response.testId,
      });
    },
    observeConsoleError({ testId, url, text, mockedResponse }) {
      if (
        mockedResponse &&
        isExpectedMockReset(mockedResponse) &&
        url === mockedResponse.url &&
        /^Failed to load resource: the server responded with a status of 500(?: \(Internal Server Error\))?$/.test(
          text,
        )
      )
        return;
      if (mockedResponse && isExpectedScenarioOutage(mockedResponse) && url === mockedResponse.url && /^Failed to load resource: the server responded with a status of 503(?: \(Service Unavailable\))?$/.test(text)) return;
      fail("browser-console-error", { testId });
    },
    observePageError({ testId }) {
      fail("browser-page-error", { testId });
    },
    observeFailure(row) {
      fail(row.kind, { ...row, detectedAt: row.detectedAt ?? now() });
    },
    feedLog(source, chunk) {
      let text = (pending.get(source) ?? "") + String(chunk);
      let end;
      while ((end = text.indexOf("\n")) >= 0) {
        inspect(source, text.slice(0, end));
        text = text.slice(end + 1);
      }
      pending.set(source, text);
      // Error markers need not wait for a trailing newline or process exit.
      if (text) inspect(source, text);
    },
    flush(source) {
      const text = pending.get(source);
      if (text) inspect(source, text);
      pending.delete(source);
    },
    markStopStarted() {
      stopStartedAt ??= now();
    },
    markStopped() {
      stoppedAt ??= now();
    },
    snapshot() {
      return {
        failure: failure && { ...failure },
        stopStartedAt,
        stoppedAt,
        expectedMockResponses,
        expectedScenarioResponses,
      };
    },
  };
}
