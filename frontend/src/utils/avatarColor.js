export function getAvatarGradient(seed = '') {
  const input = seed || 'candidate'
  let hash = 0
  for (let i = 0; i < input.length; i += 1) {
    hash = (hash * 31 + input.charCodeAt(i)) % 360
  }
  const huePrimary = hash
  const hueSecondary = (huePrimary + 40) % 360
  const color1 = `hsl(${huePrimary} 80% 55%)`
  const color2 = `hsl(${hueSecondary} 75% 45%)`
  return `linear-gradient(135deg, ${color1}, ${color2})`
}

