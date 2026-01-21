// Adapted from https://github.com/baixin1228/web-scrcpy (MIT)
// Parses the scrcpy video stream: device name header, screen size header,
// then a sequence of NAL units. Calls onNaluCallback with typed events.

class VideoParser {
    constructor(onNaluCallback, debug = false) {
        this.debug = debug;
        this.buffer = new Uint8Array(0);
        this.name = null;
        this.width = null;
        this.height = null;
        this.sps = null;
        this.pps = null;
        this.onNaluCallback = onNaluCallback;
    }

    appendData(data) {
        const newBuffer = new Uint8Array(this.buffer.length + data.length);
        newBuffer.set(this.buffer, 0);
        newBuffer.set(data, this.buffer.length);
        this.buffer = newBuffer;
        this._processBuffer();
    }

    _processBuffer() {
        let startIndex = 0;

        if (this.name === null) {
            if (this.buffer.length >= 64) {
                const name = this.buffer.slice(0, 64);
                this.name = new TextDecoder().decode(name);
                console.log('Device name:', this.name);
                this.onNaluCallback({ type: 'name', data: { name: this.name } });
                startIndex = 64;
            }
        } else if (this.width === null) {
            if (this.buffer.length >= 12) {
                this.width = new DataView(this.buffer.buffer).getInt32(4, false);
                this.height = new DataView(this.buffer.buffer).getInt32(8, false);
                console.log('Screen size:', this.width, 'x', this.height);
                this.onNaluCallback({
                    type: 'screen_size',
                    data: { width: this.width, height: this.height },
                });
                startIndex += 12;
            }
        } else {
            while (this.buffer.length - startIndex > 12) {
                const size = new DataView(this.buffer.buffer).getInt32(startIndex + 8, false);
                if (this.buffer.length - startIndex >= 12 + size) {
                    const nalu = this.buffer.slice(startIndex + 12, startIndex + 12 + size);
                    this._processNalu(nalu);
                    startIndex += 12 + size;
                } else {
                    break;
                }
            }
        }

        this.buffer = this.buffer.slice(startIndex);
    }

    _findSequence(arr, sequence, startIndex = 0) {
        const seqLen = sequence.length;
        for (let i = startIndex; i <= arr.length - seqLen; i++) {
            let match = true;
            for (let j = 0; j < seqLen; j++) {
                if (arr[i + j] !== sequence[j]) { match = false; break; }
            }
            if (match) return i;
        }
        return -1;
    }

    _processNalu(nalu) {
        const naluType = nalu[4] & 0x1f;

        if (naluType === 7) {  // SPS
            const nextPos = this._findSequence(nalu, [0, 0, 0, 1], 5);
            if (nextPos > 0) {
                this.sps = nalu.slice(0, nextPos);
                this._processNalu(nalu.slice(nextPos));
            } else {
                this.sps = nalu;
            }
            const ret = SPSParser.parseSPS(this.sps.slice(4));
            this.onNaluCallback({
                type: 'size_change',
                data: { width: ret.present_size.width, height: ret.present_size.height },
            });
            return;
        }

        if (naluType === 8) {  // PPS
            const nextPos = this._findSequence(nalu, [0, 0, 0, 1], 5);
            if (nextPos > 0) {
                this.pps = nalu.slice(0, nextPos);
                this._processNalu(nalu.slice(nextPos));
            } else {
                this.pps = nalu;
            }
            return;
        }

        if (this.sps !== null && this.pps !== null) {
            this.onNaluCallback({
                type: 'init',
                data: { sps: this.sps, pps: this.pps },
            });
            this.sps = null;
            this.pps = null;
        }

        this.onNaluCallback({ type: 'nalu', data: nalu });
    }
}
