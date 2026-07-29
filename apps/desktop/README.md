# Desktop (Electron)

Native shell for bulk resume parsing folder dialogs. Canonical location: `apps/desktop/`.

## What belongs here?

- BrowserWindow / IPC for native folder pickers
- Loading the Vite frontend (dev) or `apps/frontend/dist` (production)

## What should never be placed here?

- Business logic → `apps/backend/`
- UI components → `apps/frontend/`
- API calls → `apps/frontend/` (renderer)

## Layout

```
main.js          → BrowserWindow, loads Vite or frontend/dist
preload.js       → contextBridge for IPC
ipc-handlers.js  → native dialogs
```

## Quick start

```bash
# Terminal 1
cd apps/frontend && npm run dev

# Terminal 2 (repo root)
npm run electron
```

Production loads `apps/frontend/dist/index.html` when not in development mode.

## Related

- [Frontend](../frontend/package.json)
