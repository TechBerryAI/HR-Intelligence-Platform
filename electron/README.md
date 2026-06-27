# Electron

Native desktop shell for the HR Job Portal.

## What is this?

Electron wraps the React frontend in a desktop window and exposes native OS capabilities through secure IPC.

## Why does it exist?

Browser file pickers restrict folder access. Bulk resume parsing requires selecting input/output directories — Electron provides native folder dialogs.

## Responsibilities (only)

| Capability | Implementation |
|------------|----------------|
| Native folder dialogs | `ipc-handlers.js` |
| File system access | IPC to main process |
| Window management | `main.js` |
| Secure preload bridge | `preload.js` |

## What should never be placed here?

- Business logic → `backend/`
- UI components → `frontend/`
- AI parsing → `ai/`
- API calls → `frontend/` (renderer)

## Architecture

```
main.js          → BrowserWindow, loads Vite dev server or frontend/dist
preload.js       → contextBridge exposes safe IPC API
ipc-handlers.js  → dialog.showOpenDialog for bulk parser folders
```

## Quick start

```bash
# Terminal 1
cd frontend && npm run dev

# Terminal 2 (repo root)
npm install && npm run electron
```

Production loads `frontend/dist/index.html` when not in development mode.

## Related documentation

- [Root README](../README.md#bulk-resume-parser-electron)
- [Frontend](../frontend/package.json)
