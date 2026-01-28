/**
 * Acoustic Fella - Main JavaScript
 */

// API Base URL
const API_BASE = '';

// Chart.js defaults
Chart.defaults.color = '#94a3b8';
Chart.defaults.borderColor = '#334155';

// DOM Elements
const quickAnalysisForm = document.getElementById('quick-analysis-form');
const resultsSection = document.getElementById('results');

// Event Listeners
if (quickAnalysisForm) {
    quickAnalysisForm.addEventListener('submit', handleQuickAnalysis);
}

/**
 * Handle quick room analysis form submission
 */
async function handleQuickAnalysis(e) {
    e.preventDefault();
    
    const length = parseFloat(document.getElementById('length').value);
    const width = parseFloat(document.getElementById('width').value);
    const height = parseFloat(document.getElementById('height').value);
    const unit = document.getElementById('unit').value;
    const roomType = document.getElementById('room-type').value;
    
    // Show loading state
    const submitBtn = quickAnalysisForm.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    submitBtn.textContent = 'Analyzing...';
    submitBtn.disabled = true;
    
    try {
        // First get quick analysis
        const quickResponse = await fetch(`${API_BASE}/api/quick-analysis`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ length, width, height, unit, room_type: roomType })
        });
        const quickData = await quickResponse.json();
        
        // Then get detailed room analysis
        const roomResponse = await fetch(`${API_BASE}/api/analyze-room`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ length, width, height, unit, room_type: roomType })
        });
        const roomData = await roomResponse.json();
        
        if (quickData.success && roomData.success) {
            displayResults(quickData, roomData, unit);
            resultsSection.classList.remove('hidden');
            resultsSection.scrollIntoView({ behavior: 'smooth' });
        } else {
            alert('Error analyzing room: ' + (quickData.error || roomData.error));
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error analyzing room. Please try again.');
    } finally {
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;
    }
}

/**
 * Display analysis results
 */
function displayResults(quickData, roomData, unit) {
    const unitLabel = unit === 'metric' ? 'm' : 'ft';
    const analysis = quickData.analysis;
    const report = roomData.room_report;
    const speaker = quickData.speaker_placement;
    
    // Room Info
    document.getElementById('room-info').innerHTML = `
        <p><strong>Dimensions:</strong> <span class="value">${analysis.room_info.dimensions}</span></p>
        <p><strong>Volume:</strong> <span class="value">${analysis.room_info.volume.toFixed(1)} ${unitLabel}³</span></p>
        <p><strong>Ratio Quality:</strong> <span class="${getRatingClass(analysis.modal_analysis.ratio_quality)}">${analysis.modal_analysis.ratio_quality}</span></p>
        <p><strong>Current Ratios:</strong> <span class="value">${report.ratio_analysis.current_ratios.join(' : ')}</span></p>
    `;
    
    // Schroeder Info
    document.getElementById('schroeder-info').innerHTML = `
        <p><strong>Schroeder Frequency:</strong> <span class="value">${analysis.room_info.schroeder_frequency} Hz</span></p>
        <p><strong>Bass Trap Range:</strong> <span class="value">${roomData.schroeder.bass_trap_range}</span></p>
        <p><strong>Absorber Range:</strong> <span class="value">${roomData.schroeder.absorber_range}</span></p>
        <p class="info-note">Below Schroeder: Modal behavior (bass traps needed)<br>Above: Diffuse field (absorbers effective)</p>
    `;
    
    // Modal Analysis
    const bonelloStatus = analysis.modal_analysis.passes_bonello ? 
        '<span class="good">✓ Passes</span>' : '<span class="bad">✗ Fails</span>';
    
    document.getElementById('modal-info').innerHTML = `
        <p><strong>First Mode:</strong> <span class="value">${analysis.modal_analysis.first_mode?.toFixed(1) || 'N/A'} Hz</span></p>
        <p><strong>Modes Under 200Hz:</strong> <span class="value">${analysis.modal_analysis.total_modes_under_200hz}</span></p>
        <p><strong>Bonello Criterion:</strong> ${bonelloStatus}</p>
        <p><strong>Problem Frequencies:</strong></p>
        <p class="value">${analysis.problem_frequencies.join(' Hz, ')} Hz</p>
    `;
    
    // Speaker Placement
    document.getElementById('speaker-info').innerHTML = `
        <p><strong>Listening Position:</strong> <span class="value">${speaker.listening_position.from_front_wall}</span> from front wall</p>
        <p><strong>Speaker Distance:</strong> <span class="value">${speaker.distance_to_speakers}</span></p>
        <p><strong>Stereo Angle:</strong> <span class="value">${speaker.angles.stereo_angle}</span></p>
        <p><strong>Toe-in:</strong> <span class="value">${speaker.angles.toe_in}</span></p>
    `;
    
    // Quick Recommendations
    displayRecommendations(analysis.quick_recommendations);
    
    // Room Modes Chart
    createModesChart(report);
}

/**
 * Get CSS class based on rating
 */
function getRatingClass(rating) {
    switch (rating.toLowerCase()) {
        case 'excellent': return 'good';
        case 'good': return 'good';
        case 'fair': return 'warning';
        case 'poor': return 'bad';
        default: return '';
    }
}

/**
 * Display quick recommendations
 */
function displayRecommendations(recommendations) {
    const container = document.getElementById('recommendations');
    container.innerHTML = recommendations.map(rec => `
        <div class="recommendation-item priority-${rec.priority?.toLowerCase() || 'medium'}">
            <h4>${rec.item}</h4>
            <p><strong>Quantity:</strong> ${rec.quantity}</p>
            ${rec.size ? `<p><strong>Size:</strong> ${rec.size}</p>` : ''}
            ${rec.minimum_depth ? `<p><strong>Min Depth:</strong> ${rec.minimum_depth}</p>` : ''}
            ${rec.type ? `<p><strong>Type:</strong> ${rec.type}</p>` : ''}
            <p><strong>Priority:</strong> ${rec.priority || 'Medium'}</p>
        </div>
    `).join('');
}

/**
 * Create room modes bar chart
 */
function createModesChart(report) {
    const ctx = document.getElementById('modes-chart').getContext('2d');
    
    // Destroy existing chart if it exists
    if (window.modesChart) {
        window.modesChart.destroy();
    }
    
    // Get mode frequencies and types
    const modes = report.modes.first_10;
    const labels = modes.map(m => `${m.freq.toFixed(0)} Hz`);
    const data = modes.map(m => m.freq);
    const colors = modes.map(m => {
        switch(m.type) {
            case 'axial': return '#ef4444';
            case 'tangential': return '#f59e0b';
            case 'oblique': return '#22c55e';
            default: return '#6366f1';
        }
    });
    
    window.modesChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Room Modes',
                data: data,
                backgroundColor: colors,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        afterLabel: function(context) {
                            const mode = modes[context.dataIndex];
                            return `Type: ${mode.type}\nMode: ${mode.mode}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Frequency (Hz)'
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Room Modes'
                    }
                }
            }
        }
    });
}

/**
 * Create frequency response chart
 */
function createFrequencyResponseChart(frequencies, magnitudes, canvasId) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: frequencies,
            datasets: [{
                label: 'Magnitude (dB)',
                data: magnitudes,
                borderColor: '#6366f1',
                backgroundColor: 'rgba(99, 102, 241, 0.1)',
                fill: true,
                tension: 0.1,
                pointRadius: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    type: 'logarithmic',
                    title: {
                        display: true,
                        text: 'Frequency (Hz)'
                    },
                    min: 20,
                    max: 20000
                },
                y: {
                    title: {
                        display: true,
                        text: 'Level (dB)'
                    }
                }
            }
        }
    });
}

/**
 * Create absorption coefficients chart
 */
function createAbsorptionChart(coefficients, containerId) {
    const container = document.getElementById(containerId);
    const frequencies = Object.keys(coefficients).sort((a, b) => parseInt(a) - parseInt(b));
    
    container.innerHTML = frequencies.map(freq => {
        const value = coefficients[freq];
        const percentage = value * 100;
        return `
            <div class="absorption-bar">
                <span class="absorption-freq">${freq} Hz</span>
                <div class="absorption-bar-container">
                    <div class="absorption-bar-fill" style="width: ${percentage}%"></div>
                </div>
                <span class="absorption-value">${value.toFixed(2)}</span>
            </div>
        `;
    }).join('');
}

/**
 * File upload handling for REW files
 */
async function uploadREWFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await fetch(`${API_BASE}/api/upload-rew`, {
            method: 'POST',
            body: formData
        });
        return await response.json();
    } catch (error) {
        console.error('Error uploading file:', error);
        return { success: false, error: error.message };
    }
}

/**
 * Generate treatment plan
 */
async function generateTreatmentPlan(roomData) {
    try {
        const response = await fetch(`${API_BASE}/api/generate-treatment-plan`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(roomData)
        });
        return await response.json();
    } catch (error) {
        console.error('Error generating treatment plan:', error);
        return { success: false, error: error.message };
    }
}

/**
 * Get panel design
 */
async function designPanel(panelConfig) {
    try {
        const response = await fetch(`${API_BASE}/api/design-panel`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(panelConfig)
        });
        return await response.json();
    } catch (error) {
        console.error('Error designing panel:', error);
        return { success: false, error: error.message };
    }
}

/**
 * Calculate speaker placement
 */
async function calculateSpeakerPlacement(roomData) {
    try {
        const response = await fetch(`${API_BASE}/api/speaker-placement`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(roomData)
        });
        return await response.json();
    } catch (error) {
        console.error('Error calculating speaker placement:', error);
        return { success: false, error: error.message };
    }
}

/**
 * Utility: Format number with unit
 */
function formatWithUnit(value, unit, decimals = 1) {
    return `${value.toFixed(decimals)} ${unit}`;
}

/**
 * Utility: Get priority color
 */
function getPriorityColor(priority) {
    switch (priority) {
        case 1: return '#ef4444';  // Red - Critical
        case 2: return '#f59e0b';  // Orange - High
        case 3: return '#22c55e';  // Green - Medium
        default: return '#6366f1'; // Blue - Normal
    }
}
