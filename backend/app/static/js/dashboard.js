// Staff Dashboard Web Client Engine
let currentFilter = 'all';
let currentAlertsList = [];
let activeModalAlert = null;
let latestBannerAlert = null;
let audioEnabled = true;
let audioCtx = null;

let browserWebcamStream = null;
let browserWebcamWs = null;
let browserWebcamInterval = null;

document.addEventListener('DOMContentLoaded', () => {
  initLiveClock();
  initAudioUnlockListener();
  loadSeats();
  loadAlerts();
  loadStats();
  initWebSockets();

  // Refresh data periodically
  setInterval(loadSeats, 1500);
  setInterval(loadStats, 3000);
});

// Unlock Web Audio API Context on first user click anywhere
function initAudioUnlockListener() {
  const unlockAudio = () => {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioCtx.state === 'suspended') {
      audioCtx.resume();
    }
    document.removeEventListener('click', unlockAudio);
    document.removeEventListener('keydown', unlockAudio);
  };
  document.addEventListener('click', unlockAudio);
  document.addEventListener('keydown', unlockAudio);
}

// Toggle Audio Mute / Unmute
function toggleAudio() {
  audioEnabled = !audioEnabled;
  const btn = document.getElementById('audioToggleBtn');
  const icon = document.getElementById('audioIcon');
  const text = document.getElementById('audioStatusText');

  if (audioEnabled) {
    btn.classList.remove('muted');
    icon.textContent = '🔊';
    text.textContent = 'Audio: ON';
    playAlertTone();
  } else {
    btn.classList.add('muted');
    icon.textContent = '🔇';
    text.textContent = 'Audio: OFF';
  }
}

// Live Clock
function initLiveClock() {
  const clockEl = document.getElementById('liveClock');
  setInterval(() => {
    const now = new Date();
    clockEl.textContent = now.toLocaleTimeString();
  }, 1000);
}

// Phone Camera Modal Handlers with Auto Local IP Fetch
async function openPhoneCameraModal() {
  const modal = document.getElementById('phoneModal');
  const ipLink = document.getElementById('phoneIpLink');
  try {
    const res = await fetch('/api/stats');
    const stats = await res.json();
    if (ipLink && stats.camera_url) {
      ipLink.href = stats.camera_url;
      ipLink.textContent = stats.camera_url;
    }
  } catch (err) {
    console.error('Failed to fetch system stats IP:', err);
  }
  modal.style.display = 'flex';
}

function closePhoneModal() {
  document.getElementById('phoneModal').style.display = 'none';
}

function closePhoneModalOnOverlay(event) {
  if (event.target.id === 'phoneModal') {
    closePhoneModal();
  }
}

// Direct In-Browser Webcam Capture Streamer
async function startBrowserWebcam() {
  const imgEl = document.getElementById('videoFeedImg');
  const videoEl = document.getElementById('browserWebcamVideo');
  const canvasEl = document.getElementById('browserWebcamCanvas');
  if (!videoEl || !canvasEl) return;
  const ctx = canvasEl.getContext('2d');

  try {
    browserWebcamStream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false
    });

    videoEl.srcObject = browserWebcamStream;
    await videoEl.play();

    // Keep AI Processed Video Stream visible at all times!
    if (imgEl) imgEl.style.display = 'block';
    if (videoEl) videoEl.style.display = 'none';
    if (imgEl) imgEl.src = '/video_feed?t=' + Date.now();

    // Connect WebSocket stream to backend for AI object & phone detection
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/stream_input`;
    browserWebcamWs = new WebSocket(wsUrl);
    browserWebcamWs.binaryType = "arraybuffer";

    browserWebcamWs.onopen = () => {
      if (browserWebcamInterval) clearInterval(browserWebcamInterval);
      browserWebcamInterval = setInterval(() => {
        if (!browserWebcamWs || browserWebcamWs.readyState !== WebSocket.OPEN) return;
        if (videoEl.videoWidth === 0 || videoEl.videoHeight === 0) return;
        canvasEl.width = 640;
        canvasEl.height = 360;
        ctx.drawImage(videoEl, 0, 0, canvasEl.width, canvasEl.height);
        canvasEl.toBlob((blob) => {
          if (blob && browserWebcamWs && browserWebcamWs.readyState === WebSocket.OPEN) {
            blob.arrayBuffer().then(buf => browserWebcamWs.send(buf));
          }
        }, 'image/jpeg', 0.65);
      }, 50);
    };

    browserWebcamWs.onclose = () => {
      if (browserWebcamInterval) clearInterval(browserWebcamInterval);
    };

  } catch (err) {
    console.warn("Direct browser webcam access fallback:", err);
    if (imgEl) {
      imgEl.style.display = 'block';
      imgEl.src = '/video_feed?t=' + Date.now();
    }
    if (videoEl) videoEl.style.display = 'none';
  }
}

function stopBrowserWebcam() {
  const imgEl = document.getElementById('videoFeedImg');
  const videoEl = document.getElementById('browserWebcamVideo');

  if (browserWebcamInterval) clearInterval(browserWebcamInterval);
  if (browserWebcamWs) { browserWebcamWs.close(); browserWebcamWs = null; }
  if (browserWebcamStream) {
    browserWebcamStream.getTracks().forEach(t => t.stop());
    browserWebcamStream = null;
  }
  if (videoEl) videoEl.style.display = 'none';
  if (imgEl) {
    imgEl.style.display = 'block';
    imgEl.src = '/video_feed?t=' + Date.now();
  }
}

// Change Webcam Source (Server Index 0/1/2 vs In-Browser Webcam)
async function changeWebcamSource(val) {
  const imgEl = document.getElementById('videoFeedImg');

  // Notify backend to set feed_mode to webcam
  const modeFormData = new FormData();
  modeFormData.append('mode', 'webcam');
  try {
    await fetch('/api/mode', { method: 'POST', body: modeFormData });
  } catch (e) {
    console.warn("Failed to set mode:", e);
  }

  if (val === 'browser') {
    document.getElementById('activeSourceText').textContent = 'IN-BROWSER WEBCAM STREAM';
    await startBrowserWebcam();
  } else if (val.startsWith('server_')) {
    stopBrowserWebcam();
    const idx = parseInt(val.replace('server_', ''), 10);
    document.getElementById('activeSourceText').textContent = `SERVER WEBCAM (INDEX ${idx})`;
    
    const formData = new FormData();
    formData.append('index', idx);
    await fetch('/api/webcam/index', { method: 'POST', body: formData });
    
    if (imgEl) imgEl.src = '/video_feed?t=' + Date.now();
  }
}

// Switch Video Feed Input Source (simulator, webcam, file, phone_camera)
async function switchFeedMode(mode) {
  document.getElementById('btnModeSim').classList.remove('active');
  document.getElementById('btnModeWebcam').classList.remove('active');
  document.getElementById('btnModeFile').classList.remove('active');
  document.getElementById('btnModePhone').classList.remove('active');
  const webcamSelect = document.getElementById('webcamSelect');

  if (mode === 'simulator') {
    if (webcamSelect) webcamSelect.style.display = 'none';
    stopBrowserWebcam();
    document.getElementById('btnModeSim').classList.add('active');
    document.getElementById('activeSourceText').textContent = 'SYNTHETIC SIMULATOR';
  } else if (mode === 'webcam') {
    if (webcamSelect) {
      webcamSelect.style.display = 'inline-block';
      // Default to In-Browser Webcam on web deployments
      webcamSelect.value = 'browser';
    }
    document.getElementById('btnModeWebcam').classList.add('active');
    await changeWebcamSource('browser');
  } else if (mode === 'file') {
    if (webcamSelect) webcamSelect.style.display = 'none';
    stopBrowserWebcam();
    document.getElementById('btnModeFile').classList.add('active');
    document.getElementById('activeSourceText').textContent = 'CUSTOM VIDEO FILE';
  } else if (mode === 'phone_camera') {
    if (webcamSelect) webcamSelect.style.display = 'none';
    stopBrowserWebcam();
    document.getElementById('btnModePhone').classList.add('active');
    document.getElementById('activeSourceText').textContent = 'MOBILE PHONE CAMERA STREAM (/camera)';
  }

  const formData = new FormData();
  formData.append('mode', mode);

  try {
    await fetch('/api/mode', {
      method: 'POST',
      body: formData
    });
    const imgEl = document.getElementById('videoFeedImg');
    if (imgEl) imgEl.src = '/video_feed?t=' + Date.now();
    loadSeats();
    loadStats();
  } catch (err) {
    console.error('Failed to change feed mode:', err);
  }
}

function triggerVideoUpload() {
  document.getElementById('videoFileInput').click();
}

async function uploadVideoFile(inputEl) {
  if (!inputEl.files || inputEl.files.length === 0) return;
  const file = inputEl.files[0];
  const formData = new FormData();
  formData.append('file', file);

  document.getElementById('activeSourceText').textContent = `UPLOADING ${file.name.toUpperCase()}...`;

  try {
    const res = await fetch('/api/upload_video', {
      method: 'POST',
      body: formData
    });
    if (res.ok) {
      stopBrowserWebcam();
      document.getElementById('btnModeSim').classList.remove('active');
      document.getElementById('btnModeWebcam').classList.remove('active');
      document.getElementById('btnModeFile').classList.add('active');
      document.getElementById('btnModePhone').classList.remove('active');
      document.getElementById('activeSourceText').textContent = `VIDEO FILE: ${file.name}`;
      loadSeats();
      loadStats();
    }
  } catch (err) {
    console.error('Failed to upload video:', err);
    alert('Failed to upload video file.');
  }
}

// Load Seats Grid
async function loadSeats() {
  try {
    const res = await fetch('/api/seats');
    const seats = await res.json();
    currentSeatsData = seats;
    renderSeatingGrid(seats);
    update3DSeats(seats);
  } catch (err) {
    console.error('Failed to load seats layout:', err);
  }
}

// Render Interactive Seating Grid
function renderSeatingGrid(seats) {
  const gridContainer = document.getElementById('seatingGrid');
  gridContainer.innerHTML = '';

  // Group seats by Row Label
  const rowGroups = {};
  seats.forEach(seat => {
    if (!rowGroups[seat.row_label]) {
      rowGroups[seat.row_label] = [];
    }
    rowGroups[seat.row_label].push(seat);
  });

  // Build HTML for each row
  Object.keys(rowGroups).sort().forEach(rowLabel => {
    const rowDiv = document.createElement('div');
    rowDiv.className = 'seat-row';

    const labelDiv = document.createElement('div');
    labelDiv.className = 'row-label';
    labelDiv.textContent = rowLabel;
    rowDiv.appendChild(labelDiv);

    rowGroups[rowLabel].sort((a, b) => a.seat_number - b.seat_number).forEach(seat => {
      const btn = document.createElement('button');
      btn.className = `seat-btn ${seat.status}`;
      btn.textContent = seat.seat_number;
      btn.title = `Seat ${seat.seat_id} - Status: ${seat.status.toUpperCase()}`;

      btn.addEventListener('click', () => {
        const matchingAlert = currentAlertsList.find(a => a.seat_id === seat.seat_id);
        if (matchingAlert) {
          openEvidenceModal(matchingAlert);
        } else {
          alert(`Seat ${seat.seat_id}\nRow: ${seat.row_label}\nSeat Number: ${seat.seat_number}\nCurrent Status: ${seat.status.toUpperCase()}`);
        }
      });

      rowDiv.appendChild(btn);
    });

    gridContainer.appendChild(rowDiv);
  });
}

// Filter Alert Rows
function setAlertFilter(filterValue) {
  currentFilter = filterValue;
  document.querySelectorAll('.filter-tabs .tab-btn').forEach(btn => {
    if (btn.getAttribute('data-filter') === filterValue) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
  });
  renderAlertsTable(currentAlertsList);
}

// Load Incidents Table
async function loadAlerts() {
  try {
    const res = await fetch('/api/alerts');
    currentAlertsList = await res.json();
    renderAlertsTable(currentAlertsList);
  } catch (err) {
    console.error('Failed to load alert history:', err);
  }
}

// Render Table Rows
function renderAlertsTable(alerts) {
  const tbody = document.getElementById('alertTableBody');
  tbody.innerHTML = '';

  const filteredAlerts = alerts.filter(a => {
    if (currentFilter === 'all') return true;
    return a.status === currentFilter;
  });

  if (filteredAlerts.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 24px;">No matching incident records found. Monitoring live camera feed...</td></tr>';
    return;
  }

  filteredAlerts.forEach(alert => {
    const tr = document.createElement('tr');

    let badgeClass = 'verification';
    if (alert.status === 'Reviewed') badgeClass = 'reviewed';
    if (alert.status === 'False Alarm') badgeClass = 'false-alarm';
    if (alert.status === 'Confirmed Suspicious') badgeClass = 'confirmed';

    const thumbHtml = alert.thumbnail_url 
      ? `<img src="${alert.thumbnail_url}" class="table-thumb-preview" alt="Snapshot" onclick='openEvidenceModal(${JSON.stringify(alert).replace(/'/g, "&apos;")})' title="Click to inspect evidence">`
      : `<div class="table-thumb-placeholder" onclick='openEvidenceModal(${JSON.stringify(alert).replace(/'/g, "&apos;")})'>No Img</div>`;

    tr.innerHTML = `
      <td>${thumbHtml}</td>
      <td style="font-family: monospace; font-size: 0.78rem; color: var(--accent-cyan); cursor: pointer;" onclick='openEvidenceModal(${JSON.stringify(alert).replace(/'/g, "&apos;")})'>${alert.alert_uuid}</td>
      <td style="color: var(--text-muted);">${alert.timestamp}</td>
      <td><strong style="color: var(--accent-red); font-size: 0.9rem;">${alert.seat_id}</strong></td>
      <td>
        <span style="font-weight: 700; color: ${alert.score >= 75 ? 'var(--accent-red)' : 'var(--accent-amber)'};">
          ${alert.score}%
        </span>
      </td>
      <td>${alert.duration}s</td>
      <td style="font-size: 0.78rem; color: var(--text-muted); max-width: 280px;">${alert.reason}</td>
      <td><span class="badge-status ${badgeClass}">${alert.status}</span></td>
      <td>
        <button class="btn-action" onclick="updateAlertStatus(${alert.id}, 'Confirmed Suspicious')">Confirm</button>
        <button class="btn-action" onclick="updateAlertStatus(${alert.id}, 'False Alarm')">False Alarm</button>
        <button class="btn-action" onclick="updateAlertStatus(${alert.id}, 'Reviewed')">Reviewed</button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

// Open Evidence Lightbox Modal
function openEvidenceModal(alertRecord) {
  activeModalAlert = alertRecord;
  const modal = document.getElementById('evidenceModal');
  const img = document.getElementById('modalImage');
  const noImg = document.getElementById('modalNoImage');
  const seatId = document.getElementById('modalSeatId');
  const score = document.getElementById('modalScore');
  const duration = document.getElementById('modalDuration');
  const confidence = document.getElementById('modalConfidence');
  const reason = document.getElementById('modalReason');

  seatId.textContent = `Seat ${alertRecord.seat_id}`;
  score.textContent = `${alertRecord.score}%`;
  duration.textContent = `${alertRecord.duration}s`;
  confidence.textContent = `${Math.round(alertRecord.confidence * 100)}%`;
  reason.textContent = alertRecord.reason;

  if (alertRecord.thumbnail_url) {
    img.src = alertRecord.thumbnail_url;
    img.style.display = 'block';
    noImg.style.display = 'none';
  } else {
    img.style.display = 'none';
    noImg.style.display = 'block';
  }

  modal.style.display = 'flex';
}

function closeEvidenceModal() {
  document.getElementById('evidenceModal').style.display = 'none';
  activeModalAlert = null;
}

function closeModalOnOverlay(event) {
  if (event.target.id === 'evidenceModal') {
    closeEvidenceModal();
  }
}

async function verifyCurrentModalAlert(newStatus) {
  if (!activeModalAlert) return;
  await updateAlertStatus(activeModalAlert.id, newStatus);
  closeEvidenceModal();
}

// Update Alert Status API Call
async function updateAlertStatus(alertId, newStatus) {
  try {
    const res = await fetch(`/api/alerts/${alertId}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    });
    if (res.ok) {
      loadAlerts();
      loadSeats();
      loadStats();
    }
  } catch (err) {
    console.error('Failed to update status:', err);
  }
}

// Load Stats
async function loadStats() {
  try {
    const res = await fetch('/api/stats');
    const stats = await res.json();
    document.getElementById('kpiPending').textContent = stats.pending_alerts;
    document.getElementById('kpiConfirmed').textContent = stats.confirmed_alerts;
    document.getElementById('kpiFalse').textContent = stats.false_alarms;
    document.getElementById('kpiTotal').textContent = stats.total_alerts;

    // Sync input mode selector button state if stats returned feed_mode
    if (stats.feed_mode) {
      document.getElementById('btnModeSim').classList.remove('active');
      document.getElementById('btnModeWebcam').classList.remove('active');
      document.getElementById('btnModeFile').classList.remove('active');
      document.getElementById('btnModePhone').classList.remove('active');
      if (stats.feed_mode === 'simulator') {
        document.getElementById('btnModeSim').classList.add('active');
      } else if (stats.feed_mode === 'webcam') {
        document.getElementById('btnModeWebcam').classList.add('active');
      } else if (stats.feed_mode === 'file') {
        document.getElementById('btnModeFile').classList.add('active');
      } else if (stats.feed_mode === 'phone_camera') {
        document.getElementById('btnModePhone').classList.add('active');
      }
    }
  } catch (err) {
    console.error('Failed to load stats:', err);
  }
}

// Simulation Scenario Switcher
async function setScenario(scenarioName) {
  stopBrowserWebcam();
  document.querySelectorAll('.scenario-bar button').forEach(b => b.classList.remove('active'));
  if (scenarioName === 'recording_attempt') document.getElementById('btnScenarioRec').classList.add('active');
  if (scenarioName === 'casual_phone') document.getElementById('btnScenarioCasual').classList.add('active');
  if (scenarioName === 'normal') document.getElementById('btnScenarioNormal').classList.add('active');

  document.getElementById('btnModeSim').classList.add('active');
  document.getElementById('btnModeWebcam').classList.remove('active');
  document.getElementById('btnModeFile').classList.remove('active');
  document.getElementById('btnModePhone').classList.remove('active');
  document.getElementById('activeSourceText').textContent = 'SYNTHETIC SIMULATOR';

  const formData = new FormData();
  formData.append('scenario_name', scenarioName);

  await fetch('/api/simulator/scenario', {
    method: 'POST',
    body: formData
  });

  loadSeats();
  loadStats();
}

// WebSockets for Instant Alert Broadcasting
function initWebSockets() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/alerts`;
  const socket = new WebSocket(wsUrl);

  socket.onmessage = (event) => {
    const alertData = JSON.parse(event.data);
    latestBannerAlert = alertData;
    triggerAlertBanner(alertData);
    playAlertTone();
    loadAlerts();
    loadSeats();
    loadStats();
  };

  socket.onclose = () => {
    setTimeout(initWebSockets, 3000);
  };
}

// Audio Alert Chime (Web Audio API Synthesizer)
function playAlertTone() {
  if (!audioEnabled) return;
  try {
    if (!audioCtx) {
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioCtx.state === 'suspended') {
      audioCtx.resume();
    }
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, audioCtx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(440, audioCtx.currentTime + 0.35);

    gain.gain.setValueAtTime(0.25, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.35);

    osc.connect(gain);
    gain.connect(audioCtx.destination);

    osc.start();
    osc.stop(audioCtx.currentTime + 0.35);
  } catch (e) {
    console.log('Audio playback blocked or unavailable:', e);
  }
}

// Trigger Alert Banner
function triggerAlertBanner(alertData) {
  const banner = document.getElementById('alertBanner');
  const title = document.getElementById('bannerTitle');
  const detail = document.getElementById('bannerDetail');

  title.textContent = `⚠ Suspicious Recording Activity Detected`;
  detail.textContent = `Seat ${alertData.seat_id} | Suspicion Score: ${alertData.score}% | Duration: ${alertData.duration}s — Requires Staff Verification`;
  
  banner.style.display = 'flex';
}

function inspectCurrentBannerAlert() {
  if (latestBannerAlert) {
    openEvidenceModal(latestBannerAlert);
  }
}

function dismissBanner() {
  document.getElementById('alertBanner').style.display = 'none';
}

// ----------------------------------------------------
// 3D Spatial Cinema Theater & Camera Frustum Engine
// ----------------------------------------------------
let activeSeatingView = '2D';
let scene3D = null, camera3D = null, renderer3D = null, controls3D = null;
let seatMeshes3D = {};
let alertBeacons3D = {};
let cameraFrustumMesh3D = null;
let is3DInitialized = false;
let is3DAutoRotate = false;
let currentSeatsData = [];

function switchSeatingView(mode) {
  activeSeatingView = mode;
  const btn2D = document.getElementById('btnView2D');
  const btn3D = document.getElementById('btnView3D');
  const container2D = document.getElementById('seating2DContainer');
  const container3D = document.getElementById('seating3DContainer');

  if (mode === '2D') {
    if (btn2D) btn2D.classList.add('active');
    if (btn3D) btn3D.classList.remove('active');
    if (container2D) container2D.style.display = 'block';
    if (container3D) container3D.style.display = 'none';
  } else {
    if (btn2D) btn2D.classList.remove('active');
    if (btn3D) btn3D.classList.add('active');
    if (container2D) container2D.style.display = 'none';
    if (container3D) container3D.style.display = 'block';

    if (!is3DInitialized) {
      setTimeout(init3DTheaterScene, 50);
    } else {
      update3DSeats(currentSeatsData);
      on3DWindowResize();
    }
  }
}

function init3DTheaterScene() {
  const canvas = document.getElementById('theater3DCanvas');
  const holder = document.getElementById('canvas3DHolder');
  if (!canvas || !holder || typeof THREE === 'undefined') return;

  const width = holder.clientWidth || 500;
  const height = holder.clientHeight || 300;

  // 1. Scene setup
  scene3D = new THREE.Scene();
  scene3D.background = new THREE.Color(0x04060a);
  scene3D.fog = new THREE.FogExp2(0x04060a, 0.025);

  // 2. Camera setup
  camera3D = new THREE.PerspectiveCamera(50, width / height, 0.1, 100);
  camera3D.position.set(0, 8, 12);

  // 3. Renderer setup
  renderer3D = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true });
  renderer3D.setSize(width, height);
  renderer3D.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  // 4. Controls setup
  if (typeof THREE.OrbitControls !== 'undefined') {
    controls3D = new THREE.OrbitControls(camera3D, renderer3D.domElement);
    controls3D.enableDamping = true;
    controls3D.dampingFactor = 0.05;
    controls3D.maxPolarAngle = Math.PI / 2.05;
    controls3D.target.set(0, 1.5, 0);
  }

  // 5. Lighting setup
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
  scene3D.add(ambientLight);

  const spotLight = new THREE.SpotLight(0x00d7ff, 1.5);
  spotLight.position.set(0, 9, 2);
  spotLight.angle = Math.PI / 4;
  scene3D.add(spotLight);

  const screenLight = new THREE.PointLight(0x00a2ff, 1.2, 15);
  screenLight.position.set(0, 2, -7);
  scene3D.add(screenLight);

  // 6. Cinema Architecture
  const floorGeo = new THREE.PlaneGeometry(16, 20);
  const floorMat = new THREE.MeshStandardMaterial({ color: 0x090c14, roughness: 0.8 });
  const floor = new THREE.Mesh(floorGeo, floorMat);
  floor.rotation.x = -Math.PI / 2;
  scene3D.add(floor);

  // Cinema Screen
  const screenGeo = new THREE.PlaneGeometry(10, 4.5);
  const screenMat = new THREE.MeshBasicMaterial({ color: 0x00d7ff });
  const screenMesh = new THREE.Mesh(screenGeo, screenMat);
  screenMesh.position.set(0, 3, -8);
  scene3D.add(screenMesh);

  // Screen Frame
  const frameGeo = new THREE.BoxGeometry(10.4, 4.9, 0.2);
  const frameMat = new THREE.MeshStandardMaterial({ color: 0x111625 });
  const frameMesh = new THREE.Mesh(frameGeo, frameMat);
  frameMesh.position.set(0, 3, -8.1);
  scene3D.add(frameMesh);

  // Security Camera Mount & 3D Frustum Beam
  createCameraMountAndFrustum();

  // Raycaster for clicking seats in 3D
  const raycaster = new THREE.Raycaster();
  const mouse = new THREE.Vector2();

  canvas.addEventListener('click', (event) => {
    const rect = canvas.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera3D);
    const intersects = raycaster.intersectObjects(Object.values(seatMeshes3D));

    if (intersects.length > 0) {
      const clickedMesh = intersects[0].object;
      const seatId = clickedMesh.userData.seatId;
      if (seatId) {
        const matchingAlert = currentAlertsList.find(a => a.seat_id === seatId);
        if (matchingAlert) openEvidenceModal(matchingAlert);
      }
    }
  });

  is3DInitialized = true;
  window.addEventListener('resize', on3DWindowResize);

  function animate3D() {
    requestAnimationFrame(animate3D);
    if (controls3D) {
      controls3D.autoRotate = is3DAutoRotate;
      controls3D.update();
    }
    Object.values(alertBeacons3D).forEach(b => {
      if (b) b.rotation.y += 0.03;
    });
    renderer3D.render(scene3D, camera3D);
  }
  animate3D();

  update3DSeats(currentSeatsData);
}

function createCameraMountAndFrustum() {
  const camGeo = new THREE.BoxGeometry(0.6, 0.4, 0.8);
  const camMat = new THREE.MeshStandardMaterial({ color: 0x00d7ff, emissive: 0x004466 });
  const camMesh = new THREE.Mesh(camGeo, camMat);
  camMesh.position.set(0, 7.5, 9);
  camMesh.rotation.x = Math.PI / 6;
  scene3D.add(camMesh);

  const lensGeo = new THREE.CylinderGeometry(0.15, 0.15, 0.3, 16);
  const lensMat = new THREE.MeshStandardMaterial({ color: 0xff3b30, emissive: 0xaa0000 });
  const lensMesh = new THREE.Mesh(lensGeo, lensMat);
  lensMesh.rotation.x = Math.PI / 2;
  lensMesh.position.set(0, 7.3, 8.5);
  scene3D.add(lensMesh);

  const coneGeo = new THREE.ConeGeometry(6, 10, 4);
  const coneMat = new THREE.MeshBasicMaterial({
    color: 0x00d7ff,
    wireframe: true,
    transparent: true,
    opacity: 0.15
  });
  cameraFrustumMesh3D = new THREE.Mesh(coneGeo, coneMat);
  cameraFrustumMesh3D.position.set(0, 3.5, 2);
  cameraFrustumMesh3D.rotation.x = -Math.PI / 3;
  scene3D.add(cameraFrustumMesh3D);
}

function update3DSeats(seats) {
  currentSeatsData = seats;
  if (!scene3D || !is3DInitialized) return;

  Object.values(seatMeshes3D).forEach(mesh => scene3D.remove(mesh));
  Object.values(alertBeacons3D).forEach(beacon => scene3D.remove(beacon));
  seatMeshes3D = {};
  alertBeacons3D = {};

  const rowGroups = {};
  seats.forEach(seat => {
    if (!rowGroups[seat.row_label]) rowGroups[seat.row_label] = [];
    rowGroups[seat.row_label].push(seat);
  });

  const sortedRows = Object.keys(rowGroups).sort();
  const seatGeo = new THREE.BoxGeometry(0.5, 0.5, 0.5);

  sortedRows.forEach((rowLabel, rIdx) => {
    const rowSeats = rowGroups[rowLabel].sort((a, b) => a.seat_number - b.seat_number);
    const zPos = -3 + (rIdx * 1.5);
    const elevation = rIdx * 0.35;

    rowSeats.forEach((seat, cIdx) => {
      const totalInRow = rowSeats.length;
      const xPos = ((cIdx - (totalInRow - 1) / 2) * 0.7);

      let color = 0x1c2536;
      let emissive = 0x000000;

      if (seat.status === 'suspicious_alert') {
        color = 0xff3b30;
        emissive = 0x990000;
      } else if (seat.status === 'phone_detected') {
        color = 0xff9500;
        emissive = 0x553000;
      }

      const mat = new THREE.MeshStandardMaterial({ color: color, emissive: emissive, roughness: 0.5 });
      const mesh = new THREE.Mesh(seatGeo, mat);
      mesh.position.set(xPos, 0.25 + elevation, zPos);
      mesh.userData = { seatId: seat.seat_id, status: seat.status };

      scene3D.add(mesh);
      seatMeshes3D[seat.seat_id] = mesh;

      if (seat.status === 'suspicious_alert') {
        const beaconGeo = new THREE.OctahedronGeometry(0.3);
        const beaconMat = new THREE.MeshBasicMaterial({ color: 0xff3b30, wireframe: true });
        const beaconMesh = new THREE.Mesh(beaconGeo, beaconMat);
        beaconMesh.position.set(xPos, 1.2 + elevation, zPos);
        scene3D.add(beaconMesh);
        alertBeacons3D[seat.seat_id] = beaconMesh;
      }
    });
  });
}

function set3DCameraAngle(angle) {
  if (!camera3D || !controls3D) return;
  document.getElementById('btn3DAngleSecurity').classList.remove('active');
  document.getElementById('btn3DAngleAudience').classList.remove('active');
  document.getElementById('btn3DAngleStage').classList.remove('active');

  if (angle === 'security') {
    document.getElementById('btn3DAngleSecurity').classList.add('active');
    camera3D.position.set(0, 9, 10);
    controls3D.target.set(0, 1, 0);
  } else if (angle === 'audience') {
    document.getElementById('btn3DAngleAudience').classList.add('active');
    camera3D.position.set(0, 3, 14);
    controls3D.target.set(0, 2, -5);
  } else if (angle === 'stage') {
    document.getElementById('btn3DAngleStage').classList.add('active');
    camera3D.position.set(0, 2, -6);
    controls3D.target.set(0, 1.5, 3);
  }
}

function toggle3DAutoRotate() {
  is3DAutoRotate = !is3DAutoRotate;
  const btn = document.getElementById('btn3DAutoRotate');
  if (is3DAutoRotate) btn.classList.add('active');
  else btn.classList.remove('active');
}

function on3DWindowResize() {
  const holder = document.getElementById('canvas3DHolder');
  if (!holder || !renderer3D || !camera3D) return;
  const w = holder.clientWidth;
  const h = holder.clientHeight;
  camera3D.aspect = w / h;
  camera3D.updateProjectionMatrix();
  renderer3D.setSize(w, h);
}

// ----------------------------------------------------
// Interactive Seating Arrangement Editor Handlers
// ----------------------------------------------------
function openSeatEditorModal() {
  const modal = document.getElementById('seatEditorModal');
  if (modal) modal.style.display = 'flex';
  renderSeatEditorTable(currentSeatsData);
}

function closeSeatEditorModal() {
  const modal = document.getElementById('seatEditorModal');
  if (modal) modal.style.display = 'none';
}

function closeSeatEditorOnOverlay(event) {
  if (event.target.id === 'seatEditorModal') closeSeatEditorModal();
}

function renderSeatEditorTable(seats) {
  const tbody = document.getElementById('seatEditorTableBody');
  const countEl = document.getElementById('seatCountText');
  if (countEl) countEl.textContent = seats.length;
  if (!tbody) return;

  tbody.innerHTML = '';
  if (seats.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:var(--text-muted);">No seats configured. Use the grid generator above!</td></tr>';
    return;
  }

  seats.forEach(seat => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong style="color:var(--accent-cyan);">${seat.seat_id}</strong></td>
      <td>${seat.row_label}</td>
      <td>${seat.seat_number}</td>
      <td>
        <button class="btn-action" style="background:rgba(255,59,48,0.2); color:#ff3b30;" onclick="deleteSingleSeat('${seat.seat_id}')">🗑 Delete</button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

async function applyBatchSeatConfiguration() {
  const rowsInput = document.getElementById('editRowLabels').value;
  const seatsPerRow = parseInt(document.getElementById('editSeatsPerRow').value, 10);

  const rowsList = rowsInput.split(',').map(s => s.trim().toUpperCase()).filter(s => s.length > 0);
  if (rowsList.length === 0 || isNaN(seatsPerRow) || seatsPerRow <= 0) {
    alert("Please enter valid row labels (e.g. A,B,C,D) and seats per row!");
    return;
  }

  try {
    const res = await fetch('/api/seats/configure', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rows: rowsList, seats_per_row: seatsPerRow })
    });
    if (res.ok) {
      await loadSeats();
      renderSeatEditorTable(currentSeatsData);
      alert(`Successfully generated layout with ${rowsList.length} rows x ${seatsPerRow} seats (${rowsList.length * seatsPerRow} total)!`);
    }
  } catch (err) {
    console.error("Failed to configure seats:", err);
    alert("Error updating seating layout.");
  }
}

async function addSingleSeatManual() {
  const seatId = document.getElementById('manualSeatId').value.trim().toUpperCase();
  const rowLabel = document.getElementById('manualRowLabel').value.trim().toUpperCase();
  const seatNum = parseInt(document.getElementById('manualSeatNum').value, 10);

  if (!seatId || !rowLabel || isNaN(seatNum)) {
    alert("Please enter Seat ID, Row Label, and Seat Number!");
    return;
  }

  try {
    const res = await fetch('/api/seats', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        seat_id: seatId,
        row_label: rowLabel,
        seat_number: seatNum,
        x_min: 0.1, y_min: 0.1, x_max: 0.2, y_max: 0.2
      })
    });
    if (res.ok) {
      await loadSeats();
      renderSeatEditorTable(currentSeatsData);
      document.getElementById('manualSeatId').value = '';
      document.getElementById('manualSeatNum').value = '';
    }
  } catch (err) {
    console.error("Failed to add seat:", err);
  }
}

async function deleteSingleSeat(seatId) {
  try {
    const res = await fetch(`/api/seats/${seatId}`, { method: 'DELETE' });
    if (res.ok) {
      await loadSeats();
      renderSeatEditorTable(currentSeatsData);
    }
  } catch (err) {
    console.error("Failed to delete seat:", err);
  }
}
