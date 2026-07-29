const { dialog, ipcMain } = require('electron')
const fs = require('fs')
const path = require('path')

const ALLOWED_EXT = new Set(['.pdf', '.doc', '.docx'])

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

ipcMain.handle('dialog:selectInputFolder', async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog({
    properties: ['openDirectory'],
    title: 'Select folder containing resumes',
  })
  if (canceled || !filePaths?.length) return null
  const dirPath = filePaths[0]
  const entries = fs.readdirSync(dirPath, { withFileTypes: true })
  const files = []
  for (const e of entries) {
    if (!e.isFile()) continue
    const ext = path.extname(e.name).toLowerCase()
    if (!ALLOWED_EXT.has(ext)) continue
    const fullPath = path.join(dirPath, e.name)
    const data = fs.readFileSync(fullPath)
    files.push({ name: e.name, data: data.toString('base64') })
  }
  return { folderPath: dirPath, files }
})
