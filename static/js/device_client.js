/**
 * DeviceClient — orchestrates WebSocket connection, video decoding, and input
 * for a single Android device.
 *
 * Usage (from device.html):
 *   const client = new DeviceClient(serial, videoEl);
 *   client.connect();
 */
class DeviceClient {
    /**
     * @param {string} serial       - URL-encoded device serial number
     * @param {HTMLVideoElement} videoEl - <video> element to render into
     */
    constructor(serial, videoEl) {
        this.serial = serial;
        this.videoEl = videoEl;

        this._ws = null;
        this._jmuxer = null;
        this._input = null;
        this._connected = false;
    }

    connect() {
        const proto = location.protocol === 'https:' ? 'wss' : 'ws';
        const url = `${proto}://${location.host}/ws/${this.serial}`;

        this._ws = new WebSocket(url);
        this._ws.binaryType = 'arraybuffer';

        this._ws.onopen = () => {
            console.log(`[${this.serial}] WebSocket connected`);
            this._connected = true;
            this._showStatus('Connecting to device…');
        };

        this._ws.onmessage = (event) => {
            const data = new Uint8Array(event.data);
            if (this._parser) {
                this._parser.appendData(data);
            }
        };

        this._ws.onclose = (event) => {
            console.log(`[${this.serial}] WebSocket closed`, event.code, event.reason);
            this._connected = false;
            this._showStatus(`Disconnected (${event.reason || event.code})`);
        };

        this._ws.onerror = (err) => {
            console.error(`[${this.serial}] WebSocket error`, err);
            this._showStatus('Connection error');
        };

        this._initParser();
    }

    disconnect() {
        if (this._ws) {
            this._ws.close();
            this._ws = null;
        }
        if (this._jmuxer) {
            this._jmuxer.destroy();
            this._jmuxer = null;
        }
    }

    // ------------------------------------------------------------------

    _initParser() {
        this._parser = new VideoParser((event) => {
            switch (event.type) {
                case 'name':
                    console.log(`[${this.serial}] Device name:`, event.data.name);
                    break;

                case 'screen_size':
                    this._onScreenSize(event.data.width, event.data.height);
                    break;

                case 'size_change':
                    this._onScreenSize(event.data.width, event.data.height);
                    break;

                case 'init':
                    this._initJmuxer(event.data.sps, event.data.pps);
                    break;

                case 'nalu':
                    if (this._jmuxer) {
                        this._jmuxer.feed({ video: event.data });
                    }
                    break;

                case 'device_disconnected':
                    this._showStatus('Device disconnected');
                    break;
            }
        });
    }

    _onScreenSize(width, height) {
        console.log(`[${this.serial}] Screen size: ${width}x${height}`);
        this.videoEl.width = width;
        this.videoEl.height = height;

        if (this._input) {
            this._input.resizeScreen(width, height);
        } else {
            this._initInput(width, height);
        }
        this._showStatus('');
    }

    _initJmuxer(sps, pps) {
        if (this._jmuxer) {
            this._jmuxer.destroy();
        }
        this._jmuxer = new JMuxer({
            node: this.videoEl,
            mode: 'video',
            flushingTime: 0,
            clearBuffer: true,
            onError: (data) => console.error(`[${this.serial}] JMuxer error`, data),
        });
        // Feed SPS+PPS immediately so the MSE codec string is set
        this._jmuxer.feed({ video: new Uint8Array([...sps, ...pps]) });
    }

    _initInput(width, height) {
        this._input = new ScrcpyInput(
            (data) => this._sendControl(data),
            this.videoEl,
            width,
            height,
        );
    }

    _sendControl(data) {
        if (this._ws && this._ws.readyState === WebSocket.OPEN) {
            this._ws.send(data);
        }
    }

    _showStatus(message) {
        const el = document.getElementById('status-message');
        if (el) {
            el.textContent = message;
            el.style.display = message ? 'block' : 'none';
        }
    }
}
