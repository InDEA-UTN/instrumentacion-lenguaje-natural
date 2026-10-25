import { useState } from 'react'
import { confirmar } from './api.js'

const ESTADOS = {
  ejecutada: { icono: '✅', texto: 'Ejecutada' },
  consultada: { icono: '🔎', texto: 'Consultada' },
  aclaracion: { icono: '❓', texto: 'Aclaración' },
  confirmacion_pendiente: { icono: '⚠️', texto: 'Confirmación pendiente' },
  rechazada: { icono: '⛔', texto: 'Rechazada' },
  cancelada: { icono: '✖', texto: 'Cancelada' },
}

function conUnidad(magnitud) {
  return magnitud.unidad ? `${magnitud.valor} ${magnitud.unidad}` : `${magnitud.valor}`
}

// Parámetros con unidad: la unidad la fija el catálogo y viene en el comando validado. Si no hubo
// comando (aclaración, rechazo), se muestran los valores crudos de la intención.
function parametros(interaccion) {
  const delComando = interaccion.comando?.parametros
  if (delComando && Object.keys(delComando).length > 0) {
    return Object.entries(delComando).map(([k, m]) => `${k} = ${conUnidad(m)}`).join(', ')
  }
  const crudos = interaccion.intencion?.parametros ?? {}
  return Object.entries(crudos).map(([k, v]) => `${k} = ${v}`).join(', ')
}

export default function Resultado({ interaccion, totalS, onActualizar, onError }) {
  const [confirmando, setConfirmando] = useState(false)
  const { estado, mensaje, transcripcion, intencion, comando, rechazo, resultado } = interaccion
  const insignia = ESTADOS[estado] ?? { icono: '•', texto: estado }

  const responder = async (aceptar) => {
    setConfirmando(true)
    try {
      onActualizar(await confirmar(interaccion.id, aceptar))
    } catch (err) {
      onError('No se pudo confirmar: ' + err.message)
    } finally {
      setConfirmando(false)
    }
  }

  return (
    <div className={`tarjeta tarjeta-${estado}`}>
      <div className="insignia">
        {insignia.icono} {insignia.texto}
      </div>
      <p className="mensaje">{mensaje}</p>

      {estado === 'aclaracion' && <p className="nota">Respondé grabando de nuevo.</p>}

      {estado === 'confirmacion_pendiente' && (
        <div className="acciones">
          <button onClick={() => responder(true)} disabled={confirmando}>Confirmar</button>
          <button className="secundario" onClick={() => responder(false)} disabled={confirmando}>
            Cancelar
          </button>
        </div>
      )}

      <dl>
        {transcripcion && (
          <>
            <dt>Escuché</dt>
            <dd>
              «{transcripcion.texto}»
              <small>
                {transcripcion.modelo.nombre} · {transcripcion.latencia_s.toFixed(1)} s
              </small>
            </dd>
          </>
        )}

        {intencion && (intencion.accion || estado !== 'rechazada') && (
          <>
            <dt>Entendí</dt>
            <dd>
              {intencion.accion ?? <em>sin acción</em>}
              {parametros(interaccion) && <> ({parametros(interaccion)})</>}
              <small>
                {intencion.tipo} · confianza {intencion.confianza.toFixed(2)}
                {intencion.modelo && <> · {intencion.modelo.nombre}</>}
              </small>
            </dd>
          </>
        )}

        {comando && (
          <>
            <dt>Comando</dt>
            <dd>
              {comando.escritura && <code>{comando.escritura}</code>}
              {comando.verificacion && <code>{comando.verificacion}</code>}
            </dd>
          </>
        )}

        {resultado && (
          <>
            <dt>Instrumento respondió</dt>
            <dd>{resultado.lectura ?? <em>sin lectura</em>}</dd>
          </>
        )}

        {rechazo && (
          <>
            <dt>Motivo</dt>
            <dd>{rechazo.motivo}</dd>
          </>
        )}
      </dl>

      {totalS != null && <p className="pie">Pedido completo en {totalS.toFixed(1)} s</p>}
    </div>
  )
}
