// Local acceptance launcher starts the pinned Playwright CLI with --import of this
// bridge and an IPC channel. SIGINT uses Playwright's own bounded cancellation path.
process.on("message", (message) => {
  if (message?.type === "acceptance-stop") {
    console.log(
      "ACCEPTANCE_STOP_ACK " + JSON.stringify({ at: new Date().toISOString() }),
    );
    process.emit("SIGINT");
  }
});
