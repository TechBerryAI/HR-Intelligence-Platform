const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electron', {
  selectFolder: () => ipcRenderer.invoke('dialog:selectFolder'),
  selectSaveFile: (suggestedName = 'Parsed_Resumes.xlsx') =>
    ipcRenderer.invoke('dialog:selectSaveFile', suggestedName),
  selectInputFolder: () => ipcRenderer.invoke('dialog:selectInputFolder'),
  secureStorage: {
    get: (key) => ipcRenderer.invoke('secureStorage:get', key),
    set: (key, value) => ipcRenderer.invoke('secureStorage:set', key, value),
    clear: () => ipcRenderer.invoke('secureStorage:clear'),
  },
})
