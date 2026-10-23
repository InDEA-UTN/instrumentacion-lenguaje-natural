import { useRef, useState } from 'react'
import { concatFloat32, encodeWav } from './wav.js'

const WHISPER_URL = 'http://localhost:8080/inference'

export default function App() {
  const [estado, setEstado] = useState('idle') // idle | grabando | procesando | listo | error
  const [texto, setTexto] = useState('')
  const [error, setError] = useState('')
  const [nivel, setNivel] = useState(0) // 0..1, volumen detectado mientras se graba

  const audioContextRef = useRef(null)
  const streamRef = useRef(null)
  const processorRef = useRef(null)
  const sourceRef = useRef(null)
  const chunksRef = useRef([])

  const grabar = async () => {
    setError('')
    setTexto('')
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

      setEstado('grabando')
    } catch (err) {
      setError('No se pudo acceder al micrófono: ' + err.message)
      setEstado('error')
    }
  }

  const detener = async () => {
    const audioContext = audioContextRef.current
    processorRef.current?.disconnect()
    sourceRef.current?.disconnect()
    streamRef.current?.getTracks().forEach((track) => track.stop())

    const sampleRate = audioContext.sampleRate
    await audioContext.close()

    setNivel(0)
    setEstado('procesando')

    try {
      const samples = concatFloat32(chunksRef.current)
      const wavBlob = encodeWav(samples, sampleRate)

      const formData = new FormData()
      formData.append('file', wavBlob, 'audio.wav')
      formData.append('language', 'es')

      const respuesta = await fetch(WHISPER_URL, { method: 'POST', body: formData })
      if (!respuesta.ok) {
        throw new Error(`el servidor respondió ${respuesta.status}`)
      }
      const datos = await respuesta.json()
      setTexto(datos.text ?? JSON.stringify(datos))
      setEstado('listo')
    } catch (err) {
      setError('No se pudo transcribir: ' + err.message)
      setEstado('error')
    }
  }

  const grabando = estado === 'grabando'
  const procesando = estado === 'procesando'

  return (
    <>
      <h1>Prueba de transcripción</h1>
      <button
        onClick={grabando ? detener : grabar}
        disabled={procesando}
      >
        {grabando ? 'Detener' : 'Grabar'}
      </button>

      {grabando && (
        <div className="medidor">
          <div className="medidor-nivel" style={{ transform: `scaleX(${nivel})` }} />
        </div>
      )}

      {procesando && (
        <p>
          <span className="spinner" /> Procesando audio...
        </p>
      )}

      {error && <p className="error">{error}</p>}

      {estado === 'listo' && (
        <div className="resultado">
          <strong>Transcripción:</strong>
          <p>{texto}</p>
        </div>
      )}
    </>
  )
}
