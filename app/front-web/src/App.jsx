import { useCallback, useEffect, useRef, useState } from 'react'
import { concatFloat32, encodeWav } from './wav.js'
import { SERVIDOR_URL, enviarPedido, modelos as consultarModelos, saludInstrumento } from './api.js'
import Resultado from './Resultado.jsx'
import Selectores, { proveedorDe } from './Selectores.jsx'

// Por debajo de esto fue un toque, no un pedido: no vale la pena mandarlo al servidor.
const DURACION_MINIMA_MS = 300

// Cada cuánto se le pregunta al servidor si el instrumento responde: así se ve enchufarlo o
// desenchufarlo sin recargar. Cada consulta es un *IDN? al equipo.
const INTERVALO_INSTRUMENTO_MS = 5000

const CLAVE_SELECCION = 'seleccion-modelos'

// La elección se recuerda en el navegador. Si el servidor ya no ofrece un modelo guardado (se sacó
// de proveedores.yaml), esa etapa vuelve al predeterminado.
function seleccionInicial(catalogo) {
  let guardada = {}
  try {
    guardada = JSON.parse(localStorage.getItem(CLAVE_SELECCION)) ?? {}
  } catch {
    // sin almacenamiento (ventana privada): se usa el predeterminado
  }
  const seleccion = {}
  for (const etapa of ['asr', 'interprete']) {
    const valida = guardada[etapa] && proveedorDe(catalogo, etapa, guardada[etapa])
    seleccion[etapa] = valida ? guardada[etapa] : catalogo[etapa].predeterminado
  }
  return seleccion
}

function nuevaSesion() {
  // randomUUID solo existe en contexto seguro (https o localhost).
  return globalThis.crypto?.randomUUID?.() ?? Math.random().toString(16).slice(2) + Date.now().toString(16)
}

// "TEKTRONIX,TBS1072B,C010001,CF:91.1CT FV:v4.03" → número de serie y firmware, para distinguir
// dos equipos del mismo modelo. Si la respuesta no tiene esa forma, se muestra entera al pasar el mouse.
function identidad(idn) {
  const [, , serie, version = ''] = idn.split(',').map((parte) => parte.trim())
  const firmware = version.match(/FV:\S+/)?.[0] ?? version
  return [serie, firmware].filter(Boolean).join(' · ')
}

function LineaInstrumento({ instrumento, revisando, onRevisar }) {
  if (!instrumento) return <p className="salud">Consultando el servidor…</p>
  if (instrumento.error) {
    return (
      <p className="salud salud-mal">
        Servidor no disponible en {SERVIDOR_URL}: {instrumento.error}{' '}
        <BotonRevisar revisando={revisando} onRevisar={onRevisar} />
      </p>
    )
  }
  const simulado = instrumento.conexion === 'InstrumentoFake'
  let estado, detalle
  if (simulado) {
    estado = '(simulado en memoria)'
    detalle = 'El servidor corre con INSTRUMENTO=fake: no hay un equipo real conectado.'
  } else if (instrumento.listo) {
    const id = instrumento.idn_conectado ? identidad(instrumento.idn_conectado) : ''
    estado = `✓ conectado${id ? ' · ' + id : ''}`
    detalle = `Respondió: ${instrumento.idn_conectado ?? '?'}\nRecurso VISA: ${instrumento.recurso_conectado ?? '?'}`
  } else {
    estado = '✗ no conectado'
    detalle =
      'No responde. Revisá que esté prendido y con el cable USB en el puerto trasero (Device), ' +
      'no en el de adelante.'
  }
  return (
    <p className="salud">
      Instrumento:{' '}
      <span className={simulado || instrumento.listo ? 'ok' : 'mal'} title={detalle}>
        {instrumento.modelo} {estado}
      </span>{' '}
      {!simulado && <BotonRevisar revisando={revisando} onRevisar={onRevisar} />}
    </p>
  )
}

function BotonRevisar({ revisando, onRevisar }) {
  return (
    <button className="secundario chico" onClick={onRevisar} disabled={revisando}>
      {revisando ? 'Revisando…' : 'Revisar'}
    </button>
  )
}

export default function App() {
  const [estado, setEstado] = useState('idle') // idle | grabando | procesando
  const [interaccion, setInteraccion] = useState(null) // última Interaccion del servidor
  const [totalS, setTotalS] = useState(null)
  const [error, setError] = useState('')
  const [aviso, setAviso] = useState('')
  const [nivel, setNivel] = useState(0) // 0..1, volumen detectado mientras se graba
  const [segundos, setSegundos] = useState(0)
  const [sesion, setSesion] = useState(nuevaSesion)
  const [instrumento, setInstrumento] = useState(null) // GET /salud/instrumento, o {error}
  const [revisando, setRevisando] = useState(false)
  const [catalogoModelos, setCatalogoModelos] = useState(null)
  const [seleccion, setSeleccion] = useState({})
  const [actualizandoModelos, setActualizandoModelos] = useState(false)

  const audioContextRef = useRef(null)
  const streamRef = useRef(null)
  const processorRef = useRef(null)
  const sourceRef = useRef(null)
  const chunksRef = useRef([])
  const inicioRef = useRef(0)
  const presionadoRef = useRef(false) // el usuario sigue presionando (botón o barra espaciadora)
  const ocupadoRef = useRef(false) // abriendo el micrófono, grabando o esperando al servidor
  const sesionRef = useRef(sesion)
  sesionRef.current = sesion
  const seleccionRef = useRef(seleccion)
  seleccionRef.current = seleccion

  // Una consulta a la vez: con el equipo colgado, una puede tardar el timeout de VISA (10 s) y no
  // tiene sentido apilar otras detrás.
  const consultandoInstrumentoRef = useRef(false)
  const actualizarInstrumento = useCallback(async () => {
    if (consultandoInstrumentoRef.current) return
    consultandoInstrumentoRef.current = true
    setRevisando(true)
    try {
      setInstrumento(await saludInstrumento())
    } catch (err) {
      setInstrumento({ error: err.message })
    } finally {
      consultandoInstrumentoRef.current = false
      setRevisando(false)
    }
  }, [])

  // Consulta periódica. Se saltea mientras hay un pedido en curso (el servidor atiende al equipo de
  // a uno) y con la pestaña oculta; al volver a la pestaña se consulta en el momento.
  useEffect(() => {
    const revisar = () => {
      if (document.visibilityState === 'visible' && !ocupadoRef.current) actualizarInstrumento()
    }
    const id = setInterval(revisar, INTERVALO_INSTRUMENTO_MS)
    document.addEventListener('visibilitychange', revisar)
    return () => {
      clearInterval(id)
      document.removeEventListener('visibilitychange', revisar)
    }
  }, [actualizarInstrumento])

  const actualizarModelos = useCallback(async (refrescar = false) => {
    setActualizandoModelos(true)
    try {
      const catalogo = await consultarModelos(refrescar)
      setCatalogoModelos(catalogo)
      setSeleccion((actual) => (actual.asr ? actual : seleccionInicial(catalogo)))
    } catch (err) {
      setCatalogoModelos((actual) => actual ?? { error: err.message })
    } finally {
      setActualizandoModelos(false)
    }
  }, [])

  useEffect(() => {
    actualizarInstrumento()
    actualizarModelos()
  }, [actualizarInstrumento, actualizarModelos])

  const cambiarModelo = (etapa, id) => {
    setSeleccion((actual) => {
      const nueva = { ...actual, [etapa]: id }
      try {
        localStorage.setItem(CLAVE_SELECCION, JSON.stringify(nueva))
      } catch {
        // sin almacenamiento: la elección vale hasta recargar
      }
      return nueva
    })
  }

  // Contador visible mientras se espera: con el modelo local en CPU el pedido tarda varios segundos.
  useEffect(() => {
    if (estado !== 'procesando') return
    setSegundos(0)
    const t0 = performance.now()
    const id = setInterval(() => setSegundos(Math.floor((performance.now() - t0) / 1000)), 250)
    return () => clearInterval(id)
  }, [estado])

  const enviar = async (samples, sampleRate) => {
    setEstado('procesando')
    const t0 = performance.now()
    try {
      const wavBlob = encodeWav(samples, sampleRate)
      setInteraccion(await enviarPedido(wavBlob, sesionRef.current, seleccionRef.current))
      setTotalS((performance.now() - t0) / 1000)
    } catch (err) {
      setInteraccion(null)
      // El servidor dice qué etapa falló ("Transcripción (opencode-go): ..."): el respaldo es manual.
      const caido = /^(Transcripción|Intérprete) \(/.test(err.message)
      setError(
        'No se pudo procesar el pedido: ' + err.message +
          (caido ? ' Probá con otro proveedor o modelo en el selector.' : ''),
      )
      actualizarInstrumento()
      actualizarModelos(true)
    } finally {
      setEstado('idle')
      ocupadoRef.current = false
    }
  }

  const finalizar = async () => {
    const audioContext = audioContextRef.current
    if (!audioContext) return // ya finalizada
    audioContextRef.current = null
    processorRef.current?.disconnect()
    sourceRef.current?.disconnect()
    streamRef.current?.getTracks().forEach((track) => track.stop())

    const sampleRate = audioContext.sampleRate
    await audioContext.close()
    setNivel(0)

    if (performance.now() - inicioRef.current < DURACION_MINIMA_MS) {
      setAviso('Mantené presionado mientras hablás.')
      setEstado('idle')
      ocupadoRef.current = false
      return
    }
    await enviar(concatFloat32(chunksRef.current), sampleRate)
  }

  const presionar = async () => {
    if (ocupadoRef.current) return
    ocupadoRef.current = true
    presionadoRef.current = true
    setError('')
    setAviso('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      const audioContext = new AudioContext()
      audioContextRef.current = audioContext

      const source = audioContext.createMediaStreamSource(stream)
      sourceRef.current = source

      const processor = audioContext.createScriptProcessor(4096, 1, 1)
      processorRef.current = processor
      chunksRef.current = []

      processor.onaudioprocess = (event) => {
        const data = event.inputBuffer.getChannelData(0)
        chunksRef.current.push(new Float32Array(data))

        let sumaCuadrados = 0
        for (let i = 0; i < data.length; i++) sumaCuadrados += data[i] * data[i]
        const rms = Math.sqrt(sumaCuadrados / data.length)
        setNivel(Math.min(1, rms * 4)) // *4: el habla normal rara vez satura el rango [-1,1]
      }

      source.connect(processor)
      processor.connect(audioContext.destination)

      inicioRef.current = performance.now()
      setEstado('grabando')
    } catch (err) {
      setError('No se pudo acceder al micrófono: ' + err.message)
      setEstado('idle')
      ocupadoRef.current = false
      return
    }
    // Se soltó mientras el navegador abría el micrófono (o pedía el permiso): se corta ya, si no
    // queda grabando sin que nadie presione.
    if (!presionadoRef.current) await finalizar()
  }

  const soltar = () => {
    if (!presionadoRef.current) return
    presionadoRef.current = false
    finalizar()
  }

  // La barra espaciadora hace lo mismo que el botón. Los listeners se registran una vez y llaman
  // a la versión actual de cada función a través de refs.
  const presionarRef = useRef(presionar)
  const soltarRef = useRef(soltar)
  presionarRef.current = presionar
  soltarRef.current = soltar

  useEffect(() => {
    const abajo = (e) => {
      if (e.code !== 'Space') return
      e.preventDefault() // ni scroll ni "clic" en el botón que tenga el foco
      if (!e.repeat) presionarRef.current()
    }
    const arriba = (e) => {
      if (e.code !== 'Space') return
      e.preventDefault()
      soltarRef.current()
    }
    const perderFoco = () => soltarRef.current() // si la ventana pierde el foco no llega el keyup
    window.addEventListener('keydown', abajo)
    window.addEventListener('keyup', arriba)
    window.addEventListener('blur', perderFoco)
    return () => {
      window.removeEventListener('keydown', abajo)
      window.removeEventListener('keyup', arriba)
      window.removeEventListener('blur', perderFoco)
    }
  }, [])

  const reiniciarSesion = () => {
    setSesion(nuevaSesion())
    setInteraccion(null)
    setTotalS(null)
    setError('')
    setAviso('')
  }

  const grabando = estado === 'grabando'
  const procesando = estado === 'procesando'

  return (
    <>
      <h1>Prueba del sistema</h1>
      <LineaInstrumento instrumento={instrumento} revisando={revisando} onRevisar={actualizarInstrumento} />
      <Selectores
        catalogo={catalogoModelos}
        seleccion={seleccion}
        onCambiar={cambiarModelo}
        onActualizar={() => actualizarModelos(true)}
        actualizando={actualizandoModelos}
        deshabilitado={grabando || procesando}
      />

      <button
        className={`grabar${grabando ? ' presionado' : ''}`}
        onPointerDown={(e) => {
          if (e.button !== 0) return
          e.currentTarget.setPointerCapture(e.pointerId) // el soltar llega aunque el dedo se corra
          presionar()
        }}
        onPointerUp={soltar}
        onPointerCancel={soltar}
        onContextMenu={(e) => e.preventDefault()}
        disabled={procesando}
      >
        {grabando
          ? 'Grabando… soltá para enviar'
          : procesando
            ? `Procesando… ${segundos} s`
            : 'Mantené presionado para hablar'}
      </button>
      <p className="nota">o mantené presionada la barra espaciadora</p>

      {grabando && (
        <div className="medidor">
          <div className="medidor-nivel" style={{ transform: `scaleX(${nivel})` }} />
        </div>
      )}

      {procesando && (
        <p>
          <span className="spinner" /> Transcribiendo e interpretando…
        </p>
      )}

      {aviso && <p className="aviso">{aviso}</p>}
      {error && <p className="error">{error}</p>}

      {interaccion && !procesando && (
        <Resultado
          interaccion={interaccion}
          totalS={totalS}
          onActualizar={(nueva) => {
            setInteraccion(nueva)
            setTotalS(null)
          }}
          onError={setError}
        />
      )}

      <p className="sesion">
        Sesión <code>{sesion.slice(0, 8)}</code>{' '}
        <button className="secundario" onClick={reiniciarSesion} disabled={grabando || procesando}>
          Nueva sesión
        </button>
      </p>
    </>
  )
}
