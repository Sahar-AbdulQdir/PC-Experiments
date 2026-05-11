/*
 * WebSerial connector
 * Exposes window.port.send(...) and dispatches incoming Arduino
 * messages via window.onArduinoMessage (set by sketch.js).
 */
window.port = null;
window.onArduinoMessage = null;

document.addEventListener('DOMContentLoaded', () => {
  const connectBtn = document.getElementById('connect');

  connectBtn.addEventListener('click', async () => {
    if (window.port) {
      try { await window.port.close(); } catch (e) {}
      window.port = null;
      connectBtn.querySelector('span').textContent = 'Connect Arduino';
      return;
    }

    try {
      const selected = await navigator.serial.requestPort();
      await selected.open({ baudRate: 9600 });

      const writer = selected.writable.getWriter();
      const reader = selected.readable.getReader();

      window.port = {
        send: async (data) => {
          if (typeof data === 'string') data = new TextEncoder().encode(data);
          await writer.write(data);
        },
        close: async () => {
          try { await writer.close(); } catch(e){}
          try { await reader.cancel(); } catch(e){}
          await selected.close();
        }
      };

      // Buffered line reader (Arduino sends line-by-line)
      (async () => {
        const decoder = new TextDecoder();
        let buffer = '';
        try {
          while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            if (value) {
              buffer += decoder.decode(value);
              let idx;
              while ((idx = buffer.indexOf('\n')) >= 0) {
                const line = buffer.slice(0, idx).trim();
                buffer = buffer.slice(idx + 1);
                if (line) {
                  console.log('[Arduino]', line);
                  if (typeof window.onArduinoMessage === 'function') {
                    window.onArduinoMessage(line);
                  }
                }
              }
            }
          }
        } catch (e) { console.warn(e); }
      })();

      connectBtn.querySelector('span').textContent = 'Disconnect';
      console.log('Arduino connected.');
    } catch (e) {
      console.error('Connection failed:', e);
      alert('Could not connect. Make sure your browser supports WebSerial (Chrome/Edge).');
    }
  });
});
