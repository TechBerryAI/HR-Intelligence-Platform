(function () {
  /* Must match THEME_STORAGE_KEY / DEFAULT_THEME in src/core/theme/themeConfig.js */
  var STORAGE_KEY = 'hcip-theme'
  var DEFAULT_THEME = 'dark'
  try {
    var t = localStorage.getItem(STORAGE_KEY)
    if (t !== 'light' && t !== 'dark') t = DEFAULT_THEME
    document.documentElement.setAttribute('data-theme', t)
    document.documentElement.classList.toggle('dark', t === 'dark')
    document.documentElement.classList.toggle('light', t === 'light')
    document.documentElement.style.colorScheme = t
  } catch (e) {
    document.documentElement.setAttribute('data-theme', DEFAULT_THEME)
    document.documentElement.classList.add('dark')
    document.documentElement.style.colorScheme = DEFAULT_THEME
  }
})()
