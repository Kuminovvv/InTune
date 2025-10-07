import { contextBridge, ipcRenderer } from 'electron';

type MessageListener = (message: unknown) => void;

const api = {
  send: async (payload: unknown) => {
    await ipcRenderer.invoke('ws-send', payload);
  },
  startListen: async () => {
    await ipcRenderer.invoke('ws-send', { type: 'start_listen' });
  },
  stopListen: async () => {
    await ipcRenderer.invoke('ws-send', { type: 'stop_listen' });
  },
  shorten: async () => {
    await ipcRenderer.invoke('ws-send', { type: 'shorten_last' });
  },
  codeHint: async () => {
    await ipcRenderer.invoke('ws-send', { type: 'code_hint' });
  },
  reindex: async (paths: string[]) => {
    await ipcRenderer.invoke('ws-send', { type: 'reindex', paths });
  },
  openSettings: async () => {
    await ipcRenderer.invoke('window:settings');
  },
  openOverlay: async () => {
    await ipcRenderer.invoke('window:overlay');
  },
  getConfig: async () => ipcRenderer.invoke('config:get'),
  saveConfig: async (config: Record<string, unknown>) => ipcRenderer.invoke('config:save', config),
  onMessage: (listener: MessageListener) => {
    const handler = (_event: Electron.IpcRendererEvent, message: unknown) => listener(message);
    ipcRenderer.on('ws-message', handler);
    return () => {
      ipcRenderer.removeListener('ws-message', handler);
    };
  },
};

contextBridge.exposeInMainWorld('electronAPI', api);
