import { app, BrowserWindow, globalShortcut, ipcMain, Menu, Tray, nativeImage } from 'electron';
import path from 'node:path';
import fs from 'node:fs';
import { spawn, ChildProcessWithoutNullStreams } from 'node:child_process';
import { WebSocket } from 'ws';

interface AppConfig {
  overlay?: {
    x?: number;
    y?: number;
    width?: number;
    height?: number;
    opacity?: number;
  };
}

const isDev = !app.isPackaged;

let overlayWindow: BrowserWindow | null = null;
let settingsWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
let pythonProcess: ChildProcessWithoutNullStreams | null = null;
let ws: WebSocket | null = null;
let reconnectTimer: NodeJS.Timeout | null = null;
let pendingMessages: unknown[] = [];

const SINGLE_PIXEL_ICON =
  'iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAQAAAC1+jfqAAAAQklEQVR42mNgGLTgPwMDA8M/IJKBlAFiICBmA2JXEBvEkAExYBNBXAOiF4H0CUzAKIFaBzEfYF4gGiDeBmgFZBPgHQBynCIzQAslRhw3xGRAAAAAElFTkSuQmCC';

const getProjectRoot = () => (isDev ? path.resolve(__dirname, '..', '..', '..') : path.resolve(process.resourcesPath, '..'));

const configPath = path.resolve(getProjectRoot(), 'config.json');

const readConfig = (): AppConfig => {
  try {
    const raw = fs.readFileSync(configPath, 'utf-8');
    return JSON.parse(raw);
  } catch (error) {
    console.error('[config] Failed to read config.json', error);
    return {};
  }
};

const saveConfig = (config: Record<string, unknown>) => {
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf-8');
};

const getPreloadPath = () =>
  isDev ? path.join(__dirname, '../preload/index.ts') : path.join(__dirname, '../preload/index.js');

const getRendererUrl = (route: string) =>
  isDev
    ? `http://127.0.0.1:5173/#${route}`
    : `file://${path.join(__dirname, '../renderer/index.html')}#${route}`;

const broadcast = (message: unknown) => {
  overlayWindow?.webContents.send('ws-message', message);
  settingsWindow?.webContents.send('ws-message', message);
};

const flushPendingMessages = () => {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    return;
  }
  pendingMessages.forEach((payload) => ws?.send(JSON.stringify(payload)));
  pendingMessages = [];
};

const sendToPython = async (payload: unknown) => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(payload));
    return;
  }
  if (!ws || ws.readyState === WebSocket.CLOSED) {
    ensureWebSocket();
  }
  pendingMessages.push(payload);
};

const ensureWebSocket = () => {
  if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) {
    return;
  }

  ws = new WebSocket('ws://127.0.0.1:8765');

  ws.on('open', () => {
    console.log('[ws] Connected to python core');
    flushPendingMessages();
  });

  ws.on('message', (data) => {
    try {
      const parsed = JSON.parse(data.toString());
      broadcast(parsed);
    } catch (error) {
      console.error('[ws] Invalid JSON from server', error);
    }
  });

  ws.on('close', () => {
    console.warn('[ws] Connection closed, will retry');
    ws = null;
    if (!reconnectTimer) {
      reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        ensureWebSocket();
      }, 1000);
    }
  });

  ws.on('error', (error) => {
    console.error('[ws] Error', error);
  });
};

const startPythonCore = () => {
  if (pythonProcess) {
    return;
  }
  const projectRoot = getProjectRoot();
  console.log('[python] starting python core in', projectRoot);
  pythonProcess = spawn('python', ['-m', 'app.python_core.main', '--config', configPath], {
    cwd: projectRoot,
    env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
  });

  pythonProcess.stdout.on('data', (data) => {
    process.stdout.write(`[python] ${data}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    process.stderr.write(`[python] ${data}`);
  });

  pythonProcess.on('exit', (code, signal) => {
    console.warn(`[python] exited with code=${code} signal=${signal}`);
    pythonProcess = null;
  });
};

const stopPythonCore = () => {
  if (!pythonProcess) {
    return;
  }
  pythonProcess.kill();
  pythonProcess = null;
};

const createOverlayWindow = () => {
  if (overlayWindow) {
    return overlayWindow;
  }

  const config = readConfig();
  const overlayCfg = config.overlay ?? {};

  overlayWindow = new BrowserWindow({
    width: Math.round((overlayCfg.width as number) || 640),
    height: Math.round((overlayCfg.height as number) || 180),
    x: overlayCfg.x as number | undefined,
    y: overlayCfg.y as number | undefined,
    frame: false,
    transparent: true,
    resizable: false,
    alwaysOnTop: true,
    skipTaskbar: true,
    backgroundColor: '#00000000',
    webPreferences: {
      preload: getPreloadPath(),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  overlayWindow.setMenu(null);
  overlayWindow.setAlwaysOnTop(true, 'screen-saver');
  const opacity = typeof overlayCfg.opacity === 'number' ? Number(overlayCfg.opacity) : 1;
  overlayWindow.setOpacity(Math.min(1, Math.max(0.1, opacity)));
  overlayWindow.loadURL(getRendererUrl('/'));

  overlayWindow.on('close', (event) => {
    event.preventDefault();
    overlayWindow?.hide();
  });

  return overlayWindow;
};

const createSettingsWindow = () => {
  if (settingsWindow) {
    settingsWindow.show();
    return settingsWindow;
  }

  settingsWindow = new BrowserWindow({
    width: 980,
    height: 720,
    minWidth: 720,
    minHeight: 560,
    show: false,
    backgroundColor: '#0f172a',
    webPreferences: {
      preload: getPreloadPath(),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  settingsWindow.setMenu(null);
  settingsWindow.loadURL(getRendererUrl('/settings'));

  settingsWindow.once('ready-to-show', () => {
    settingsWindow?.show();
  });

  settingsWindow.on('close', (event) => {
    event.preventDefault();
    settingsWindow?.hide();
  });

  return settingsWindow;
};

const toggleOverlayVisibility = () => {
  const window = createOverlayWindow();
  if (window.isVisible()) {
    window.hide();
  } else {
    window.showInactive();
  }
};

const registerShortcuts = () => {
  globalShortcut.register('Control+Space', () => {
    toggleOverlayVisibility();
  });
  globalShortcut.register('Control+R', () => {
    void sendToPython({ type: 'shorten_last' });
  });
  globalShortcut.register('Control+Q', () => {
    void sendToPython({ type: 'code_hint' });
  });
};

const createTray = () => {
  if (tray) {
    return tray;
  }

  const image = nativeImage.createFromDataURL(`data:image/png;base64,${SINGLE_PIXEL_ICON}`);
  tray = new Tray(image);
  tray.setToolTip('Interview Copilot');
  const contextMenu = Menu.buildFromTemplate([
    { label: 'Показать подсказку', click: () => createOverlayWindow().show() },
    { label: 'Скрыть подсказку', click: () => overlayWindow?.hide() },
    { type: 'separator' },
    { label: 'Начать слушать', click: () => void sendToPython({ type: 'start_listen' }) },
    { label: 'Остановить', click: () => void sendToPython({ type: 'stop_listen' }) },
    { type: 'separator' },
    { label: 'Настройки', click: () => createSettingsWindow() },
    { type: 'separator' },
    {
      label: 'Выход',
      click: () => {
        stopPythonCore();
        app.quit();
      },
    },
  ]);
  tray.setContextMenu(contextMenu);
  tray.on('click', () => {
    toggleOverlayVisibility();
  });
  return tray;
};

const setupIpc = () => {
  ipcMain.handle('ws-send', async (_event, payload) => {
    await sendToPython(payload);
  });

  ipcMain.handle('window:settings', async () => {
    createSettingsWindow();
  });

  ipcMain.handle('window:overlay', async () => {
    createOverlayWindow().show();
  });

  ipcMain.handle('config:get', async () => {
    return readConfig();
  });

  ipcMain.handle('config:save', async (_event, payload) => {
    const data = payload as Record<string, unknown>;
    saveConfig(data);
    await sendToPython({ type: 'set_config', payload: data });
    const overlayCfg = (data.overlay ?? {}) as Record<string, unknown>;
    if (overlayWindow && Object.keys(overlayCfg).length > 0) {
      const width = Number(overlayCfg.width ?? overlayWindow.getBounds().width);
      const height = Number(overlayCfg.height ?? overlayWindow.getBounds().height);
      const x = overlayCfg.x as number | undefined;
      const y = overlayCfg.y as number | undefined;
      overlayWindow.setOpacity(Math.min(1, Math.max(0.1, Number(overlayCfg.opacity ?? overlayWindow.getOpacity()))));
      overlayWindow.setBounds({
        width: Number.isFinite(width) ? Math.round(width) : overlayWindow.getBounds().width,
        height: Number.isFinite(height) ? Math.round(height) : overlayWindow.getBounds().height,
        x: typeof x === 'number' ? Math.round(x) : overlayWindow.getBounds().x,
        y: typeof y === 'number' ? Math.round(y) : overlayWindow.getBounds().y,
      });
    }
  });
};

const setupLifecycle = (): boolean => {
  const gotLock = app.requestSingleInstanceLock();
  if (!gotLock) {
    app.quit();
    return false;
  }

  app.on('before-quit', () => {
    globalShortcut.unregisterAll();
    stopPythonCore();
    ws?.close();
  });

  app.on('window-all-closed', (event) => {
    event.preventDefault();
  });

  app.on('second-instance', () => {
    if (overlayWindow) {
      overlayWindow.show();
    }
    if (settingsWindow) {
      settingsWindow.show();
    }
  });
  return true;
};

const bootstrap = async () => {
  if (!setupLifecycle()) {
    return;
  }
  await app.whenReady();
  Menu.setApplicationMenu(null);
  startPythonCore();
  ensureWebSocket();
  setupIpc();
  createOverlayWindow();
  createTray();
  registerShortcuts();
};

void bootstrap();
