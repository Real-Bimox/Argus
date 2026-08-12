import log from 'electron-log/main';
import { join } from 'node:path';
import { app } from 'electron';

export function createLogger(): typeof log {
  log.initialize();
  if (app.isPackaged) {
    log.transports.console.level = false;
  }
  log.transports.file.resolvePathFn = () =>
    join(app.getPath('userData'), 'logs', 'desktop.log');
  log.transports.file.maxSize = 5 * 1024 * 1024;
  log.catchErrors({
    showDialog: false,
    onError(error) {
      log.error('uncaught main-process error', error);
    }
  });
  return log;
}
