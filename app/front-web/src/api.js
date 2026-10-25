// Cliente del servidor (servidor/src/servidor/api/app.py). Con location.hostname el mismo build
// funciona desde localhost y desde otra máquina de la red.
export const SERVIDOR_URL =
  import.meta.env.VITE_SERVIDOR_URL ?? `http://${location.hostname}:8000`

async function leer(respuesta) {
  if (respuesta.ok) return respuesta.json()
  // FastAPI devuelve {"detail": "..."}: es lo que el usuario necesita ver (ej. modelo caído).
  let detalle = `el servidor respondió ${respuesta.status}`
  try {
    const cuerpo = await respuesta.json()
    if (typeof cuerpo.detail === 'string') detalle = cuerpo.detail
    else if (cuerpo.detail) detalle = JSON.stringify(cuerpo.detail)
  } catch {
    // cuerpo no JSON: queda el código de estado
  }
  throw new Error(detalle)
}

export async function enviarPedido(wavBlob, sesion) {
  const formData = new FormData()
  formData.append('audio', wavBlob, 'audio.wav')
  formData.append('sesion', sesion)
  return leer(await fetch(`${SERVIDOR_URL}/pedidos`, { method: 'POST', body: formData }))
}

export async function confirmar(id, aceptar) {
  return leer(
    await fetch(`${SERVIDOR_URL}/confirmaciones/${id}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ aceptar }),
    }),
  )
}

export async function salud() {
  return leer(await fetch(`${SERVIDOR_URL}/salud`))
}
