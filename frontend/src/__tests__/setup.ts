/**
 * Setup para tests de vitest.
 * Proporciona mocks para APIs del navegador que Zustand/lucide puedan necesitar.
 */

// Mock de localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = value; },
    removeItem: (key: string) => { delete store[key]; },
    clear: () => { store = {}; },
    get length() { return Object.keys(store).length; },
    key: (index: number) => Object.keys(store)[index] ?? null,
  };
})();

Object.defineProperty(globalThis, "localStorage", { value: localStorageMock });

// Mock de Audio
class AudioMock {
  src = "";
  constructor(src?: string) { this.src = src || ""; }
  play() { return Promise.resolve(); }
}
Object.defineProperty(globalThis, "Audio", { value: AudioMock, writable: true });

class ResizeObserverMock {
  observe() {}
  disconnect() {}
  unobserve() {}
}
Object.defineProperty(globalThis, "ResizeObserver", { value: ResizeObserverMock, writable: true });
