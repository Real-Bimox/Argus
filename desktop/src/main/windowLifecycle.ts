/** Pure desktop-window lifetime policy, kept independent of Electron for tests. */

/** A normal close hides the shell; only an explicit stop-and-quit stops work. */
export function shouldHideWindowOnClose(quitting: boolean): boolean {
  return !quitting;
}

/** Default app exit detaches the owned backend for later authenticated adoption. */
export function shouldStopBackendOnQuit(stopBackendAndQuitRequested: boolean): boolean {
  return stopBackendAndQuitRequested;
}
