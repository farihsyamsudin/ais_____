// ==============================
// Configuration
// ==============================
const API_BASE_URL = 'http://localhost:5020';

// Default params — harus sinkron dengan backend/app.py DEFAULT_PARAMS
const DEFAULT_PARAMS = {
    proximity_km:           0.5,
    duration_min:           30,
    candidate_duration_min: 15,
    sog_threshold:          2.0,
    port_distance_km:       0.5,
    time_gap_min:           10
};

// Default date range — sinkron dengan seed_database.py test scenarios
const DEFAULT_START = '2024-01-01T10:00';
const DEFAULT_END   = '2024-01-01T22:00';

// Ports Batam/SG/Johor — sinkron dengan V4/main.py + backend/app.py
const PORTS = [
    { name: "Batu Ampar (Cargo)",        lat: 1.1617, lon: 104.0047 },
    { name: "Kabil (Citranusa/Oil)",      lat: 1.1108, lon: 104.1403 },
    { name: "Sekupang (Ferry/Intl)",      lat: 1.1261, lon: 103.9278 },
    { name: "Tanjung Uncang (Shipyard)",  lat: 1.0750, lon: 103.9050 },
    { name: "Nongsa Pura",               lat: 1.1960, lon: 104.0830 },
    { name: "Telaga Punggur",            lat: 1.0370, lon: 104.1480 },
    { name: "Batam Centre",              lat: 1.1320, lon: 104.0520 },
    { name: "Harbour Bay",               lat: 1.1550, lon: 103.9950 },
    { name: "Tanjung Uban (Oil)",        lat: 1.0713, lon: 104.2209 },
    { name: "Jurong Port",               lat: 1.2604, lon: 103.6888 },
    { name: "Pasir Panjang",             lat: 1.2761, lon: 103.7914 },
    { name: "Keppel Terminal",           lat: 1.2600, lon: 103.8300 },
    { name: "Brani Terminal",            lat: 1.2630, lon: 103.8350 },
    { name: "Tanjong Pagar",             lat: 1.2670, lon: 103.8450 },
    { name: "Marina South Pier",         lat: 1.2700, lon: 103.8640 },
    { name: "Changi Naval Base",         lat: 1.3200, lon: 104.0200 },
    { name: "Changi Cargo",              lat: 1.3500, lon: 104.0300 },
    { name: "Tuas Mega Port",            lat: 1.2900, lon: 103.6200 },
    { name: "Sembawang",                 lat: 1.4550, lon: 103.8250 },
    { name: "Tanjung Pelepas (PTP)",     lat: 1.3600, lon: 103.5500 },
    { name: "Tanjung Bin (Power/Coal)",  lat: 1.3300, lon: 103.5400 },
    { name: "Kukup Anchorage",           lat: 1.3200, lon: 103.4500 },
    { name: "Johor Port (Pasir Gudang)", lat: 1.4300, lon: 103.9000 },
    { name: "Tanjung Langsat",           lat: 1.4500, lon: 104.0100 },
];

// Global state
let map     = null;
let markers = [];

// ==============================
// Initialization
// ==============================

document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
    setupEventListeners();
    setDefaultDates();
    updateSliderValues();
});

async function initializeApp() {
    await checkHealth();
    await loadStats();
    initializeMap();
}

// ==============================
// API Functions
// ==============================

async function checkHealth() {
    const indicator = document.getElementById('statusIndicator');
    const dot  = indicator.querySelector('.status-dot');
    const text = indicator.querySelector('span:last-child');

    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        const data = await response.json();

        if (data.status === 'healthy') {
            dot.className  = 'status-dot status-healthy';
            text.textContent = `Connected · ${(data.document_count || 0).toLocaleString()} signals`;
        } else {
            dot.className  = 'status-dot status-unhealthy';
            text.textContent = 'Disconnected';
        }
    } catch (error) {
        dot.className  = 'status-dot status-unhealthy';
        text.textContent = 'Error — Backend not running?';
        console.error('Health check failed:', error);
    }
}

async function loadStats() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/stats`);
        const data = await response.json();

        document.getElementById('totalSignals').textContent  = (data.total_signals  || 0).toLocaleString();
        document.getElementById('uniqueVessels').textContent = (data.unique_vessels || 0).toLocaleString();
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

async function runDetection() {
    const startDate = document.getElementById('startDate').value;
    const endDate   = document.getElementById('endDate').value;

    if (!startDate || !endDate) {
        alert('Please select both start and end dates');
        return;
    }

    const parameters = {
        proximity_km:           parseFloat(document.getElementById('proximityThreshold').value),
        duration_min:           parseInt(document.getElementById('durationThreshold').value),
        candidate_duration_min: DEFAULT_PARAMS.candidate_duration_min,
        sog_threshold:          parseFloat(document.getElementById('sogThreshold').value),
        port_distance_km:       parseFloat(document.getElementById('portDistance').value),
        time_gap_min:           DEFAULT_PARAMS.time_gap_min
    };

    document.getElementById('loadingState').classList.remove('hidden');
    document.getElementById('detectBtn').disabled = true;

    try {
        const response = await fetch(`${API_BASE_URL}/api/detect`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                start_date: new Date(startDate).toISOString(),
                end_date:   new Date(endDate).toISOString(),
                parameters
            })
        });

        const data = await response.json();

        if (response.ok) {
            displayResults(data);
        } else {
            alert(`Error: ${data.error}`);
        }
    } catch (error) {
        console.error('Detection failed:', error);
        alert('Detection failed. Is the backend running on port 5000?');
    } finally {
        document.getElementById('loadingState').classList.add('hidden');
        document.getElementById('detectBtn').disabled = false;
    }
}

// ==============================
// Display Functions
// ==============================

function displayResults(data) {
    document.getElementById('confirmedCount').textContent = data.confirmed_anomalies.length;
    document.getElementById('candidateCount').textContent = data.candidate_anomalies.length;

    document.getElementById('resultsSection').classList.remove('hidden');

    // Clear previous markers
    markers.forEach(m => map.removeLayer(m));
    markers = [];

    displayConfirmedTable(data.confirmed_anomalies);
    displayCandidateTable(data.candidate_anomalies);
    displayAnomaliesOnMap(data.confirmed_anomalies, data.candidate_anomalies);

    document.getElementById('resultsSection').scrollIntoView({ behavior: 'smooth' });
}

function displayConfirmedTable(anomalies) {
    const tbody = document.getElementById('confirmedTable');
    tbody.innerHTML = '';

    if (anomalies.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="px-4 py-3 text-center text-gray-500">No confirmed anomalies detected</td></tr>';
        return;
    }

    anomalies.forEach(anomaly => {
        const row = document.createElement('tr');
        row.className = 'hover:bg-gray-50 cursor-pointer';
        row.onclick = () => focusOnAnomaly(anomaly.lat, anomaly.lon);

        row.innerHTML = `
            <td class="px-4 py-3 text-sm font-mono text-gray-900">${anomaly.mmsi_1}<br>${anomaly.mmsi_2}</td>
            <td class="px-4 py-3 text-sm text-gray-900">${anomaly.duration_min.toFixed(1)} min</td>
            <td class="px-4 py-3 text-sm text-gray-500">${new Date(anomaly.start_time).toLocaleString()}</td>
            <td class="px-4 py-3 text-sm text-gray-500">${anomaly.lat.toFixed(5)}, ${anomaly.lon.toFixed(5)}</td>
        `;
        tbody.appendChild(row);
    });
}

function displayCandidateTable(anomalies) {
    const tbody = document.getElementById('candidateTable');
    tbody.innerHTML = '';

    if (anomalies.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="px-4 py-3 text-center text-gray-500">No candidate anomalies detected</td></tr>';
        return;
    }

    anomalies.forEach(anomaly => {
        const row = document.createElement('tr');
        row.className = 'hover:bg-gray-50 cursor-pointer';
        row.onclick = () => focusOnAnomaly(anomaly.lat, anomaly.lon);

        row.innerHTML = `
            <td class="px-4 py-3 text-sm font-mono text-gray-900">${anomaly.mmsi_1}<br>${anomaly.mmsi_2}</td>
            <td class="px-4 py-3 text-sm text-gray-900">${anomaly.duration_min.toFixed(1)} min</td>
            <td class="px-4 py-3 text-sm text-gray-500">${new Date(anomaly.start_time).toLocaleString()}</td>
            <td class="px-4 py-3 text-sm text-gray-500">${anomaly.lat.toFixed(5)}, ${anomaly.lon.toFixed(5)}</td>
        `;
        tbody.appendChild(row);
    });
}

function displayAnomaliesOnMap(confirmed, candidates) {
    // Confirmed = merah
    confirmed.forEach(anomaly => {
        const marker = L.circleMarker([anomaly.lat, anomaly.lon], {
            radius: 9, fillColor: '#ef4444', color: '#991b1b',
            weight: 2, opacity: 1, fillOpacity: 0.8
        }).addTo(map);

        marker.bindPopup(`
            <strong>🚨 Confirmed Anomaly</strong><br>
            MMSI 1: <code>${anomaly.mmsi_1}</code><br>
            MMSI 2: <code>${anomaly.mmsi_2}</code><br>
            Duration: <b>${anomaly.duration_min.toFixed(1)} min</b><br>
            Start: ${new Date(anomaly.start_time).toLocaleString()}<br>
            End:   ${new Date(anomaly.end_time).toLocaleString()}<br>
            Loc: ${anomaly.lat.toFixed(5)}, ${anomaly.lon.toFixed(5)}
        `);
        markers.push(marker);
    });

    // Candidates = kuning
    candidates.forEach(anomaly => {
        const marker = L.circleMarker([anomaly.lat, anomaly.lon], {
            radius: 7, fillColor: '#f59e0b', color: '#92400e',
            weight: 2, opacity: 1, fillOpacity: 0.7
        }).addTo(map);

        marker.bindPopup(`
            <strong>⚠️ Candidate Anomaly</strong><br>
            MMSI 1: <code>${anomaly.mmsi_1}</code><br>
            MMSI 2: <code>${anomaly.mmsi_2}</code><br>
            Duration: <b>${anomaly.duration_min.toFixed(1)} min</b><br>
            Start: ${new Date(anomaly.start_time).toLocaleString()}<br>
            Loc: ${anomaly.lat.toFixed(5)}, ${anomaly.lon.toFixed(5)}
        `);
        markers.push(marker);
    });

    // Fit map ke semua markers
    if (markers.length > 0) {
        const group = L.featureGroup(markers);
        map.fitBounds(group.getBounds().pad(0.15));
    }
}

// ==============================
// Map Functions
// ==============================

function initializeMap() {
    // Center: Batam / Selat Singapura
    map = L.map('map', {
        center: [1.25, 103.95],
        zoom: 10,
        zoomControl: true,
        scrollWheelZoom: true
    });

    // Dark basemap (mirip dengan output folium V4)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '© OpenStreetMap © CARTO',
        subdomains: 'abcd',
        maxZoom: 19
    }).addTo(map);

    setTimeout(() => map.invalidateSize(), 100);

    // Port markers — semua 24 port dari V4/main.py
    PORTS.forEach(port => {
        L.circleMarker([port.lat, port.lon], {
            radius: 5,
            fillColor: '#3b82f6',
            color: '#1d4ed8',
            weight: 1.5,
            opacity: 1,
            fillOpacity: 0.8
        }).addTo(map).bindPopup(`<strong>🚢 ${port.name}</strong>`);
    });
}

function focusOnAnomaly(lat, lon) {
    map.setView([lat, lon], 13);
    markers.forEach(marker => {
        const ll = marker.getLatLng();
        if (Math.abs(ll.lat - lat) < 0.0001 && Math.abs(ll.lng - lon) < 0.0001) {
            marker.openPopup();
        }
    });
}

// ==============================
// Event Listeners & UI
// ==============================

function setupEventListeners() {
    document.getElementById('detectBtn').addEventListener('click', runDetection);

    document.getElementById('resetBtn').addEventListener('click', () => {
        setDefaultDates();
        document.getElementById('proximityThreshold').value = DEFAULT_PARAMS.proximity_km;
        document.getElementById('durationThreshold').value  = DEFAULT_PARAMS.duration_min;
        document.getElementById('sogThreshold').value       = DEFAULT_PARAMS.sog_threshold;
        document.getElementById('portDistance').value       = DEFAULT_PARAMS.port_distance_km;
        updateSliderValues();
    });

    ['proximityThreshold', 'durationThreshold', 'sogThreshold', 'portDistance']
        .forEach(id => document.getElementById(id).addEventListener('input', updateSliderValues));
}

function updateSliderValues() {
    document.getElementById('proximityValue').textContent = document.getElementById('proximityThreshold').value;
    document.getElementById('durationValue').textContent  = document.getElementById('durationThreshold').value;
    document.getElementById('sogValue').textContent       = document.getElementById('sogThreshold').value;
    document.getElementById('portDistValue').textContent  = document.getElementById('portDistance').value;
}

function setDefaultDates() {
    document.getElementById('startDate').value = DEFAULT_START;
    document.getElementById('endDate').value   = DEFAULT_END;
}

// Auto-refresh stats every 30 seconds
setInterval(loadStats, 30000);