// Adapted from https://github.com/baixin1228/web-scrcpy (MIT)
// Converts browser mouse/keyboard/wheel events into scrcpy binary protocol buffers.

class ScrcpyInput {
    constructor(callback, videoElement, width, height, debug = false) {
        this.callback = callback;
        this.width = width;
        this.height = height;
        this.debug = debug;

        let mouseX = null;
        let mouseY = null;
        let leftButtonIsPressed = false;
        let rightButtonIsPressed = false;

        document.addEventListener('mousedown', (event) => {
            const rect = videoElement.getBoundingClientRect();
            const local_x = event.clientX - rect.left;
            const local_y = event.clientY - rect.top;

            if (videoElement.contains(event.target)) {
                if (event.button === 0) {
                    leftButtonIsPressed = true;
                    mouseX = (local_x / (rect.right - rect.left)) * this.width;
                    mouseY = (local_y / (rect.bottom - rect.top)) * this.height;
                    this.callback(this.createTouchProtocolData(0, mouseX, mouseY, this.width, this.height, 0, 0, 65535));
                } else if (event.button === 2) {
                    rightButtonIsPressed = true;
                    this._sendKeyCode(event, 0, 4);
                    event.preventDefault();
                }
            }
        });

        document.addEventListener('mouseup', (event) => {
            if (!leftButtonIsPressed) return;
            const rect = videoElement.getBoundingClientRect();
            const local_x = event.clientX - rect.left;
            const local_y = event.clientY - rect.top;

            if (event.button === 0) {
                leftButtonIsPressed = false;
                if (videoElement.contains(event.target)) {
                    mouseX = (local_x / (rect.right - rect.left)) * this.width;
                    mouseY = (local_y / (rect.bottom - rect.top)) * this.height;
                }
                this.callback(this.createTouchProtocolData(1, mouseX, mouseY, this.width, this.height, 0, 0, 0));
            } else if (event.button === 2 && rightButtonIsPressed) {
                rightButtonIsPressed = false;
                this._sendKeyCode(event, 1, 4);
                event.preventDefault();
            }
        });

        document.addEventListener('mousemove', (event) => {
            if (!leftButtonIsPressed) return;
            const rect = videoElement.getBoundingClientRect();
            const local_x = event.clientX - rect.left;
            const local_y = event.clientY - rect.top;
            if (videoElement.contains(event.target)) {
                mouseX = (local_x / (rect.right - rect.left)) * this.width;
                mouseY = (local_y / (rect.bottom - rect.top)) * this.height;
                this.callback(this.createTouchProtocolData(2, mouseX, mouseY, this.width, this.height, 0, 0, 65535));
            }
        });

        videoElement.addEventListener('contextmenu', (event) => event.preventDefault());

        videoElement.addEventListener('wheel', (event) => {
            const rect = videoElement.getBoundingClientRect();
            const relativeX = event.clientX - rect.left;
            const relativeY = event.clientY - rect.top;
            this.callback(this.createScrollProtocolData(
                relativeX, relativeY,
                rect.right - rect.left, rect.bottom - rect.top,
                event.deltaX, event.deltaY, event.button,
            ));
        });

        videoElement.addEventListener('keydown', async (event) => {
            const keyCode = this._mapToAndroidKeyCode(event);
            if (keyCode !== null) {
                this._sendKeyCode(event, 0, keyCode);
            } else {
                if (this.debug) console.log(`Unmapped key: ${event.code}`);
            }
        });

        videoElement.addEventListener('keyup', (event) => {
            const keyCode = this._mapToAndroidKeyCode(event);
            if (keyCode !== null) {
                this._sendKeyCode(event, 1, keyCode);
            }
        });
    }

    resizeScreen(width, height) {
        this.width = width;
        this.height = height;
    }

    _mapToAndroidKeyCode(event) {
        const map = {
            'KeyA': 29, 'KeyB': 30, 'KeyC': 31, 'KeyD': 32, 'KeyE': 33,
            'KeyF': 34, 'KeyG': 35, 'KeyH': 36, 'KeyI': 37, 'KeyJ': 38,
            'KeyK': 39, 'KeyL': 40, 'KeyM': 41, 'KeyN': 42, 'KeyO': 43,
            'KeyP': 44, 'KeyQ': 45, 'KeyR': 46, 'KeyS': 47, 'KeyT': 48,
            'KeyU': 49, 'KeyV': 50, 'KeyW': 51, 'KeyX': 52, 'KeyY': 53, 'KeyZ': 54,
            'Digit0': 7, 'Digit1': 8, 'Digit2': 9, 'Digit3': 10, 'Digit4': 11,
            'Digit5': 12, 'Digit6': 13, 'Digit7': 14, 'Digit8': 15, 'Digit9': 16,
            'Enter': 66, 'Backspace': 67, 'Tab': 61, 'Space': 62,
            'Escape': 111, 'CapsLock': 115, 'NumLock': 143, 'ScrollLock': 116,
            'ArrowUp': 19, 'ArrowDown': 20, 'ArrowLeft': 21, 'ArrowRight': 22,
            'ShiftLeft': 59, 'ShiftRight': 60,
            'ControlLeft': 113, 'ControlRight': 114,
            'AltLeft': 57, 'AltRight': 58,
            'MetaLeft': 117, 'MetaRight': 118,
            'Numpad0': 144, 'Numpad1': 145, 'Numpad2': 146, 'Numpad3': 147,
            'Numpad4': 148, 'Numpad5': 149, 'Numpad6': 150, 'Numpad7': 151,
            'Numpad8': 152, 'Numpad9': 153, 'NumpadEnter': 160,
            'NumpadAdd': 157, 'NumpadSubtract': 156,
            'NumpadMultiply': 155, 'NumpadDivide': 154,
            'F1': 131, 'F2': 132, 'F3': 133, 'F4': 134, 'F5': 135, 'F6': 136,
            'F7': 137, 'F8': 138, 'F9': 139, 'F10': 140, 'F11': 141, 'F12': 142,
            'Back': 4, 'Home': 3, 'Menu': 82,
        };
        return map[event.code] !== undefined ? map[event.code] : null;
    }

    _sendKeyCode(keyEvent, action, keycode) {
        let metakey = 0;
        if (keyEvent.shiftKey)   metakey |= 0x40;
        if (keyEvent.ctrlKey)    metakey |= 0x2000;
        if (keyEvent.altKey)     metakey |= 0x10;
        if (keyEvent.metaKey)    metakey |= 0x20000;
        if (keyEvent.getModifierState && keyEvent.getModifierState('CapsLock')) metakey |= 0x100000;
        if (keyEvent.getModifierState && keyEvent.getModifierState('NumLock'))  metakey |= 0x200000;
        this.callback(this.createKeyProtocolData(action, keycode, keyEvent.repeat, metakey));
    }

    createTouchProtocolData(action, x, y, width, height, actionButton, buttons, pressure) {
        const buffer = new ArrayBuffer(1 + 1 + 8 + 4 + 4 + 2 + 2 + 2 + 4 + 4);
        const view = new DataView(buffer);
        let off = 0;
        view.setUint8(off++, 2);  // type: touch
        view.setUint8(off++, action);
        // pointer ID: 0xFFFFFFFFFFFFFFFD
        view.setUint8(off++, 0xff); view.setUint8(off++, 0xff); view.setUint8(off++, 0xff);
        view.setUint8(off++, 0xff); view.setUint8(off++, 0xff); view.setUint8(off++, 0xff);
        view.setUint8(off++, 0xff); view.setUint8(off++, 0xfd);
        view.setInt32(off, x, false);    off += 4;
        view.setInt32(off, y, false);    off += 4;
        view.setUint16(off, width, false);  off += 2;
        view.setUint16(off, height, false); off += 2;
        view.setInt16(off, pressure, false); off += 2;
        view.setInt32(off, actionButton, false); off += 4;
        view.setInt32(off, buttons, false);
        return buffer;
    }

    createKeyProtocolData(action, keycode, repeat, metaState) {
        const buffer = new ArrayBuffer(1 + 1 + 4 + 4 + 4);
        const view = new DataView(buffer);
        let off = 0;
        view.setUint8(off++, 0);  // type: key
        view.setUint8(off++, action);
        view.setInt32(off, keycode, false);   off += 4;
        view.setInt32(off, repeat, false);    off += 4;
        view.setInt32(off, metaState, false);
        return buffer;
    }

    createScrollProtocolData(x, y, width, height, hScroll, vScroll, button) {
        const buffer = new ArrayBuffer(1 + 4 + 4 + 2 + 2 + 2 + 2 + 4);
        const view = new DataView(buffer);
        let off = 0;
        view.setUint8(off++, 3);  // type: scroll
        view.setInt32(off, x, false);       off += 4;
        view.setInt32(off, y, false);       off += 4;
        view.setUint16(off, width, false);  off += 2;
        view.setUint16(off, height, false); off += 2;
        view.setInt16(off, hScroll, false); off += 2;
        view.setInt16(off, vScroll, false); off += 2;
        view.setInt32(off, button, false);
        return buffer;
    }

    screen_on_off(action) {
        const buffer = new ArrayBuffer(2);
        const view = new DataView(buffer);
        view.setUint8(0, 4);  // type: screen
        view.setUint8(1, action);
        this.callback(buffer);
    }
}
