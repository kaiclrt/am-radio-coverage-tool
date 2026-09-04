/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL for the Flask API. Defaults to '' (same-origin, via the Vite
   *  dev-server proxy). Set to an absolute origin for a deployed build. */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
