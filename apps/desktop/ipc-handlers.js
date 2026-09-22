const { app, dialog, ipcMain, safeStorage } = require('electron')
const fs = require('fs')
const path = require('path')

const ALLOWED_EXT = new Set(['.pdf', '.doc', '.docx'])

// Auth tokens for the Electron client: it can't rely on the web's httpOnly
// cookie (the production build loads via file:// and calls the API
// cross-origin, so a SameSite cookie from the API's origin never attaches),
// so it keeps using an Authorization header instead — backed by OS-keychain
// encryption here rather than the renderer's localStorage.
const SECURE_STORAGE_PATH = () => path.join(app.getPath('userData'), 'secure-tokens.json')

function readSecureStorageFile() {
  try {
    const raw = fs.readFileSync(SECURE_STORAGE_PATH(), 'utf8')
    return JSON.parse(raw)
  } catch {
    return {}
  }
}

function writeSecureStorageFile(data) {
  fs.writeFileSync(SECURE_STORAGE_PATH(), JSON.stringify(data), 'utf8')
}

ipcMain.handle('secureStorage:get', async (_, key) => {
  if (!safeStorage.isEncryptionAvailable()) return null
  const stored = readSecureStorageFile()
  const encoded = stored[key]
  if (!encoded) return null
  try {
    return safeStorage.decryptString(Buffer.from(encoded, 'base64'))
  } catch {
    return null
  }
})

ipcMain.handle('secureStorage:set', async (_, key, value) => {
  if (!safeStorage.isEncryptionAvailable()) return false
  const stored = readSecureStorageFile()
  stored[key] = safeStorage.encryptString(String(value)).toString('base64')
  writeSecureStorageFile(stored)
  return true
})

ipcMain.handle('secureStorage:clear', async () => {
  writeSecureStorageFile({})
  return true
})

ipcMain.handle('dialog:selectFolder', async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog({
    properties: ['openDirectory'],
    title: 'Select output folder',
  })
  if (canceled || !filePaths?.length) return null
  return filePaths[0]
})

ipcMain.handle('dialog:selectSaveFile', async (_, suggestedName) => {
  const { canceled, filePath } = await dialog.showSaveDialog({
    defaultPath: suggestedName,
    title: 'Choose output file',
    filters: [{ name: 'Excel', extensions: ['xlsx'] }],
  })
  if (canceled || !filePath) return null
  return filePath
})

/**
 * Recursively collect resume files under rootDir (all nested subfolders).
 */
function collectResumeFiles(rootDir, currentDir = rootDir, files = []) {
  let entries
  try {
    entries = fs.readdirSync(currentDir, { withFileTypes: true })
  } catch {
    return files
  }
  for (const e of entries) {
    const fullPath = path.join(currentDir, e.name)
    if (e.name.startsWith('.')) continue
    if (e.isDirectory()) {
      collectResumeFiles(rootDir, fullPath, files)
      continue
    }
    if (!e.isFile()) continue
    const ext = path.extname(e.name).toLowerCase()
    if (!ALLOWED_EXT.has(ext)) continue
    try {
      const data = fs.readFileSync(fullPath)
      // Preserve relative path so nested same-named files stay unique on the server
      const rel = path.relative(rootDir, fullPath).split(path.sep).join('__')
      files.push({ name: rel || e.name, data: data.toString('base64') })
    } catch {
      // skip unreadable files
    }
  }
  return files
}

ipcMain.handle('dialog:selectInputFolder', async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog({
    properties: ['openDirectory'],
    title: 'Select folder containing resumes',
  })
  if (canceled || !filePaths?.length) return null
  const dirPath = filePaths[0]
  const files = collectResumeFiles(dirPath)
  return { folderPath: dirPath, files }
})
