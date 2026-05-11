/*
 * AI Smart Sorter - p5.js sketch
 * Workflow:
 *   1. Open page -> camera + model load
 *   2. Connect Arduino (button in header)
 *   3. Press the PHYSICAL button on the Arduino board
 *      -> Arduino sends "STATE:ARMED" -> classification loop begins.
 *      -> Press again to disarm.
 */

// =====================================================
// CONFIGURATION
// =====================================================
const MODEL_URL       = 'https://teachablemachine.withgoogle.com/models/PASTE_YOUR_ID_HERE/';
const CONF_THRESHOLD  = 0.90;
const COOLDOWN_MS     = 2500;
const WIGGLE_COOLDOWN = 1500;

// =====================================================
let classifier;
let video;
let labels = [];
let isModelLoaded = false;
let isVideoReady  = false;
let isArmed       = false;      // controlled by Arduino's button
let lastSentTime    = 0;
let lastWiggleTime  = 0;
let logEntries = [];

// DOM refs
let statusDiv;
let bar1, bar2, pct1, pct2, label1, label2;
let ledGreen, ledRed, buzzer, btnIcon;
let servoArm, angleText, lastDet;
let logBody, downloadBtn, clearBtn;
let armBadge, armLabel, hint;

// =====================================================
// SETUP
// =====================================================
function setup() {
  noCanvas();

  statusDiv   = document.getElementById('status');
  bar1        = document.getElementById('bar1');
  bar2        = document.getElementById('bar2');
  pct1        = document.getElementById('pct1');
  pct2        = document.getElementById('pct2');
  label1      = document.getElementById('label1');
  label2      = document.getElementById('label2');
  ledGreen    = document.getElementById('ledGreen');
  ledRed      = document.getElementById('ledRed');
  buzzer      = document.getElementById('buzzer');
  btnIcon     = document.getElementById('btnIcon');
  servoArm    = document.getElementById('servoArm');
  angleText   = document.getElementById('angleText');
  lastDet     = document.getElementById('lastDet');
  logBody     = document.getElementById('logBody');
  downloadBtn = document.getElementById('downloadBtn');
  clearBtn    = document.getElementById('clearBtn');
  armBadge    = document.getElementById('armBadge');
  armLabel    = document.getElementById('armLabel');
  hint        = document.getElementById('hint');

  downloadBtn.addEventListener('click', downloadCSV);
  clearBtn.addEventListener('click', clearLog);

  // Listen for Arduino messages
  window.onArduinoMessage = onArduinoMessage;

  setStatus('starting camera');
  video = createCapture(VIDEO, () => {
    isVideoReady = true;
    setStatus(isModelLoaded ? 'ready - press button on board' : 'loading model');
  });
  video.size(640, 480);
  video.parent('videoBox');
  video.elt.setAttribute('playsinline', '');
  video.elt.setAttribute('autoplay', '');
  video.elt.muted = true;

  initClassifier();
}

// =====================================================
// MODEL LOADING
// =====================================================
function initClassifier() {
  if (!MODEL_URL || MODEL_URL.includes('PASTE_YOUR_ID_HERE')) {
    setStatus('set MODEL_URL in sketch.js');
    return;
  }
  const cleanUrl = MODEL_URL.endsWith('/') ? MODEL_URL : MODEL_URL + '/';

  httpGet(cleanUrl + 'metadata.json', 'json',
    (response) => {
      labels = (response && response.labels) ? response.labels : ['class1', 'class2'];
      if (label1) label1.textContent = labels[0] || 'class1';
      if (label2) label2.textContent = labels[1] || 'class2';

      try {
        classifier = ml5.imageClassifier(cleanUrl + 'model.json', () => {
          isModelLoaded = true;
          setStatus(isVideoReady ? 'ready - press button on board' : 'starting camera');
          // Start the classify loop immediately so confidence bars work
          // even before the user arms the system. Sorting is gated by isArmed.
          classifyVideo();
        });
      } catch (e) {
        console.error(e);
        setStatus('could not load model');
      }
    },
    (err) => {
      console.error('metadata.json error:', err);
      setStatus('invalid model url');
    }
  );
}

// =====================================================
// ARDUINO MESSAGES
// =====================================================
function onArduinoMessage(line) {
  if (line.includes('STATE:ARMED')) {
    isArmed = true;
    armBadge.classList.remove('idle');
    armBadge.classList.add('armed');
    armLabel.textContent = 'ARMED';
    btnIcon.classList.add('pressed');
    setStatus('sorting active');
    if (hint) hint.classList.add('hidden');
  } else if (line.includes('STATE:IDLE')) {
    isArmed = false;
    armBadge.classList.remove('armed');
    armBadge.classList.add('idle');
    armLabel.textContent = 'IDLE';
    btnIcon.classList.remove('pressed');
    setStatus('paused - press button on board');
    updateBars(0, 0);
  }
}

// =====================================================
// CLASSIFICATION LOOP
// =====================================================
function classifyVideo() {
  if (!isModelLoaded || !isVideoReady || !classifier) return;
  if (!video.elt || video.elt.readyState < 2) {
    setTimeout(classifyVideo, 150);
    return;
  }
  classifier.classify(video, gotResult);
}

function gotResult(error, results) {
  if (error)   { console.error(error); setTimeout(classifyVideo, 200); return; }
  if (!results || results.length === 0) { classifyVideo(); return; }

  const c1 = findConf(results, labels[0]);
  const c2 = findConf(results, labels[1]);
  updateBars(c1, c2);

  // Only act on classifications when armed
  if (isArmed) {
    const top = Math.max(c1, c2);
    const now = millis();

    // Thinking wiggle when something interesting is detected
    if (top > 0.55 && top < CONF_THRESHOLD
        && (now - lastWiggleTime) > WIGGLE_COOLDOWN
        && (now - lastSentTime)   > COOLDOWN_MS) {
      sendCommand('w');
      triggerWiggleAnim();
      lastWiggleTime = now;
    }

    if (now - lastSentTime > COOLDOWN_MS) {
      if (c1 >= CONF_THRESHOLD) {
        triggerWiggleAnim();
        sendCommand('1');
        logDetection(labels[0], c1, 'Servo->A, Green LED, 1 beep');
        setTimeout(() => animateAction('class1'), 500);
        lastSentTime = now;
      } else if (c2 >= CONF_THRESHOLD) {
        triggerWiggleAnim();
        sendCommand('2');
        logDetection(labels[1], c2, 'Servo->B, Red LED, 2 beeps');
        setTimeout(() => animateAction('class2'), 500);
        lastSentTime = now;
      } else if (top > 0 && top < 0.55) {
        sendCommand('0');
        logDetection('unknown', top, 'Blink LEDs, warning');
        animateAction('unknown');
        lastSentTime = now;
      }
    }
  }

  classifyVideo();
}

function findConf(results, label) {
  if (!label) return 0;
  const r = results.find(o => o.label === label);
  return r ? r.confidence : 0;
}

// =====================================================
// SERIAL
// =====================================================
function sendCommand(cmd) {
  try {
    const view = new TextEncoder().encode(cmd);
    if (window.port) window.port.send(view);
    console.log('[Serial] Sent:', cmd);
  } catch (e) { console.warn('Arduino not connected:', e.message); }
}

// =====================================================
// UI
// =====================================================
function updateBars(c1, c2) {
  bar1.style.width = (c1 * 100) + '%';
  bar2.style.width = (c2 * 100) + '%';
  pct1.textContent = (c1 * 100).toFixed(0) + '%';
  pct2.textContent = (c2 * 100).toFixed(0) + '%';
}

function setStatus(msg) {
  if (statusDiv) statusDiv.textContent = msg;
}

function triggerWiggleAnim() {
  servoArm.classList.add('wiggling');
  const base = parseFloat(angleText.textContent) || 90;
  const offsets = [12, -12, 12, -12, 0];
  let i = 0;
  const step = setInterval(() => {
    if (i >= offsets.length) {
      clearInterval(step);
      servoArm.classList.remove('wiggling');
      moveServo(base);
      return;
    }
    moveServo(base + offsets[i]);
    i++;
  }, 90);
}

function animateAction(type) {
  ledGreen.classList.remove('on');
  ledRed.classList.remove('on');
  buzzer.classList.remove('active');

  if (type === 'class1') {
    ledGreen.classList.add('on');
    buzzer.classList.add('active');
    moveServo(30);
    lastDet.textContent = labels[0];
    setTimeout(() => { ledGreen.classList.remove('on'); buzzer.classList.remove('active'); moveServo(90); }, 1200);
  } else if (type === 'class2') {
    ledRed.classList.add('on');
    buzzer.classList.add('active');
    moveServo(150);
    lastDet.textContent = labels[1];
    setTimeout(() => { ledRed.classList.remove('on'); buzzer.classList.remove('active'); moveServo(90); }, 1200);
  } else {
    buzzer.classList.add('active');
    let toggles = 0;
    const blink = setInterval(() => {
      ledGreen.classList.toggle('on');
      ledRed.classList.toggle('on');
      toggles++;
      if (toggles > 6) {
        clearInterval(blink);
        ledGreen.classList.remove('on');
        ledRed.classList.remove('on');
        buzzer.classList.remove('active');
      }
    }, 200);
    lastDet.textContent = 'unknown';
  }
}

function moveServo(angle) {
  const rotation = angle - 90;
  servoArm.style.transform = `translateX(-50%) rotate(${rotation}deg)`;
  angleText.textContent = Math.round(angle) + '°';
}

// =====================================================
// DATA LOGGING
// =====================================================
function logDetection(className, confidence, action) {
  const ts = new Date().toISOString();
  const entry = { timestamp: ts, className, confidence: confidence.toFixed(3), action };
  logEntries.push(entry);
  console.log('[LOG]', entry);

  const row = document.createElement('tr');
  row.innerHTML = `
    <td>${logEntries.length}</td>
    <td>${ts.split('T')[1].split('.')[0]}</td>
    <td>${className}</td>
    <td>${(confidence * 100).toFixed(1)}%</td>
    <td>${action}</td>
  `;
  logBody.prepend(row);
}

function downloadCSV() {
  if (logEntries.length === 0) { alert('No data to export yet.'); return; }
  let csv = 'Timestamp,Class,Confidence,Action\n';
  logEntries.forEach(e => {
    csv += `${e.timestamp},${e.className},${e.confidence},"${e.action}"\n`;
  });
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `sorter_log_${Date.now()}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function clearLog() {
  if (!confirm('Clear all logged data?')) return;
  logEntries = [];
  logBody.innerHTML = '';
}
