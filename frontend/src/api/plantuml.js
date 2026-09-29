/**
 * PlantUML text encoding.
 *
 * The official PlantUML server renders a diagram from a URL that carries the
 * source compressed and re-encoded. This module reproduces that encoding:
 * DEFLATE (RFC 1951) the UTF-8 bytes, then base64-encode the result with
 * PlantUML's own alphabet.
 *
 * Note: rendering this way means the diagram source is sent to whatever
 * server `VITE_PLANTUML_SERVER` points at. Point it at a local PlantUML
 * instance to keep the source on your machine.
 */

const ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_'

/** PlantUML server base URL (no trailing slash). */
export const plantUmlServer = (
  import.meta.env.VITE_PLANTUML_SERVER || 'https://www.plantuml.com/plantuml'
).replace(/\/+$/, '')

function encode6bit(value) {
  return ALPHABET.charAt(value & 0x3f)
}

function append3bytes(b1, b2, b3) {
  const c1 = b1 >> 2
  const c2 = ((b1 & 0x03) << 4) | (b2 >> 4)
  const c3 = ((b2 & 0x0f) << 2) | (b3 >> 6)
  const c4 = b3 & 0x3f
  return encode6bit(c1) + encode6bit(c2) + encode6bit(c3) + encode6bit(c4)
}

async function deflateRaw(bytes) {
  if (typeof CompressionStream === 'undefined') {
    throw new Error('This browser lacks CompressionStream support, so PlantUML cannot be encoded.')
  }
  const stream = new Blob([bytes]).stream().pipeThrough(new CompressionStream('deflate-raw'))
  return new Uint8Array(await new Response(stream).arrayBuffer())
}

/**
 * Encode PlantUML source the way the PlantUML server expects.
 *
 * @param {string} source
 * @returns {Promise<string>}
 */
export async function encodePlantUml(source) {
  const data = await deflateRaw(new TextEncoder().encode(source))
  let encoded = ''
  for (let i = 0; i < data.length; i += 3) {
    if (i + 2 === data.length) {
      encoded += append3bytes(data[i], data[i + 1], 0)
    } else if (i + 1 === data.length) {
      encoded += append3bytes(data[i], 0, 0)
    } else {
      encoded += append3bytes(data[i], data[i + 1], data[i + 2])
    }
  }
  return encoded
}

/**
 * @param {string} encoded
 * @returns {string} URL returning the rendered diagram as SVG.
 */
export function plantUmlSvgUrl(encoded) {
  return `${plantUmlServer}/svg/${encoded}`
}
