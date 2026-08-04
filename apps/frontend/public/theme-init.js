(function () {
  try {
    var t = localStorage.getItem('hcip-theme')
    if (t !== 'light' && t !== 'dark') t = 'dark'
    document.documentElement.setAttribute('data-theme', t)
    document.documentElement.classList.toggle('dark', t === 'dark')
    document.documentElement.classList.toggle('light', t === 'light')
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'dark')
    document.documentElement.classList.add('dark')
  }
})()
