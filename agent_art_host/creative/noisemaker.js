// Native Noisemaker program execution. This adapter never translates shader code.
import { CanvasRenderer } from '../vendor/noisemaker/shaders/src/renderer/canvas.js';

function flipRows(values, width, height) {
  const output = new values.constructor(values.length);
  for (let y = 0; y < height; y++) output.set(values.subarray(y*width*4, (y+1)*width*4), (height-y-1)*width*4);
  return output;
}

function upload(backend, id, values) {
  const tex = backend.textures.get(id);
  if (!tex) throw new Error(`Missing input texture ${id}`);
  if (backend.device) {
    const data = tex.gpuFormat === 'rgba16float' ? new Float16Array(values) : values;
    if (!['rgba16float', 'rgba32float'].includes(tex.gpuFormat)) throw new Error(`Not a float input: ${tex.gpuFormat}`);
    backend.queue.writeTexture({texture: tex.handle}, data,
      {bytesPerRow: tex.width * 4 * data.BYTES_PER_ELEMENT}, {width: tex.width, height: tex.height});
  } else {
    const gl = backend.gl;
    gl.bindTexture(gl.TEXTURE_2D, tex.handle);
    gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, tex.width, tex.height, gl.RGBA, gl.FLOAT, flipRows(values, tex.width, tex.height));
    if (gl.getError() !== gl.NO_ERROR) throw new Error('Float texture upload failed');
  }
}

async function readFloat(backend, id) {
  const tex = backend.textures.get(id);
  const {width, height} = tex;
  if (backend.device) {
    const bytes = tex.gpuFormat === 'rgba16float' ? 2 : tex.gpuFormat === 'rgba32float' ? 4 : 0;
    if (!bytes) throw new Error(`Not a float output: ${tex.gpuFormat}`);
    const stride = Math.ceil(width*4*bytes/256)*256;
    const staging = backend.device.createBuffer({size: stride*height, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ});
    try {
      const encoder = backend.device.createCommandEncoder();
      encoder.copyTextureToBuffer({texture: tex.handle}, {buffer: staging, bytesPerRow: stride}, {width, height});
      backend.queue.submit([encoder.finish()]);
      await staging.mapAsync(GPUMapMode.READ);
      const view = bytes === 2 ? new Float16Array(staging.getMappedRange()) : new Float32Array(staging.getMappedRange());
      const output = new Float32Array(width*height*4);
      for (let y = 0; y < height; y++) output.set(view.subarray(y*stride/bytes, y*stride/bytes+width*4), y*width*4);
      staging.unmap();
      return {values: output, format: tex.gpuFormat};
    } finally { staging.destroy(); }
  }
  const gl = backend.gl;
  const previous = gl.getParameter(gl.FRAMEBUFFER_BINDING);
  const fbo = gl.createFramebuffer();
  try {
    gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex.handle, 0);
    if (gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== gl.FRAMEBUFFER_COMPLETE) throw new Error('Incomplete float readback framebuffer');
    const values = new Float32Array(width*height*4);
    gl.readPixels(0, 0, width, height, gl.RGBA, gl.FLOAT, values);
    if (gl.getError() !== gl.NO_ERROR) throw new Error('Float readback failed');
    return {values: flipRows(values, width, height), format: tex.format};
  } finally { gl.bindFramebuffer(gl.FRAMEBUFFER, previous); gl.deleteFramebuffer(fbo); }
}

window.runArtProgram = async (job) => {
  const canvas = document.querySelector('canvas');
  const errors = [];
  const renderer = new CanvasRenderer({canvas, width: job.width, height: job.height,
    basePath: new URL('../vendor/noisemaker/shaders', location.href).href, preferWebGPU: job.backend === 'webgpu',
    onError: e => errors.push(String(e))});
  const started = performance.now();
  try {
    await renderer.loadManifest();
    await renderer.loadEffects(job.effects);
    await renderer.compile(job.dsl);
    renderer.stop();
    const pipeline = renderer.pipeline;
    const backend = pipeline.backend;
    const actual = backend.device ? 'webgpu' : 'webgl2';
    if (actual !== job.backend) throw new Error(`Requested ${job.backend}, received ${actual}; no silent fallback`);
    for (const name of job.inputs) {
      const values = new Float32Array(await (await fetch(`/transfer/input/${name}`)).arrayBuffer());
      if (values.length !== job.width*job.height*4) throw new Error(`Input ${name} has wrong shape`);
      const surface = pipeline.surfaces.get(name);
      if (!surface) throw new Error(`Program has no surface ${name}`);
      upload(backend, surface.read, values);
      upload(backend, surface.write, values);
    }
    const frames = [];
    for (let i = 0; i < job.times.length; i++) {
      if (job.parameters) renderer.applyStepParameterValues(job.parameters);
      // Direct pipeline call propagates errors instead of CanvasRenderer's logged catch.
      pipeline.render(job.times[i]);
      const surface = pipeline.surfaces.get(job.output);
      if (!surface) throw new Error(`No output surface ${job.output}`);
      const {values, format} = await readFloat(backend, surface.read);
      const response = await fetch(`/transfer/output/${i}`, {method: 'POST', body: values});
      if (!response.ok) throw new Error('Could not store float output');
      frames.push({format, time: job.times[i], passes: pipeline.lastPassCount});
    }
    if (errors.length) throw new Error(errors.join('\n'));
    return {backend: actual, seconds: (performance.now()-started)/1000, frames};
  } finally { renderer.dispose(); }
};
