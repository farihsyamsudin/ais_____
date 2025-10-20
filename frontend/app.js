// Configuration
const API_BASE_URL = 'http://localhost:5000';

// Global state
let map = null;
let markers = [];

// ==============================
// Initialization
// ==============================

document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
    setupEventListeners();
    setDefaultDates();
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
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        const data = await response.json();
        
        const indicator = document.getElementById('statusIndicator');
        const dot = indicator.querySelector('.status-dot');
        const text = indicator.querySelector('span:last-child');
        
        if (data.status === 'healthy') {
            dot.className = 'status-dot status-healthy';
            text.textContent = 'Connected';
        } else {
            dot.className = 'status-dot status-unhealthy';
            text.textContent = 'Disconnected';
        }
    } catch (error) {
        const indicator = document.getElementById('statusIndicator');
        const dot = indicator.querySelector('.status-dot');
        const text = indicator.querySelector('span:last-child');
        dot.className = 'status-dot status-unhealthy';
        text.textContent = 'Error';
        console.error('Health check failed:', error);
    }
}

async function loadStats() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/stats`);
        const data = await response.json();
        
        document.getElementById('totalSignals').textContent = data.total_signals.toLocaleString();
        document.getElementById('uniqueVessels').textContent = data.unique_vessels.toLocaleString();
    } catch (error) {
        console.error('Failed to load stats:', error);
    }
}

async function runDetection() {
    const startDate = document.getElementById('startDate').value;
    const endDate = document.getElementById('endDate').value;
    
    if (!startDate || !endDate) {
        alert('Please select both start and end dates');
        return;
    }
    
    // Get parameters
    const parameters = {
        proximity_km: parseFloat(document.getElementById('proximityThreshold').value),
        duration_min: parseInt(document.getElementById('durationThreshold').value),
        candidate_duration_min: 22,
        sog_threshold: parseFloat(document.getElementById('sogThreshold').value),
        port_distance_km: parseFloat(document.getElementById('portDistance').value),
        time_gap_min: 10
    };
    
    // Show loading
    document.getElementById('loadingState').classList.remove('hidden');
    document.getElementById('detectBtn').disabled = true;
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/detect`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                start_date: new Date(startDate).toISOString(),
                end_date: new Date(endDate).toISOString(),
                parameters: parameters
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
        alert('Detection failed. Please check console for details.');
    } finally {
        document.getElementById('loadingState').classList.add('hidden');
        document.getElementById('detectBtn').disabled = false;
    }
}

// ==============================
// Display Functions
// ==============================

function displayResults(data) {
    // Update counts
    document.getElementById('confirmedCount').textContent = data.confirmed_anomalies.length;
    document.getElementById('candidateCount').textContent = data.candidate_anomalies.length;
    
    // Show results section
    document.getElementById('resultsSection').classList.remove('hidden');
    
    // Clear previous markers
    markers.forEach(marker => map.removeLayer(marker));
    markers = [];
    
    // Display confirmed anomalies
    displayConfirmedTable(data.confirmed_anomalies);
    displayCandidateTable(data.candidate_anomalies);
    
    // Update map
    displayAnomaliesOnMap(data.confirmed_anomalies, data.candidate_anomalies);
    
    // Scroll to results
    document.getElementById('resultsSection').scrollIntoView({ behavior: 'smooth' });
}

function displayConfirmedTable(anomalies) {
    const tbody = document.getElementById('confirmedTable');
    tbody.innerHTML = '';
    
    if (anomalies.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="px-4 py-3 text-center text-gray-500">No confirmed anomalies detected</td></tr>';
        return;
    }
    
    anomalies.forEach(anomaly => {
        const row = document.createElement('tr');
        row.className = 'hover:bg-gray-50 cursor-pointer';
        row.onclick = () => focusOnAnomaly(anomaly.lat, anomaly.lon);
        
        const startTime = new Date(anomaly.start_time).toLocaleString();
        
        row.innerHTML = `
            <td class="px-4 py-3 text-sm text-gray-900">${anomaly.mmsi_1} / ${anomaly.mmsi_2}</td>
            <td class="px-4 py-3 text-sm text-gray-900">${anomaly.duration_min.toFixed(1)} min</td>
            <td class="px-4 py-3 text-sm text-gray-500">${startTime}</td>
        `;
        
        tbody.appendChild(row);
    });
}

function displayCandidateTable(anomalies) {
    const tbody = document.getElementById('candidateTable');
    tbody.innerHTML = '';
    
    if (anomalies.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="px-4 py-3 text-center text-gray-500">No candidate anomalies detected</td></tr>';
        return;
    }
    
    anomalies.forEach(anomaly => {
        const row = document.createElement('tr');
        row.className = 'hover:bg-gray-50 cursor-pointer';
        row.onclick = () => focusOnAnomaly(anomaly.lat, anomaly.lon);
        
        const startTime = new Date(anomaly.start_time).toLocaleString();
        
        row.innerHTML = `
            <td class="px-4 py-3 text-sm text-gray-900">${anomaly.mmsi_1} / ${anomaly.mmsi_2}</td>
            <td class="px-4 py-3 text-sm text-gray-900">${anomaly.duration_min.toFixed(1)} min</td>
            <td class="px-4 py-3 text-sm text-gray-500">${startTime}</td>
        `;
        
        tbody.appendChild(row);
    });
}

function displayAnomaliesOnMap(confirmed, candidates) {
    // Add confirmed anomalies (red markers)
    confirmed.forEach(anomaly => {
        const marker = L.circleMarker([anomaly.lat, anomaly.lon], {
            radius: 8,
            fillColor: '#ef4444',
            color: '#991b1b',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.7
        }).addTo(map);
        
        marker.bindPopup(`
            <strong>Confirmed Anomaly</strong><br>
            MMSI: ${anomaly.mmsi_1} & ${anomaly.mmsi_2}<br>
            Duration: ${anomaly.duration_min.toFixed(1)} min<br>
            Start: ${new Date(anomaly.start_time).toLocaleString()}<br>
            Location: ${anomaly.lat.toFixed(4)}, ${anomaly.lon.toFixed(4)}
        `);
        
        markers.push(marker);
    });
    
    // Add candidate anomalies (yellow markers)
    candidates.forEach(anomaly => {
        const marker = L.circleMarker([anomaly.lat, anomaly.lon], {
            radius: 6,
            fillColor: '#f59e0b',
            color: '#92400e',
            weight: 2,
            opacity: 1,
            fillOpacity: 0.6
        }).addTo(map);
        
        marker.bindPopup(`
            <strong>Candidate Anomaly</strong><br>
            MMSI: ${anomaly.mmsi_1} & ${anomaly.mmsi_2}<br>
            Duration: ${anomaly.duration_min.toFixed(1)} min<br>
            Start: ${new Date(anomaly.start_time).toLocaleString()}<br>
            Location: ${anomaly.lat.toFixed(4)}, ${anomaly.lon.toFixed(4)}
        `);
        
        markers.push(marker);
    });
    
    // Fit map to show all markers
    if (markers.length > 0) {
        const group = L.featureGroup(markers);
        map.fitBounds(group.getBounds().pad(0.1));
    }
}

// ==============================
// Map Functions
// ==============================

function initializeMap() {
    // Initialize Leaflet map centered on Selat Sunda
    map = L.map('map', {
        center: [-6.0, 105.5],
        zoom: 9,
        zoomControl: true,
        scrollWheelZoom: true
    });
    
    // Add OpenStreetMap tiles with error handling
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19,
        minZoom: 7
    }).addTo(map);
    
    // Force map to invalidate size after a short delay
    setTimeout(() => {
        map.invalidateSize();
    }, 100);
    
    // Add port markers
    const ports = [
        {"name": "Pelabuhan Merak", "lat": -5.8933, "lon": 106.0086},
        {"name": "Pelabuhan Ciwandan", "lat": -5.9525, "lon": 106.0358},
        {"name": "Pelabuhan Bojonegara", "lat": -5.8995, "lon": 106.0657},
        {"name": "Pelabuhan Bakauheni", "lat": -5.8711, "lon": 105.7421},
        {"name": "Pelabuhan Panjang", "lat": -5.4558, "lon": 105.3134}
    ];
    
    ports.forEach(port => {
        L.marker([port.lat, port.lon], {
            icon: L.divIcon({
                className: 'port-marker',
                html: '<div style="background-color: #3b82f6; width: 12px; height: 12px; border-radius: 50%; border: 2px solid white;"></div>',
                iconSize: [16, 16]
            })
        }).addTo(map).bindPopup(`<strong>${port.name}</strong>`);
    });
}

function focusOnAnomaly(lat, lon) {
    map.setView([lat, lon], 12);
    
    // Find and open popup for this marker
    markers.forEach(marker => {
        const markerLatLng = marker.getLatLng();
        if (Math.abs(markerLatLng.lat - lat) < 0.0001 && Math.abs(markerLatLng.lng - lon) < 0.0001) {
            marker.openPopup();
        }
    });
}

// ==============================
// Event Listeners
// ==============================

function setupEventListeners() {
    // Detect button
    document.getElementById('detectBtn').addEventListener('click', runDetection);
    
    // Reset button
    document.getElementById('resetBtn').addEventListener('click', () => {
        setDefaultDates();
        document.getElementById('proximityThreshold').value = 0.2;
        document.getElementById('durationThreshold').value = 30;
        document.getElementById('sogThreshold').value = 0.5;
        document.getElementById('portDistance').value = 10;
        updateSliderValues();
    });
    
    // Slider value updates
    document.getElementById('proximityThreshold').addEventListener('input', updateSliderValues);
    document.getElementById('durationThreshold').addEventListener('input', updateSliderValues);
    document.getElementById('sogThreshold').addEventListener('input', updateSliderValues);
    document.getElementById('portDistance').addEventListener('input', updateSliderValues);
}

function updateSliderValues() {
    document.getElementById('proximityValue').textContent = document.getElementById('proximityThreshold').value;
    document.getElementById('durationValue').textContent = document.getElementById('durationThreshold').value;
    document.getElementById('sogValue').textContent = document.getElementById('sogThreshold').value;
    document.getElementById('portDistValue').textContent = document.getElementById('portDistance').value;
}

function setDefaultDates() {
    // Set default to last 24 hours from test data start
    const start = new Date('2023-08-01T10:00:00');
    const end = new Date('2023-08-01T12:00:00');
    
    document.getElementById('startDate').value = formatDateTimeLocal(start);
    document.getElementById('endDate').value = formatDateTimeLocal(end);
}

function formatDateTimeLocal(date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    
    return `${year}-${month}-${day}T${hours}:${minutes}`;
}

// Auto-refresh stats every 30 seconds
setInterval(loadStats, 30000);