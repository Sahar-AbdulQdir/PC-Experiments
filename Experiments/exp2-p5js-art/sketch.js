let port;
let connected  = false;
let distance   = 0;
let joyX       = 512;
let joyY       = 512;
let joyBtn     = 0;

// Calibration
let joyXCenter = 512;
let joyYCenter = 512;
let calibrated = false;

//  Target and smoothed rotation angles
let targetRotZ  = 0;   // where joystick X says to point
let smoothRotZ  = 0;   // what's actually drawn (lerped)
let targetTilt  = 0;   // where joystick Y says to shift
let smoothTilt  = 0;   // what's actually drawn (lerped)

let lastSentColors = "";

const COLS = 20;
const ROWS = 20;
let cells = [];
const DEAD = 50;

function setup() {
  createCanvas(600, 600);
  textAlign(CENTER, CENTER);
  port = createSerial();

  for (let i = 0; i < COLS; i++) {
    cells[i] = [];
    for (let j = 0; j < ROWS; j++) {
      cells[i][j] = {
        type:     random(2) < 1 ? 'bar' : 'cube',
        offset:   random(TWO_PI),
        currentH: 4,
        targetH:  4
      };
    }
  }
}

function draw() {
  background(20);
  connected = port.opened();

  if (!connected) calibrated = false;

  // ── Read serial ─────────────────────────────
  if (connected && port.available() > 0) {
    let raw = port.readUntil('\n');
    if (raw) {
      raw = raw.trim();
      let parts = raw.split(',');
      let gotJoy = false;
      for (let p of parts) {
        if (p.startsWith("DIST:")) { let v = int(p.substring(5)); if (!isNaN(v)) distance = v; }
        if (p.startsWith("JX:"))   { let v = int(p.substring(3)); if (!isNaN(v)) { joyX = v; gotJoy = true; } }
        if (p.startsWith("JY:"))   { let v = int(p.substring(3)); if (!isNaN(v)) joyY = v; }
        if (p.startsWith("JB:"))   { let v = int(p.substring(3)); if (!isNaN(v)) joyBtn = v; }
      }
      // Calibrate on first real reading
      if (gotJoy && !calibrated) {
        joyXCenter = joyX;
        joyYCenter = joyY;
        calibrated = true;
      }
    }
  }

  // ── Joystick → DIRECT positional rotation ───
  // Joystick X position directly maps to a rotation angle
  // Joystick Y position directly maps to a tilt offset
  // No accumulation — where stick is = where grid points
  if (calibrated) {
    let dxRaw = joyX - joyXCenter;
    let dyRaw = joyY - joyYCenter;

    // Apply dead zone — snap to zero inside it
    let dx = abs(dxRaw) > DEAD ? dxRaw : 0;
    let dy = abs(dyRaw) > DEAD ? dyRaw : 0;

    if (joyBtn === 1) {
      // Button held → reset to centre
      targetRotZ = 0;
      targetTilt = 0;
    } else {
      // ✅ Direct map: stick position → angle
      // Full left  = -HALF_PI/2,  Full right = +HALF_PI/2  (~90° total sweep)
      targetRotZ = map(dx, -512, 512, -HALF_PI / 2, HALF_PI / 2);
      targetTilt = map(dy, -512, 512, -100, 100);
    }
  }

  //  Smooth lerp toward target — feels fluid, not instant
  smoothRotZ = lerp(smoothRotZ, targetRotZ, 0.08);
  smoothTilt = lerp(smoothTilt, targetTilt, 0.08);

  // ── Art parameters from distance ────────────
  let d        = constrain(distance, 0, 40);
  let waveAmp  = map(d, 0, 40, 0.0, 1.0);
  let minH     = 4;
  let maxH     = map(d, 0, 40, 4, 120);
  let speed    = map(d, 0, 40, 0.0008, 0.004);
  let hueShift = map(d, 0, 40, 0, 280);

  let isoW    = 26;
  let isoH    = 13;
  let originX = width / 2;
  let originY = 160 + smoothTilt;

  colorMode(HSB, 360, 100, 100, 100);
  noStroke();

  //  Rotate grid by smoothed angle
  push();
  translate(width / 2, height / 2);
  rotate(smoothRotZ);
  translate(-width / 2, -height / 2);

  for (let j = 0; j < ROWS; j++) {
    for (let i = 0; i < COLS; i++) {
      let cell = cells[i][j];

      let sx = originX + (i - j) * isoW;
      let sy = originY + (i + j) * isoH;

      let wave      = sin(frameCount * speed + cell.offset + (i + j) * 0.3);
      let wavePart  = map(wave, -1, 1, 0, 1) * waveAmp;
      cell.targetH  = lerp(minH, maxH, wavePart);
      cell.currentH = lerp(cell.currentH, cell.targetH, 0.05);

      let hue = (hueShift + (i * 7 + j * 13)) % 360;

      if (cell.type === 'bar') {
        drawIsoBar(sx, sy, cell.currentH, hue, isoW, isoH);
      } else {
        drawIsoCube(sx, sy, cell.currentH, hue, isoW, isoH);
      }
    }
  }
  pop();

  // ── UI ───────────────────────────────────────
  colorMode(RGB, 255);
  fill(255);
  textSize(16);

  if (connected) {
    text("Distance: " + distance + " cm",           width / 2, 26);
    text("Rotation: " + nf(degrees(smoothRotZ), 1, 1) + "°", width / 2, 46);
    fill(joyBtn === 1 ? color(255, 80, 80) : color(160));
    text(joyBtn === 1 ? "● RESET" : "○ Push to reset", width / 2, 66);
  } else {
    fill(255);
    text("Click anywhere to connect to Arduino", width / 2, 26);
  }

  // p5 no longer drives LEDs — Arduino handles them by distance
  // But we still need to keep serial open for joystick reads,
  // so just flush any pending writes
  lastSentColors = "";

  fill(connected ? color(0, 200, 0) : color(200, 0, 0));
  noStroke();
  ellipse(width / 2 - 75, height - 20, 10, 10);
  fill(255);
  textSize(13);
  text(connected ? "Connected" : "Disconnected", width / 2, height - 20);

  if (connected) drawLEDPreview(distance);
}

// ── LED preview reflects distance zones ──────
function drawLEDPreview(dist) {
  colorMode(RGB, 255);
  let w = 50;
  let startX = width / 2 - 2 * w - 10;
  let y = height - 80;

  // Mirror the Arduino distance logic visually
  let colors = [
    [0,   0,   0],   // Red LED
    [0,   0,   0],   // Green LED
    [0,   0,   0],   // Blue LED
    [0,   0,   0]    // Yellow LED
  ];

  if (dist <= 10) {
    colors[0] = [255, 0, 0];
  } else if (dist <= 20) {
    colors[0] = [255, 0, 0];
    colors[3] = [255, 200, 0];
  } else if (dist <= 30) {
    colors[3] = [255, 200, 0];
    colors[1] = [0, 255, 0];
  } else if (dist <= 50) {
    colors[1] = [0, 255, 0];
    colors[2] = [0, 100, 255];
  } else {
    colors[2] = [0, 100, 255];
  }

  let labels = ["R", "G", "B", "Y"];
  for (let i = 0; i < 4; i++) {
    fill(colors[i][0], colors[i][1], colors[i][2]);
    noStroke();
    rect(startX + i * (w + 10), y, w, w);
    fill(255);
    textSize(14);
    text(labels[i], startX + i * (w + 10) + w / 2, y + w + 12);
  }
}

// ── Draw an isometric CUBE ──────────────────
function drawIsoCube(sx, sy, h, hue, isoW, isoH) {
  let top   = color_hsb(hue, 60, 100, 95);
  let left  = color_hsb(hue, 80, 65,  95);
  let right = color_hsb(hue, 80, 45,  95);

  fill(top);
  beginShape();
  vertex(sx,        sy - h);
  vertex(sx + isoW, sy - h + isoH);
  vertex(sx,        sy - h + isoH * 2);
  vertex(sx - isoW, sy - h + isoH);
  endShape(CLOSE);

  fill(left);
  beginShape();
  vertex(sx - isoW, sy - h + isoH);
  vertex(sx,        sy - h + isoH * 2);
  vertex(sx,        sy + isoH * 2);
  vertex(sx - isoW, sy + isoH);
  endShape(CLOSE);

  fill(right);
  beginShape();
  vertex(sx + isoW, sy - h + isoH);
  vertex(sx,        sy - h + isoH * 2);
  vertex(sx,        sy + isoH * 2);
  vertex(sx + isoW, sy + isoH);
  endShape(CLOSE);
}

// ── Draw an isometric flat BAR ──────────────
function drawIsoBar(sx, sy, h, hue, isoW, isoH) {
  let slabH = max(3, h * 0.25);

  let top   = color_hsb((hue + 40) % 360, 50, 100, 90);
  let left  = color_hsb((hue + 40) % 360, 70, 70,  90);
  let right = color_hsb((hue + 40) % 360, 70, 50,  90);

  fill(top);
  beginShape();
  vertex(sx,        sy - slabH);
  vertex(sx + isoW, sy - slabH + isoH);
  vertex(sx,        sy - slabH + isoH * 2);
  vertex(sx - isoW, sy - slabH + isoH);
  endShape(CLOSE);

  fill(left);
  beginShape();
  vertex(sx - isoW, sy - slabH + isoH);
  vertex(sx,        sy - slabH + isoH * 2);
  vertex(sx,        sy + isoH * 2);
  vertex(sx - isoW, sy + isoH);
  endShape(CLOSE);

  fill(right);
  beginShape();
  vertex(sx + isoW, sy - slabH + isoH);
  vertex(sx,        sy - slabH + isoH * 2);
  vertex(sx,        sy + isoH * 2);
  vertex(sx + isoW, sy + isoH);
  endShape(CLOSE);
}

// ── HSB color helper ────────────────────────
function color_hsb(h, s, b, a) {
  colorMode(HSB, 360, 100, 100, 100);
  let c = color(h, s, b, a);
  colorMode(RGB, 255);
  return c;
}

// ── Mouse: open / close port ────────────────
function mousePressed() {
  if (!connected) {
    port.open(9600);
  } else {
    port.close();
  }
}