export {}; // ensure this file is treated as a module

declare global {
  interface ElectronAPI {
    send(action: unknown): Promise<void>;
    startListen(): Promise<void>;
    stopListen(): Promise<void>;
    shorten(): Promise<void>;
    codeHint(): Promise<void>;
    reindex(paths: string[]): Promise<void>;
    openSettings(): Promise<void>;
    openOverlay(): Promise<void>;
    getConfig(): Promise<Record<string, unknown>>;
    saveConfig(config: Record<string, unknown>): Promise<void>;
    onMessage(callback: (message: any) => void): () => void;
  }

  interface Window {
    electronAPI: ElectronAPI;
  }
}
