/* AcFella - Main JavaScript */
/* ============================================================ */

/* Utility: API call helper */
async function apiCall(url, method = 'GET', body = null) {
    const opts = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    if (body) opts.body = JSON.stringify(body);
    const resp = await fetch(url, opts);
    return resp.json();
}

/* Format numbers */
function fmt(num, decimals = 2) {
    if (typeof num !== 'number') return num;
    return num.toFixed(decimals);
}

/* Show/hide elements */
function show(id) { document.getElementById(id).style.display = ''; }
function hide(id) { document.getElementById(id).style.display = 'none'; }

/* ============================================================ */
/* Quick Analysis (legacy - index page fallback) */
function setupQuickAnalysis() {
    const form = document.getElementById('quick-analysis-form');
    if (!form) return;
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());
        // Convert numeric fields
        ['length', 'width', 'height'].forEach(k => { data[k] = parseFloat(data[k]); });
        try {
            const result = await apiCall('/api/analyze-room', 'POST', data);
            if (result.success) {
                displayQuickResults(result);
            } else {
                alert('Error: ' + result.error);
            }
        } catch (err) {
            console.error(err);
            alert('Error running analysis');
        }
    });
}

function displayQuickResults(data) {
    const container = document.getElementById('quick-results');
    if (!container) return;
    container.style.display = '';
    container.innerHTML = `
        <div class="result-card">
            <h3>Room Analysis Summary</h3>
            <div class="result-content">
                <p><strong>Volume:</strong> ${data.room_info.volume} m&sup3;</p>
                <p><strong>Schroeder Frequency:</strong> ${data.schroeder.frequency} Hz</p>
                <p><strong>Total Modes:</strong> ${data.modes.length}</p>
                <p><strong>Bonello:</strong> <span class="${data.bonello.passes_bonello ? 'good' : 'bad'}">${data.bonello.passes_bonello ? 'PASSES' : 'FAILS'}</span></p>
            </div>
        </div>
    `;
}

/* ============================================================ */
/* Chart.js Defaults */
if (typeof Chart !== 'undefined') {
    Chart.defaults.color = '#9ca3af';
    Chart.defaults.borderColor = 'rgba(255,255,255,0.05)';
    Chart.defaults.font.family = "'Inter', sans-serif";
    Chart.defaults.font.size = 12;
}

/* ============================================================ */
/* Init */
document.addEventListener('DOMContentLoaded', () => {
    setupQuickAnalysis();
});
