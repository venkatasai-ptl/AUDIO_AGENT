class PCMCollector extends AudioWorkletProcessor {
    constructor(opts) {
        super();
        const { targetSampleRate = 16000, frameMs = 30 } = opts.processorOptions || {};
        this.target = targetSampleRate;
        this.frameSamples = Math.round(targetSampleRate * frameMs / 1000); // 480
        this.buf = new Float32Array(0);
        this.frac = 0; this.prev = 0; // resampler state
    }
    resample(mono) {
        const inHz = sampleRate;
        if (inHz === this.target) return mono;
        const ratio = this.target / inHz, outLen = Math.floor((mono.length + 1) * ratio);
        const out = new Float32Array(outLen);
        let t = this.frac, last = this.prev;
        for (let o = 0; o < outLen; o++) {
            const i = Math.floor(t), f = t - i;
            const s0 = (i === -1) ? last : (mono[i] ?? mono[mono.length - 1] ?? 0);
            const s1 = mono[i + 1] ?? mono[mono.length - 1] ?? s0;
            out[o] = s0 + (s1 - s0) * f;
            t += 1 / ratio;
            if (Math.floor(t) >= mono.length) break;
        }
        this.frac = t - Math.floor(t);
        this.prev = mono[mono.length - 1] ?? this.prev;
        return out;
    }
    emit() {
        while (this.buf.length >= this.frameSamples) {
            const frame = this.buf.subarray(0, this.frameSamples);
            const i16 = new Int16Array(frame.length);
            for (let i = 0; i < frame.length; i++) {
                let s = Math.max(-1, Math.min(1, frame[i]));
                i16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
            }
            this.port.postMessage({ type: 'frame', bytes: new Uint8Array(i16.buffer) });
            const rem = this.buf.length - this.frameSamples;
            const tmp = new Float32Array(rem);
            tmp.set(this.buf.subarray(this.frameSamples));
            this.buf = tmp;
        }
    }
    process(inputs) {
        const chs = inputs[0]; if (!chs || chs.length === 0) return true;
        const len = chs[0]?.length || 0, mono = new Float32Array(len);
        for (let i = 0; i < len; i++) { let acc = 0; for (let c = 0; c < chs.length; c++) acc += chs[c][i] || 0; mono[i] = acc / Math.max(1, chs.length); }
        const res = this.resample(mono);
        const comb = new Float32Array(this.buf.length + res.length);
        comb.set(this.buf, 0); comb.set(res, this.buf.length); this.buf = comb;
        this.emit();
        return true;
    }
}
registerProcessor('pcm_collector', PCMCollector);
