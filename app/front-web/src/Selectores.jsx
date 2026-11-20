// Selector de proveedor y modelo por etapa (GET /modelos del servidor). El respaldo es manual: si un
// proveedor se cae, se elige otro acá. Qué proveedores y modelos hay lo decide
// servidor/src/servidor/proveedores.yaml; el front no tiene ninguna lista propia.

const ETAPAS = [
  ['asr', 'Transcripción'],
  ['interprete', 'Intérprete'],
]

// Sin la clave no puede andar: no tiene sentido elegirlo. "No responde" sí se puede elegir, porque
// el estado puede tener hasta 30 s de antigüedad.
const sinClave = (m) => m.motivo?.startsWith('Falta')

function estado(item) {
  return item.listo ? '✓' : '✗'
}

export function proveedorDe(catalogo, etapa, idModelo) {
  return catalogo[etapa].proveedores.find((p) => p.modelos.some((m) => m.id === idModelo))
}

export default function Selectores({ catalogo, seleccion, onCambiar, onActualizar, actualizando, deshabilitado }) {
  if (!catalogo) return <p className="salud">Cargando modelos…</p>
  if (catalogo.error) return <p className="salud salud-mal">No se pudo obtener la lista de modelos: {catalogo.error}</p>

  return (
    <div className="selectores">
      {ETAPAS.map(([etapa, titulo]) => {
        const proveedores = catalogo[etapa].proveedores
        const proveedor = proveedorDe(catalogo, etapa, seleccion[etapa]) ?? proveedores[0]
        const modelo = proveedor?.modelos.find((m) => m.id === seleccion[etapa])
        return (
          <div className="selector" key={etapa}>
            <span className="selector-etapa">{titulo}</span>
            <select
              aria-label={`Proveedor de ${titulo.toLowerCase()}`}
              value={proveedor?.id ?? ''}
              disabled={deshabilitado}
              onChange={(e) => {
                const nuevo = proveedores.find((p) => p.id === e.target.value)
                onCambiar(etapa, nuevo.predeterminado)
              }}
            >
              {proveedores.map((p) => (
                <option key={p.id} value={p.id} title={p.listo ? '' : 'Ningún modelo de este proveedor responde'}>
                  {p.nombre} {estado(p)}
                </option>
              ))}
            </select>
            <select
              aria-label={`Modelo de ${titulo.toLowerCase()}`}
              value={seleccion[etapa] ?? ''}
              disabled={deshabilitado}
              onChange={(e) => onCambiar(etapa, e.target.value)}
            >
              {proveedor?.modelos.map((m) => (
                <option key={m.id} value={m.id} disabled={sinClave(m)} title={m.motivo ?? ''}>
                  {m.nombre} {estado(m)}
                </option>
              ))}
            </select>
            {modelo && !modelo.listo && <small className="selector-motivo">{modelo.motivo}</small>}
          </div>
        )
      })}
      <button className="secundario" onClick={onActualizar} disabled={actualizando || deshabilitado}>
        {actualizando ? 'Consultando…' : '↻ Actualizar disponibilidad'}
      </button>
    </div>
  )
}
