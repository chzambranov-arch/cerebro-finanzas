const CONFIG = {
    API_BASE: '/api/v1'
};

let chartDaily = null;
let chartSections = null;
let rawExpenses = [];
let dashboardData = {};

document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
    loadData('month');
});

function checkAuth() {
    // Try to get token from shared localStorage domain (same origin)
    const token = localStorage.getItem('auth_token');
    if (!token) {
        alert('Por favor inicia sesión en la App primero.');
        window.location.href = '/';
    }
}

function getHeaders() {
    const token = localStorage.getItem('auth_token');
    return {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
    };
}

async function loadData(filter = 'month') {
    try {
        // 1. Fetch Expenses Listing
        const resExpenses = await fetch(`${CONFIG.API_BASE}/expenses/`, { headers: getHeaders() });
        if (resExpenses.status === 401) return logout();
        rawExpenses = await resExpenses.json();

        // 2. Fetch Dashboard Summary (Budget)
        const resDash = await fetch(`${CONFIG.API_BASE}/expenses/dashboard`, { headers: getHeaders() });
        dashboardData = await resDash.json();

        // Filter Logic
        let filteredDetails = rawExpenses;
        if (filter === 'month') {
            const now = new Date();
            filteredDetails = rawExpenses.filter(e => {
                const d = new Date(e.date);
                return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
            });
        }

        updateKPIs(filteredDetails, dashboardData);
        renderCharts(filteredDetails);
        renderTable(filteredDetails);

        document.getElementById('user-name').textContent = dashboardData.user_name || 'Usuario';

    } catch (e) {
        console.error("Error loading analytics:", e);
    }
}

function updateKPIs(expenses, dashMeta) {
    const total = expenses.reduce((sum, e) => sum + e.amount, 0);
    const count = expenses.length;
    const avg = count > 0 ? total / count : 0;

    // Use the same values as the mobile app
    const budget = dashMeta.monthly_budget || 0;
    const balance = dashMeta.available_balance || 0;  // Use API value, not calculated

    document.getElementById('kpi-total').textContent = formatMoney(total);

    // Logic for balance/saving based on filter
    if (expenses.length === rawExpenses.length) {
        // Historic
        document.getElementById('kpi-budget').textContent = "Histórico";
        document.getElementById('kpi-balance').textContent = "-";
        document.getElementById('kpi-saving-rate').textContent = "-";
    } else {
        // Monthly
        document.getElementById('kpi-budget').textContent = `Presupuesto: ${formatMoney(budget)}`;
        document.getElementById('kpi-balance').textContent = formatMoney(balance);

        const savingRate = budget > 0 ? ((balance / budget) * 100).toFixed(1) : 0;
        const savingEl = document.getElementById('kpi-saving-rate');
        savingEl.textContent = `${savingRate}% Disponible`;
        savingEl.className = `kpi-trend ${balance >= 0 ? 'positive' : 'negative'}`;
        if (balance < 0) savingEl.style.color = '#f87171';
        else savingEl.style.color = '#4ade80';
    }

    document.getElementById('kpi-count').textContent = count;
    document.getElementById('kpi-avg').textContent = formatMoney(avg);
}

function renderCharts(expenses) {
    // 1. Daily Trend
    const dailyMap = {};
    expenses.forEach(e => {
        // e.date comes as 'YYYY-MM-DD'
        if (!dailyMap[e.date]) dailyMap[e.date] = 0;
        dailyMap[e.date] += e.amount;
    });

    // Sort dates
    const labels = Object.keys(dailyMap).sort();
    const dataDaily = labels.map(d => dailyMap[d]);

    const ctxDaily = document.getElementById('chart-daily').getContext('2d');
    if (chartDaily) chartDaily.destroy();

    chartDaily = new Chart(ctxDaily, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Gasto Diario',
                data: dataDaily,
                borderColor: '#38bdf8',
                backgroundColor: 'rgba(56, 189, 248, 0.1)',
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    enabled: true,
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    titleColor: '#f8fafc',
                    bodyColor: '#94a3b8',
                    borderColor: '#38bdf8',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        label: function (context) {
                            return 'Gasto: ' + formatMoney(context.parsed.y);
                        }
                    }
                }
            },
            scales: {
                y: {
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: {
                        color: '#94a3b8',
                        callback: function (value) {
                            return '$' + (value / 1000).toFixed(0) + 'k';
                        }
                    }
                },
                x: { grid: { display: false }, ticks: { color: '#94a3b8' } }
            }
        }
    });

    // 2. Sections Doughnut
    const secMap = {};
    expenses.forEach(e => {
        const sec = e.section || 'OTROS';
        if (!secMap[sec]) secMap[sec] = 0;
        secMap[sec] += e.amount;
    });

    const secLabels = Object.keys(secMap);
    const secData = secLabels.map(k => secMap[k]);
    const bgColors = [
        '#38bdf8', '#818cf8', '#34d399', '#f472b6', '#fbbf24', '#a78bfa', '#f87171'
    ];

    const ctxSec = document.getElementById('chart-sections').getContext('2d');
    if (chartSections) chartSections.destroy();

    chartSections = new Chart(ctxSec, {
        type: 'doughnut',
        data: {
            labels: secLabels,
            datasets: [{
                data: secData,
                backgroundColor: bgColors,
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '70%',
            plugins: {
                legend: { position: 'right', labels: { color: '#94a3b8', boxWidth: 12 } },
                tooltip: {
                    enabled: true,
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    titleColor: '#f8fafc',
                    bodyColor: '#94a3b8',
                    borderColor: '#38bdf8',
                    borderWidth: 1,
                    padding: 12,
                    callbacks: {
                        label: function (context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((value / total) * 100).toFixed(1);
                            return label + ': ' + formatMoney(value) + ' (' + percentage + '%)';
                        }
                    }
                }
            }
        }
    });
}

function renderTable(expenses) {
    const tbody = document.querySelector('#tx-table tbody');
    tbody.innerHTML = '';

    // Sort descending
    const sorted = [...expenses].sort((a, b) => new Date(b.date) - new Date(a.date));
    const recent = sorted.slice(0, 50); // Show last 50

    recent.forEach(e => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>${formatDate(e.date)}</td>
            <td style="font-weight:500;">${e.concept}</td>
            <td><span class="badge badge-cat">${e.category}</span></td>
            <td>${e.payment_method || '-'}</td>
            <td style="text-align:right; font-weight:600;">${formatMoney(e.amount)}</td>
        `;
        tbody.appendChild(tr);
    });
}

// Utils
function formatMoney(amount) {
    return new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP' }).format(amount);
}

function formatDate(dateStr) {
    const d = new Date(dateStr);
    return d.toLocaleDateString('es-CL', { day: '2-digit', month: 'short' });
}

function logout() {
    window.location.href = '/';
}

function switchView(viewName) {
    document.querySelectorAll('.nav-link').forEach(el => el.classList.remove('active'));
    // Ideally we would swap content divs, but for MVP this is static dashboard
    // If user wants trends page separate, we can implement logic.
    // For now, it's single page dashboard.
}
