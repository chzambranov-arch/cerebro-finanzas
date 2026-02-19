const CONFIG = {
    // Force absolute path if running from file system (double click index.html)
    API_BASE: window.location.protocol === 'file:'
        ? 'http://localhost:8005/api/v1'
        : '/api/v1',
    POLL_INTERVAL: 30000,
    VAPID_PUBLIC_KEY: 'BO8yC-brgiP_8TYicNkmpYlQ9a8qGtDLFAtZlA8_DH17MxyXCVFFdu2qQhjvHHQvmesm-DDXY49DcUOh5ekIa6c'
};

if (window.location.protocol === 'file:') {
    document.body.innerHTML = `
        <div style="padding: 20px; font-family: sans-serif; text-align: center; margin-top: 50px;">
            <h1 style="color: #ef4444; font-size: 2rem;">⚠️ MODO DE ACCESO INCORRECTO</h1>
            <p style="font-size: 1.2rem; margin-bottom: 20px;">Estás abriendo el archivo localmente. Esto bloquea la conexión por seguridad.</p>
            <p>Por favor, haz clic aquí para entrar correctamente:</p>
            <a href="http://localhost:8005" style="font-size: 2.5rem; color: #3b82f6; font-weight: bold; text-decoration: underline;">ENTRAR AL SISTEMA</a>
        </div>
    `;
    // Stop execution
    throw new Error("Local file access constrained");
}
console.log('🚀 Finanzas Core v3.0.46 Loading...');
const CURRENT_VERSION = 'v3.0.46-debug';
console.log('App Config:', CONFIG);

class FinanceApp {
    constructor() {
        this.currentView = 'inicio';
        this.token = localStorage.getItem('auth_token');
        this.sectionsData = {};
        this.dashboardData = null;
        this.commitments = [];
        this.allExpenses = []; // Store all expenses for pagination
        this.expensePage = 1;
        this.commitmentPage = 1;
        this.init();
    }

    /* REMOVED MUTATION OBSERVER TO PPREVENT FREEZE */

    toggleBodyModal(isOpen) {
        if (isOpen) {
            document.body.classList.add('body-modal-open');
            const fab = document.querySelector('.fab');
            if (fab) fab.style.display = 'none';
        } else {
            document.body.classList.remove('body-modal-open');
            const fab = document.querySelector('.fab');
            if (fab) fab.style.display = 'flex';
        }
    }

    getHeaders() {
        const headers = {};
        // Try this.token first, fallback to localStorage
        const token = this.token || localStorage.getItem('auth_token');
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        return headers;
    }

    init() {
        this.setupNavigation();
        this.setupModal();
        this.setupCamera();
        this.setupEventListeners();

        // Setup Event Delegation for Expense List
        const list = document.getElementById('expense-list');
        if (list) {
            list.addEventListener('click', (e) => {
                const btn = e.target.closest('.btn-delete-expense');
                if (btn) {
                    e.stopPropagation();
                    const id = btn.dataset.id;
                    if (id) {
                        this.deleteExpense(id);
                    }
                }
            });
        }

        this.setupSettings();
        this.setupAuth();

        // FIX: Always activate the default view, otherwise screen is white if logged in
        this.switchView('inicio');

        if (this.token) {
            this.hideLogin();
            this.refreshData().catch(() => {
                console.log("Token invalid or server down, forcing login");
                this.showLogin();
            });
            this.initPushNotifications();
            this.updatePushButton();
        } else {
            this.showLogin();
        }
    }


    async refreshData() {
        console.log('[DEBUG] Refreshing all data...');
        try {
            await this.loadDashboard();
            // Small delay to ensure DB sync is settled and UI can breathe
            setTimeout(async () => {
                await this.loadExpenses();
                if (this.currentView === 'compromisos') {
                    await this.loadCompromisos();
                }
                // Proactive check from Lúcio
                if (this.checkPendingGasto) {
                    setTimeout(() => this.checkPendingGasto(), 1000);
                }
            }, 300);
        } catch (e) {
            console.error('[CRITICAL] Failed to refresh data:', e);

            // Show visible error
            const syncEl = document.getElementById('sync-time');
            if (syncEl) {
                syncEl.textContent = "Error";
                syncEl.style.color = "red";
            }

            // Create or update debugging banner
            let banner = document.getElementById('debug-banner');
            if (!banner) {
                banner = document.createElement('div');
                banner.id = 'debug-banner';
                banner.style.cssText = "position:fixed; bottom:0; left:0; width:100%; background:rgba(255,0,0,0.9); color:white; font-size:12px; padding:10px; z-index:99999; text-align:center;";
                document.body.appendChild(banner);
            }
            banner.innerHTML = `CONN ERROR: ${e.message} <br> API: ${CONFIG.API_BASE} <br> <button onclick="location.reload(true)">RECARGAR</button>`;

            if (e.message && e.message.includes('401')) {
                this.showLogin();
            }
        }
    }


    setupNavigation() {
        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            item.addEventListener('click', () => {
                const view = item.dataset.view;
                this.switchView(view);
                navItems.forEach(ni => ni.classList.remove('active'));
                item.classList.add('active');
            });
        });
    }

    switchView(viewId) {
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        const target = document.getElementById(`view-${viewId}`);
        if (target) {
            target.classList.add('active');
            this.currentView = viewId;

            // FAB Context Logic
            const fab = document.getElementById('fab-add');
            if (fab) {
                if (viewId === 'compromisos') {
                    fab.querySelector('.label').textContent = 'Nuevo Compromiso';
                    fab.querySelector('.icon').textContent = '🤝';
                } else {
                    fab.querySelector('.label').textContent = 'Agregar Gasto';
                    fab.querySelector('.icon').textContent = '+';
                }
            }

            if (viewId === 'compromisos') {
                this.loadCompromisos();
            }

            if (viewId === 'stats') {
                this.loadStatistics();
            }
            if (viewId === 'mas') {
                this.loadSettings();
            }
        }
    }

    loadSettings() {
        if (this.dashboardData) {
            const input = document.getElementById('global-budget-input');
            if (input) input.value = this.dashboardData.monthly_budget;
        }
        const versionEl = document.getElementById('app-version-display');
        if (versionEl) versionEl.textContent = `Cerebro App ${CURRENT_VERSION} (Lúcio AI)`;

        // Restore toggle states
        const themeToggle = document.getElementById('toggle-dark-mode');
        if (themeToggle) themeToggle.checked = localStorage.getItem('theme') === 'dark';

        const alertToggle = document.getElementById('toggle-smart-alerts');
        if (alertToggle) alertToggle.checked = localStorage.getItem('smart_alerts') !== 'false';

        // Update push button status
        this.updatePushButton();
    }

    async updatePushButton() {
        const btnPush = document.getElementById('btn-enable-push');
        if (!btnPush) return;

        if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
            btnPush.textContent = 'No soportado';
            btnPush.disabled = true;
            return;
        }

        try {
            const registration = await navigator.serviceWorker.ready;
            const subscription = await registration.pushManager.getSubscription();

            if (subscription) {
                btnPush.textContent = '✓ Activo';
                btnPush.disabled = true;
                btnPush.classList.add('active-push'); // Optional: for styling
                btnPush.style.backgroundColor = '#d1fae5';
                btnPush.style.color = '#059669';
                btnPush.style.borderColor = '#10b981';
            } else {
                btnPush.textContent = 'Activar';
                btnPush.disabled = false;
                btnPush.style = ''; // Reset inline styles
            }
        } catch (e) {
            console.error('Error checking push status:', e);
        }
    }

    setupSettings() {
        // Dark Mode
        const themeToggle = document.getElementById('toggle-dark-mode');
        if (themeToggle) {
            // Check saved theme on load
            if (localStorage.getItem('theme') === 'dark') {
                document.body.classList.add('dark-mode');
                themeToggle.checked = true;
            }

            themeToggle.addEventListener('change', (e) => {
                if (e.target.checked) {
                    document.body.classList.add('dark-mode');
                    localStorage.setItem('theme', 'dark');
                } else {
                    document.body.classList.remove('dark-mode');
                    localStorage.setItem('theme', 'light');
                }
            });
        }

        // Other Toggles (Mock persistence)
        const alertToggle = document.getElementById('toggle-smart-alerts');
        if (alertToggle) {
            alertToggle.addEventListener('change', (e) => {
                localStorage.setItem('smart_alerts', e.target.checked);
            });
        }

        const btnGmail = document.getElementById('btn-sync-gmail');
        if (btnGmail) {
            btnGmail.addEventListener('click', () => this.handleGmailSync());
        }

        const autoCatToggle = document.getElementById('toggle-auto-cat');
        if (autoCatToggle) {
            autoCatToggle.addEventListener('change', (e) => {
                localStorage.setItem('auto_cat', e.target.checked);
            });
        }

        // Hard Reset Button
        const btnReset = document.getElementById('btn-hard-reset');
        if (btnReset) {
            btnReset.addEventListener('click', async () => {
                if (confirm('¿Seguro que quieres borrar todos los datos locales y reiniciar la app? Esto solucionará problemas de actualización.')) {
                    // 1. Unregister SW
                    if ('serviceWorker' in navigator) {
                        const registrations = await navigator.serviceWorker.getRegistrations();
                        for (let registration of registrations) {
                            await registration.unregister();
                        }
                    }
                    // 2. Clear Storage
                    localStorage.clear();
                    sessionStorage.clear();

                    // 3. Reload from server
                    window.location.reload(true);
                }
            });
        }

        const btnPush = document.getElementById('btn-enable-push');
        if (btnPush) {
            btnPush.addEventListener('click', async () => {
                btnPush.textContent = 'Tratando...';
                btnPush.disabled = true;
                try {
                    await this.initPushNotifications();
                    this.updatePushButton();
                } catch (e) {
                    console.error('Push error:', e);
                    if (e.message.includes('denegado') || e.message.includes('denied') || e.message.includes('permission')) {
                        alert('⚠️ Permiso bloqueado por el navegador.\n\nPara arreglarlo:\n1. Haz clic en el ícono de "candado" o "ajustes" 🔒 a la izquierda de la URL (localhost).\n2. Busca "Notificaciones" o "Permisos".\n3. Cambia a "Permitir" o haz clic en "Restablecer permisos".\n4. Recarga la página.');
                    } else {
                        alert(`Error al activar notificaciones: ${e.message}`);
                    }
                    btnPush.textContent = '🔒 Bloqueado';
                    // Reset button after 3 seconds so user can try again
                    setTimeout(() => this.updatePushButton(), 3000);
                }
            });
        }
    }

    async handleUpdateBudget() {
        const input = document.getElementById('global-budget-input');
        const val = parseInt(input.value);
        if (!val || val <= 0) return alert('⚠️ Ingresa un monto válido');

        const btn = document.getElementById('btn-save-budget');
        btn.textContent = 'Guardando...';
        btn.disabled = true;

        try {
            const response = await fetch(`${CONFIG.API_BASE}/expenses/budget`, {
                method: 'POST',
                headers: { ...this.getHeaders(), 'Content-Type': 'application/json' },
                body: JSON.stringify({ new_budget: val })
            });

            if (response.ok) {
                alert('✅ ¡Presupuesto actualizado!');
                await this.refreshData();
            } else {
                const err = await response.json();
                alert(`❌ Error: ${err.detail || 'No se pudo actualizar'}`);
            }
        } catch (e) {
            console.error(e);
            alert(`⚠️ Error de conexión: ${e.message}`);
        } finally {
            btn.textContent = 'Guardar Nuevo Presupuesto';
            btn.disabled = false;
        }
    }

    loadStatistics() {
        console.log('Loading statistics dashboard...');
        const container = document.getElementById('stats-main-chart-container');
        if (!container || !this.dashboardData) return;

        container.innerHTML = '<canvas id="mainDashboardChart"></canvas>';

        const totalBudget = this.dashboardData.monthly_budget;
        const available = this.dashboardData.available_balance;
        const totalSpent = totalBudget - available;

        setTimeout(() => {
            const ctx = document.getElementById('mainDashboardChart').getContext('2d');
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: ['Gastado', 'Disponible'],
                    datasets: [{
                        data: [totalSpent, available],
                        backgroundColor: ['#ef4444', '#10b981'],
                        borderWidth: 0,
                        hoverOffset: 4
                    }]
                },
                options: {
                    cutout: '70%',
                    responsive: true,
                    maintainAspectRatio: false,
                    layout: {
                        padding: { top: 10, bottom: 10 }
                    },
                    plugins: {
                        legend: { position: 'bottom', labels: { font: { family: 'Outfit', size: 11, weight: 'bold' }, padding: 15 } }
                    }
                }
            });
        }, 100);
    }

    setupModal() {
        const fab = document.getElementById('fab-add');
        const modal = document.getElementById('modal-add');
        const detailModal = document.getElementById('modal-detail');
        const statsModal = document.getElementById('modal-stats-detail');
        const commModal = document.getElementById('modal-add-commitment');

        if (fab) {
            fab.addEventListener('click', () => {
                if (this.currentView === 'compromisos') {
                    commModal.classList.add('active');
                } else {
                    modal.classList.add('active');
                }
                this.toggleBodyModal(true);
            });
        }

        const closeBtns = document.querySelectorAll('.btn-close');
        closeBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                btn.closest('.modal').classList.remove('active');
                this.toggleBodyModal(false);
            });
        });

        // Close when clicking outside content
        document.querySelectorAll('.modal').forEach(m => {
            m.addEventListener('click', (e) => {
                if (e.target === m) {
                    m.classList.remove('active');
                    this.toggleBodyModal(false);
                }
            });
        });
    }

    setupCamera() {
        const btnCamera = document.getElementById('btn-camera');
        const inputUpload = document.getElementById('image-upload');
        if (btnCamera && inputUpload) {
            btnCamera.addEventListener('click', () => inputUpload.click());
            inputUpload.addEventListener('change', (e) => {
                if (e.target.files.length > 0) btnCamera.textContent = '✅ Boleta Adjunta';
            });
        }
    }

    setupEventListeners() {
        const expenseForm = document.getElementById('expense-form');
        const loginForm = document.getElementById('login-form');
        const sectionSelect = document.getElementById('section-select');
        const commForm = document.getElementById('commitment-form');
        const budgetBtn = document.getElementById('btn-save-budget');

        if (sectionSelect) {
            sectionSelect.addEventListener('change', () => this.updateSubcategories());
        }

        if (expenseForm) {
            expenseForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                await this.handleExpenseSubmit();
            });
        }

        if (loginForm) {
            loginForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                await this.handleLogin();
            });
        }

        if (commForm) {
            commForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                await this.handleCommitmentSubmit();
            });
        }

        if (budgetBtn) {
            budgetBtn.addEventListener('click', async () => await this.handleUpdateBudget());
        }

        const btnSaveEdit = document.getElementById('btn-save-edit-cat');
        if (btnSaveEdit) {
            btnSaveEdit.addEventListener('click', async () => await this.submitEditCategory());
        }
    }

    setupAuth() {
        // Handled in setupEventListeners for reliability
        console.log('[AUTH] System ready');
    }

    showLogin() {
        const overlay = document.getElementById('login-overlay');
        if (overlay) {
            overlay.classList.add('active');
            overlay.style.pointerEvents = 'auto';
            overlay.style.display = 'flex';
            this.toggleBodyModal(true);
        }
    }

    hideLogin() {
        const overlay = document.getElementById('login-overlay');
        if (overlay) {
            overlay.classList.remove('active');
            this.toggleBodyModal(false);
        }
    }

    async handleLogin() {
        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;
        const remember = document.getElementById('login-remember').checked;
        const errorDiv = document.getElementById('login-error');
        const btn = document.getElementById('btn-login');

        btn.disabled = true;
        btn.textContent = 'Cargando...';
        errorDiv.textContent = '';

        try {
            const formData = new FormData();
            formData.append('username', email);
            formData.append('password', password);

            const response = await fetch(`${CONFIG.API_BASE}/auth/login`, {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                const data = await response.json();
                this.token = data.access_token;
                // Always save token (Analytics needs it)
                localStorage.setItem('auth_token', this.token);
                this.hideLogin();
                await this.refreshData();
                this.initPushNotifications();
            } else {
                errorDiv.textContent = 'Credenciales inválidas';
            }
        } catch (error) {
            console.error('Login error:', error);
            errorDiv.textContent = 'Error de conexión';
        } finally {
            btn.disabled = false;
            btn.textContent = 'Entrar';
        }
    }

    async loadDashboard() {
        try {
            const response = await fetch(`${CONFIG.API_BASE}/expenses/dashboard?_t=${Date.now()}`, {
                headers: this.getHeaders()
            });
            if (response.ok) {
                const data = await response.json();
                console.log('[DEBUG] Dashboard Data:', data);
                this.dashboardData = data;
                try {
                    this.renderDashboard(data);
                } catch (renderError) {
                    console.error('Render Error:', renderError);
                    document.getElementById('sync-time').textContent = `Err: ${renderError.message}`;
                }
            } else if (response.status === 401) {
                this.showLogin();
            } else {
                document.getElementById('sync-time').textContent = `Err ${response.status}`;
            }
        } catch (error) {
            console.error('Network Error loading dashboard:', error);
            document.getElementById('sync-time').textContent = "Err Conexión";
        }
    }

    renderDashboard(data) {
        console.log('[DEBUG] Rendering Dashboard');
        const user = data.user_name || "Christian ZV";
        const greeting = document.getElementById('greeting-text');
        if (greeting) greeting.textContent = `Hola, ${user} 👋`;

        const balance = document.getElementById('available-balance');
        // Map backend 'total_remaining' to 'available_balance'
        const availableBal = data.total_remaining ?? 0;
        const monthlyBud = data.total_budget ?? 0;

        if (balance) balance.textContent = `$${availableBal.toLocaleString()}`;

        const budget = document.getElementById('total-budget');
        if (budget) budget.textContent = `$${monthlyBud.toLocaleString()}`;

        const syncTime = document.getElementById('sync-time');
        if (syncTime) syncTime.textContent = new Date().toLocaleTimeString();

        const container = document.getElementById('categories-container');
        if (!container) return;
        container.innerHTML = '';

        // Store folders in sectionsData for detail view
        this.sectionsData = {};
        (data.folders || []).forEach(f => {
            this.sectionsData[f.name] = {
                id: f.id,
                budget: f.initial_balance,
                spent: f.spent,
                remaining: f.remaining,
                name: f.name
            };
        });

        Object.entries(this.sectionsData).forEach(([name, sec]) => {
            const budgetVal = sec.budget ?? 0;
            const spentVal = sec.spent ?? 0;
            const percent = budgetVal > 0 ? (spentVal / budgetVal) * 100 : 0;
            const remaining = sec.remaining;
            const isOver = remaining < 0;
            const barColor = percent >= 90 ? 'red' : (percent >= 70 ? 'orange' : 'green');
            const icon = this.getIconForSection(name);

            const card = document.createElement('div');
            card.className = 'category-card';
            card.innerHTML = `
                <div class="cat-header">
                    <span class="cat-icon">${icon}</span>
                    <span class="cat-title">${name}</span>
                </div>
                <div class="cat-values">
                    $${spentVal.toLocaleString()} / $${budgetVal.toLocaleString()} ${!isOver ? `(${percent.toFixed(1)}%)` : ''}
                    ${isOver ? '<span class="over-alert">⚠️ Te pasaste!</span>' : ''}
                </div>
                <div class="progress-container">
                    <div class="progress-bar ${barColor}" style="width: ${Math.min(percent, 100)}%"></div>
                </div>
                <div class="cat-remaining" style="color: ${isOver ? 'var(--danger)' : 'var(--text-muted)'}">
                    ${isOver ? `Excedido por $${Math.abs(remaining).toLocaleString()}` : `Queda $${remaining.toLocaleString()}`}
                </div>
            `;
            card.addEventListener('click', () => this.showCategoryDetail(name));
            container.appendChild(card);
        });

        const addCard = document.createElement('div');
        addCard.className = 'category-card';
        addCard.style.cssText = 'border: 2px dashed #cbd5e1; justify-content: center; align-items: center; cursor: pointer; background: rgba(255,255,255,0.5);';
        addCard.innerHTML = `
            <div style="font-size: 2rem; color: #94a3b8;">+</div>
            <div style="font-size: 0.9rem; color: #94a3b8; font-weight: 500;">Nueva Carpeta</div>
        `;
        addCard.addEventListener('click', () => this.handleAddSection());
        container.appendChild(addCard);
    }

    async updateModalCategories() {
        const sectionSelect = document.getElementById('section-select');
        if (!sectionSelect) return;
        const currentSecId = sectionSelect.value;

        try {
            const response = await fetch(`${CONFIG.API_BASE}/expenses/folders`, { headers: this.getHeaders() });
            if (response.ok) {
                const folders = await response.json();
                this.foldersList = folders; // Cache list of folders with items

                sectionSelect.innerHTML = '<option value="">Selecciona Carpeta...</option>';
                folders.forEach(f => {
                    const opt = document.createElement('option');
                    opt.value = f.id;
                    opt.textContent = f.name;
                    sectionSelect.appendChild(opt);
                });
                if (currentSecId) sectionSelect.value = currentSecId;
            }
        } catch (e) {
            console.error(e);
        }
    }

    updateSubcategories() {
        const sectionSelect = document.getElementById('section-select');
        const categorySelect = document.getElementById('category');
        const selectedFolderId = parseInt(sectionSelect.value);

        categorySelect.innerHTML = '<option value="">Esporádico / Libre...</option>';
        if (selectedFolderId && this.foldersList) {
            const folder = this.foldersList.find(f => f.id === selectedFolderId);
            if (folder && folder.items) {
                folder.items.forEach(item => {
                    const opt = document.createElement('option');
                    opt.value = item.id;
                    opt.textContent = `${item.name} (${item.type})`;
                    categorySelect.appendChild(opt);
                });
            }
        }
    }

    getIconForSection(name) {
        const n = name.toUpperCase();
        if (n.includes('COMIDA') || n.includes('FOOD') || n.includes('ALMUERZO')) return '🍕';
        if (n.includes('CASA') || n.includes('HOME') || n.includes('ARRIENDO')) return '🏠';
        if (n.includes('TRANSPORTE') || n.includes('UBER') || n.includes('AUTO') || n.includes('BENCINA')) return '🚗';
        if (n.includes('VICIO') || n.includes('ALCOHOL') || n.includes('FIESTA')) return '🎉';
        if (n.includes('STREAM') || n.includes('NETFLIX') || n.includes('SPOTIFY')) return '📺';
        if (n.includes('SALUD') || n.includes('FARMACIA') || n.includes('DOCTOR')) return '💊';
        if (n.includes('MASCOTA') || n.includes('PERRO') || n.includes('GATO') || n.includes('VET')) return '🐶';
        if (n.includes('ROP') || n.includes('ZAPAT') || n.includes('VESTIMENTA')) return '👕';
        if (n.includes('DEUDA') || n.includes('CREDITO') || n.includes('PRESTAMO')) return '💸';
        if (n.includes('EDUCACION') || n.includes('CURSO')) return '🎓';
        if (n.includes('VIAJE') || n.includes('VACACION')) return '✈️';
        if (n.includes('SUPER') || n.includes('MERCADO')) return '🛒';
        if (n.includes('FIJO')) return '📅';
        if (n.includes('SEGUR') || n.includes('COMISION') || n.includes('COMISIÓN')) return '🛡️';
        return '📦';
    }

    async showCategoryDetail(sectionName) {
        const cachedSec = this.sectionsData[sectionName];
        if (!cachedSec) return;

        // Fetch fresh folder details from backend
        try {
            const response = await fetch(`${CONFIG.API_BASE}/expenses/folders/${cachedSec.id}`, {
                headers: this.getHeaders()
            });
            if (!response.ok) throw new Error("Could not fetch details");
            const sec = await response.json();

            const modal = document.getElementById('modal-detail');
            const title = document.getElementById('detail-title');
            const spentVal = document.getElementById('detail-spent');
            const budgetVal = document.getElementById('detail-budget');
            const progressBar = document.getElementById('detail-progress-bar');
            const subList = document.getElementById('detail-subcategories');
            const iconContainer = document.getElementById('detail-icon');

            // sec is now Folder schema with initial_balance, spent, items
            const totalSpent = sec.items.reduce((acc, i) => acc + i.spent, 0) + (sec.sporadic_spent || 0);
            const totalBudget = sec.initial_balance;
            const percent = totalBudget > 0 ? (totalSpent / totalBudget) * 100 : 0;

            title.textContent = sec.name;
            iconContainer.textContent = this.getIconForSection(sec.name);
            spentVal.innerHTML = `$${totalSpent.toLocaleString()} ${percent <= 100 ? `(${percent.toFixed(1)}%)` : ''} ${totalSpent > totalBudget ? '<span class="over-alert small">🚨</span>' : ''}`;
            budgetVal.textContent = `$${totalBudget.toLocaleString()}`;

            if (progressBar) {
                progressBar.style.width = `${Math.min(percent, 100)}%`;
                progressBar.className = `progress-bar ${percent >= 90 ? 'red' : (percent >= 70 ? 'orange' : 'green')}`;
            }

            subList.innerHTML = '';

            // Render Items (Fijos/Balance)
            sec.items.forEach(item => {
                const itemDiv = document.createElement('div');
                itemDiv.className = 'subcat-item';
                const itemPercent = item.budget > 0 ? (item.spent / item.budget) * 100 : 0;
                const remaining = item.budget - item.spent;
                const isOver = remaining < 0;
                const barColor = itemPercent >= 90 ? 'red' : (itemPercent >= 70 ? 'orange' : 'green');

                itemDiv.innerHTML = `
                    <div class="subcat-header-row">
                        <h4 style="font-size: 1rem;">${item.name} <small style="opacity:0.6">(${item.type})</small></h4>
                        <div class="subcat-actions" style="display: flex; gap: 10px; align-items: center;">
                             <span class="btn-delete-item" style="cursor: pointer; font-size: 0.9rem;" title="Eliminar ítem">🗑️</span>
                             ${item.is_paid ? '✅ Pagado' : '⏳ Pendiente'}
                        </div>
                    </div>
                    <div class="subcat-header-row">
                        <span class="subcat-values" style="font-size: 0.9rem; color: var(--text-main); font-weight: 500;">
                            $${item.spent.toLocaleString()} / $${item.budget.toLocaleString()}
                        </span>
                    </div>
                    <div class="progress-container small">
                        <div class="progress-bar ${barColor}" style="width: ${Math.min(itemPercent, 100)}%"></div>
                    </div>
                `;

                // Bind delete action
                itemDiv.querySelector('.btn-delete-item').addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.handleDeleteItem(item.id, sec.name);
                });

                // Bind toggle paid action (existing logic placeholder)
                /* itemDiv.querySelector('.subcat-actions').addEventListener('click', (e) => {
                    if (e.target.classList.contains('btn-delete-item')) return;
                    e.stopPropagation(); 
                    // toggle logic...
                }); */

                subList.appendChild(itemDiv);
            });

            // Render Sporadic Items if any
            if (sec.sporadic_items && sec.sporadic_items.length > 0) {
                sec.sporadic_items.forEach(exp => {
                    const row = document.createElement('div');
                    row.className = 'subcat-item';
                    row.style.cssText = 'padding: 12px; margin-bottom: 8px; border: 1px solid #f1f5f9; background: #fff; display: flex; justify-content: space-between; align-items: center;';

                    row.innerHTML = `
                        <div style="display: flex; flex-direction: column;">
                            <h4 style="font-size: 1rem; margin: 0;">${exp.description} <small style="opacity:0.6; font-weight:400;">(Esporádico)</small></h4>
                            <span style="font-size: 0.75rem; color: #64748b; margin-top: 4px;">${new Date(exp.date).toLocaleDateString()}</span>
                        </div>
                        <div style="display: flex; gap: 10px; align-items: center;">
                            <span style="font-weight: 600; color: var(--text-main);">$${exp.amount.toLocaleString()}</span>
                            <span class="btn-del-exp" style="cursor: pointer; opacity: 0.7;" title="Borrar">🗑️</span>
                        </div>
                    `;

                    row.querySelector('.btn-del-exp').addEventListener('click', async (e) => {
                        e.stopPropagation();
                        if (!confirm(`¿Borrar "${exp.description}" de $${exp.amount.toLocaleString()}?`)) return;
                        try {
                            const r = await fetch(`${CONFIG.API_BASE}/expenses/expenses/${exp.id}`, {
                                method: 'DELETE',
                                headers: this.getHeaders()
                            });
                            if (!r.ok) {
                                const err = await r.json();
                                alert(`Error: ${err.detail || 'No se pudo borrar'}`);
                                return;
                            }
                            await this.loadDashboard();
                            this.showCategoryDetail(sec.name);
                        } catch (err) {
                            console.error(err);
                            alert('Error de conexión al borrar gasto');
                        }
                    });

                    subList.appendChild(row);
                });
            }

            const addBtn = document.createElement('button');
            addBtn.className = 'btn-add-cat';
            addBtn.textContent = '+ Agregar Ítem (Fijo/Saldo)';
            addBtn.style.cssText = 'width: 100%; padding: 12px; margin-top: 15px; background: #f1f5f9; border: 1px dashed #cbd5e1; border-radius: 8px; color: var(--text-main); font-weight: 500; cursor: pointer;';
            addBtn.addEventListener('click', () => this.handleAddCategory(sec.id));
            subList.appendChild(addBtn);

            const delSecBtn = document.createElement('button');
            delSecBtn.textContent = '⚠️ Eliminar Carpeta Completa';
            delSecBtn.style.cssText = 'width: 100%; padding: 10px; margin-top: 20px; background: none; border: 1px solid #fee2e2; border-radius: 8px; color: #ef4444; font-size: 0.8rem; cursor: pointer;';
            delSecBtn.addEventListener('click', () => this.handleDeleteSection(sec.id));
            subList.appendChild(delSecBtn);

            modal.classList.add('active');
            this.toggleBodyModal(true);

        } catch (e) {
            console.error(e);
            alert("Error al cargar detalles");
        }
    }

    showStatDetail(type) {
        const modal = document.getElementById('modal-stats-detail');
        const title = document.getElementById('stats-detail-title');
        const icon = document.getElementById('stats-detail-icon');
        const content = document.getElementById('stats-detail-content');

        const configs = {
            'general': { title: 'Indicadores Generales', icon: '⚡' },
            'prediction': { title: 'Predicción de Gastos', icon: '🔮' },
            'comparison': { title: 'Comparación Mensual', icon: '⚖️' },
            'savings': { title: 'Proyección Ahorro', icon: '🐖' }
        };

        const config = configs[type];
        if (!config) return;

        title.textContent = config.title;
        icon.textContent = config.icon;
        content.innerHTML = '';

        if (type === 'general') {
            if (!this.dashboardData) {
                content.innerHTML = '<p class="placeholder-text">Sin datos disponibles.</p>';
                modal.classList.add('active');
                this.toggleBodyModal(true);
                return;
            }

            const totalBudget = this.dashboardData.monthly_budget;
            const totalSpent = totalBudget - this.dashboardData.available_balance;
            const available = this.dashboardData.available_balance;

            const barContainer = document.createElement('div');
            barContainer.style.height = '120px';
            barContainer.style.width = '100%';
            barContainer.style.marginBottom = '20px';
            barContainer.innerHTML = '<canvas id="statsChartBar"></canvas>';
            content.appendChild(barContainer);

            const pieContainer = document.createElement('div');
            pieContainer.style.height = '180px';
            pieContainer.style.width = '100%';
            pieContainer.style.marginTop = '10px';
            pieContainer.innerHTML = '<canvas id="statsChartPie"></canvas>';
            pieContainer.style.borderTop = '1px solid #f1f5f9';
            pieContainer.style.paddingTop = '15px';
            content.appendChild(pieContainer);

            modal.classList.add('active');
            this.toggleBodyModal(true);

            setTimeout(() => {
                // 1. Bar Chart (Spent vs Available)
                const ctxBar = document.getElementById('statsChartBar').getContext('2d');
                new Chart(ctxBar, {
                    type: 'bar',
                    data: {
                        labels: ['Gastado', 'Disponible'],
                        datasets: [{
                            data: [totalSpent, available],
                            backgroundColor: ['#ef4444', '#10b981'],
                            borderRadius: 6
                        }]
                    },
                    options: {
                        indexAxis: 'y',
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: { x: { beginAtZero: true } }
                    }
                });

                // 2. Pie Chart (Spending by Section)
                const ctxPie = document.getElementById('statsChartPie').getContext('2d');
                const secLabels = Object.keys(this.sectionsData);
                const secSpent = Object.values(this.sectionsData).map(s => s.spent);

                new Chart(ctxPie, {
                    type: 'pie',
                    data: {
                        labels: secLabels,
                        datasets: [{
                            data: secSpent,
                            backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4'],
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { position: 'right', labels: { font: { family: 'Outfit', size: 9 } } }
                        }
                    }
                });
            }, 100);
            return;
        } else if (type === 'prediction') {
            if (!this.dashboardData) {
                content.innerHTML = '<p class="placeholder-text">Sin datos disponibles.</p>';
            } else {
                const totalBudget = this.dashboardData.monthly_budget;
                const available = this.dashboardData.available_balance;
                const totalSpent = totalBudget - available;

                const now = new Date();
                const currentDay = now.getDate();
                const totalDays = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate();
                const daysRemaining = totalDays - currentDay;

                // 1. Daily Average so far
                const dailyAvg = currentDay > 0 ? totalSpent / currentDay : 0;

                // 2. Projected Finish
                const projectedSpent = (dailyAvg * totalDays);
                const projectedBalance = totalBudget - projectedSpent;
                const isProjectedOver = projectedBalance < 0;

                // 3. Recommended Daily (to match budget)
                const recommendedDaily = daysRemaining > 0 && available > 0 ? available / daysRemaining : 0;

                content.innerHTML = `
                    <div class="stat-detail-card">
                        <div class="projection-header" style="text-align: center; margin-bottom: 25px;">
                            <p style="color: var(--text-muted); font-size: 0.9rem; margin-bottom: 5px;">Proyección Cierre de Mes</p>
                            <h2 style="font-size: 2.2rem; color: ${isProjectedOver ? '#ef4444' : '#10b981'}; font-weight: 700;">
                                $${projectedSpent.toLocaleString()}
                            </h2>
                            <p style="font-size: 0.85rem; color: ${isProjectedOver ? '#ef4444' : '#10b981'}; background: ${isProjectedOver ? '#fee2e2' : '#d1fae5'}; display: inline-block; padding: 4px 12px; border-radius: 20px; margin-top: 5px;">
                                ${isProjectedOver ? `Excedido por $${Math.abs(projectedBalance).toLocaleString()}` : `Ahorro posible: $${projectedBalance.toLocaleString()}`}
                            </p>
                        </div>

                        <div class="projection-stats" style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                            <div class="p-stat-box" style="background: #f8fafc; padding: 15px; border-radius: 12px; text-align: center;">
                                <div style="font-size: 1.5rem; margin-bottom: 5px;">📅</div>
                                <div style="font-size: 0.8rem; color: var(--text-muted);">Gasto Diario Actual</div>
                                <div style="font-weight: 600; font-size: 1.1rem; color: var(--text-main);">$${Math.round(dailyAvg).toLocaleString()}</div>
                            </div>
                            <div class="p-stat-box" style="background: #f0fdf4; padding: 15px; border-radius: 12px; text-align: center; border: 1px solid #bbf7d0;">
                                <div style="font-size: 1.5rem; margin-bottom: 5px;">🎯</div>
                                <div style="font-size: 0.8rem; color: #15803d;">Meta Diaria Restante</div>
                                <div style="font-weight: 600; font-size: 1.1rem; color: #15803d;">$${Math.round(recommendedDaily).toLocaleString()}</div>
                            </div>
                        </div>

                        <div class="projection-note" style="margin-top: 25px; font-size: 0.85rem; color: var(--text-muted); text-align: center; line-height: 1.5;">
                            ${daysRemaining} días restantes. <br>
                            ${dailyAvg > recommendedDaily ? '⚠️ Estás gastando más de lo recomendado.' : '✅ Estás bajo la meta diaria. ¡Bien hecho!'}
                        </div>
                    </div>
                `;
            }
        }
        modal.classList.add('active');
        this.toggleBodyModal(true);
    }



    async loadExpenses() {
        console.log('[DEBUG] Loading expenses...');
        try {
            const response = await fetch(`${CONFIG.API_BASE}/expenses/?_t=${Date.now()}`, {
                headers: this.getHeaders()
            });
            if (response.ok) {
                const expenses = await response.json();
                console.log(`[DEBUG] Received ${expenses.length} expenses`);
                this.allExpenses = expenses;
                this.renderExpenses(expenses, this.expensePage);
            }
        } catch (error) {
            console.error('Error loading expenses:', error);
        }
    }

    renderExpenses(expenses, page = 1) {
        const list = document.getElementById('expense-list');
        if (!list) {
            console.error('[DEBUG] #expense-list not found in DOM');
            return;
        }

        this.expensePage = page;
        const itemsPerPage = 10;
        const start = (page - 1) * itemsPerPage;
        const end = start + itemsPerPage;
        const pageItems = expenses.slice(start, end);

        console.log(`[DEBUG] Rendering expenses page ${page}...`);
        list.innerHTML = '';

        const icons = {
            'COMIDAS': '🍕', 'TRANSPORTE': '🚗', 'VICIOS': '🎉', 'OTROS': '📦',
            'CASA': '🏠', 'GASTOS FIJOS': '🏠', 'SALUD': '💊', 'EDUCACION': '📚',
            'PERSONALES': '👤', 'FAMILIA': '👨‍👩‍👧‍👦',
            'Supermercado': '🛒', 'Restaurante': '🍽️', 'Bencina': '⛽', 'Uber': '🚖',
            'Cerveza': '🍺', 'Farmacia': '🩹', 'Arriendo': '🔑'
        };

        pageItems.forEach(exp => {
            try {
                const item = document.createElement('div');
                item.className = 'expense-item';

                let icon = icons[exp.category] || icons[exp.category?.toUpperCase()] || icons[exp.section] || icons[exp.section?.toUpperCase()] || '💰';
                const dateStr = exp.date ? new Date(exp.date).toLocaleDateString() : 'N/A';

                item.innerHTML = `
                    <div class="exp-icon-box">${icon}</div>
                    <div class="exp-details">
                        <h4>${exp.concept || 'Sin concepto'}</h4>
                        <p>${dateStr} • ${exp.category || 'General'}</p>
                    </div>
                    <div class="exp-amount">$${(exp.amount || 0).toLocaleString()}</div>
                    <button class="btn-delete-expense" data-id="${exp.id}" title="Eliminar gasto">🗑️</button>
                `;
                list.appendChild(item);
            } catch (err) {
                console.error('[DEBUG] Error rendering single expense:', err, exp);
            }
        });

        this.renderPagination('expense-pagination', expenses.length, itemsPerPage, page, (p) => {
            this.renderExpenses(expenses, p);
            window.scrollTo({ top: list.offsetTop - 100, behavior: 'smooth' });
        });
    }

    renderPagination(containerId, totalItems, itemsPerPage, currentPage, onPageChange) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const totalPages = Math.ceil(totalItems / itemsPerPage);
        container.innerHTML = '';

        if (totalPages <= 1) return;

        // Show a max of 5 page buttons or logic for dots if many
        for (let i = 1; i <= totalPages; i++) {
            const btn = document.createElement('button');
            btn.className = `btn-page ${i === currentPage ? 'active' : ''}`;
            btn.textContent = i;
            btn.onclick = () => onPageChange(i);
            container.appendChild(btn);
        }
    }

    async deleteExpense(id, event) {
        if (event) event.stopPropagation();

        if (!confirm('¿Estás seguro de que deseas eliminar este gasto? También se borrará de la planilla.')) {
            return;
        }

        try {
            console.log(`[DEBUG] Deleting expense ${id}...`);
            // Correct API route based on finance.py backend structure
            // Use /expenses/${id} directly if router is mounted at /expenses
            // But we created @router.delete("/expenses/{expense_id}") inside finance.py
            // So full path is /api/v1/expenses/expenses/${id}
            const response = await fetch(`${CONFIG.API_BASE}/expenses/expenses/${id}`, {
                method: 'DELETE',
                headers: this.getHeaders()
            });

            if (response.ok) {
                console.log('[DEBUG] Expense deleted successfully');
                await this.refreshData(); // Ensure we await refresh
            } else {
                const err = await response.json();
                alert(`❌ Fallo al eliminar: ${err.detail || 'Error desconocido'}`);
            }
        } catch (error) {
            console.error('Error deleting expense:', error);
            alert('Error de conexión al intentar eliminar.');
        }
    }

    async handleExpenseSubmit() {
        console.log('[DEBUG] Starting handleExpenseSubmit v4.0 (JSON mode)');
        const btn = document.getElementById('btn-submit-expense');
        btn.disabled = true;
        btn.textContent = 'Guardando...';

        try {
            const amtEl = document.getElementById('expense-amount') || document.getElementById('amount');
            const descEl = document.getElementById('expense-desc') || document.getElementById('concept');
            const folderEl = document.getElementById('section-select');
            const itemEl = document.getElementById('category');

            if (!amtEl || !folderEl) throw new Error("Faltan campos críticos");

            const folderId = parseInt(folderEl.value);
            const itemId = itemEl.value ? parseInt(itemEl.value) : null;

            // Determine type automatically based on item selected
            let type = 'ESPORADICO';
            if (itemId && this.foldersList) {
                const folder = this.foldersList.find(f => f.id === folderId);
                const item = folder?.items.find(i => i.id === itemId);
                if (item) type = item.type;
            }

            const payload = {
                description: descEl ? descEl.value : 'Sin descripción',
                amount: parseInt(amtEl.value),
                folder_id: folderId,
                item_id: itemId,
                type: type,
                date: new Date().toISOString().split('T')[0]
            };

            const response = await fetch(`${CONFIG.API_BASE}/expenses/expenses`, {
                method: 'POST',
                headers: { ...this.getHeaders(), 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                document.getElementById('modal-add').classList.remove('active');
                this.toggleBodyModal(false);
                document.getElementById('expense-form').reset();
                await this.refreshData();
                alert('✅ Gasto registrado');
            } else {
                const errJson = await response.json().catch(() => ({}));
                alert('Fallo al guardar: ' + (errJson.detail || 'Error en el servidor'));
            }
        } catch (error) {
            console.error('Submission error:', error);
            alert('Error: ' + error.message);
        } finally {
            btn.disabled = false;
            btn.textContent = 'Guardar Gasto';
        }
    }

    async loadCompromisos() {
        const list = document.getElementById('compromisos-list');
        if (!list) return;
        list.innerHTML = '<p class="placeholder-text">Cargando...</p>';
        try {
            const response = await fetch(`/api/v3/commitments/`, {
                headers: this.getHeaders()
            });
            if (response.ok) {
                const data = await response.json();
                this.commitments = data;
                this.renderCompromisos(data, this.commitmentPage);
            } else {
                console.error('[COMMITMENTS] Error response:', response.status);
                list.innerHTML = '<p class="placeholder-text">Error al cargar compromisos (' + response.status + ')</p>';
            }
        } catch (error) {
            console.error('[COMMITMENTS] Network error:', error);
            list.innerHTML = '<p class="placeholder-text">Error de conexión</p>';
        }
    }

    renderCompromisos(data, page = 1) {
        let totalDebt = 0, countDebt = 0, totalLoan = 0, countLoan = 0;
        data.forEach(c => {
            if (c.status !== 'PAID') {
                const rem = c.total_amount - c.paid_amount;
                if (c.type === 'DEBT') { totalDebt += rem; countDebt++; }
                else { totalLoan += rem; countLoan++; }
            }
        });

        this.commitmentPage = page;
        const itemsPerPage = 10;
        const start = (page - 1) * itemsPerPage;
        const end = start + itemsPerPage;
        const pageItems = data.slice(start, end);

        // Update KPIs
        const debtAmtEl = document.getElementById('kpi-debt-amount');
        const debtCntEl = document.getElementById('kpi-debt-count');
        if (debtAmtEl) {
            debtAmtEl.textContent = `$${totalDebt.toLocaleString()}`;
            debtAmtEl.style.color = totalDebt > 0 ? 'var(--danger)' : 'var(--text-muted)';
        }
        if (debtCntEl) debtCntEl.textContent = `${countDebt} items`;

        const loanAmtEl = document.getElementById('kpi-loan-amount');
        const loanCntEl = document.getElementById('kpi-loan-count');
        if (loanAmtEl) {
            loanAmtEl.textContent = `$${totalLoan.toLocaleString()}`;
            loanAmtEl.style.color = totalLoan > 0 ? 'var(--accent)' : 'var(--text-muted)';
        }
        if (loanCntEl) loanCntEl.textContent = `${countLoan} items`;

        const balanceAmtEl = document.getElementById('kpi-total-balance');
        const balanceDetEl = document.getElementById('kpi-balance-detail');
        const balance = totalLoan - totalDebt;
        if (balanceAmtEl) {
            balanceAmtEl.textContent = `$${Math.abs(balance).toLocaleString()}`;
            balanceAmtEl.style.color = balance >= 0 ? 'var(--accent)' : 'var(--danger)';
        }
        if (balanceDetEl) {
            balanceDetEl.textContent = balance > 0 ? 'A favor' : (balance < 0 ? 'En contra' : 'Equilibrado');
        }

        const list = document.getElementById('compromisos-list');
        if (!list) return;

        list.innerHTML = '';
        pageItems.forEach(c => {
            const item = document.createElement('div');
            item.className = `commitment-item ${c.status === 'PAID' ? 'paid-item' : ''}`;
            const isPaid = c.status === 'PAID';
            const dateObj = c.created_at ? new Date(c.created_at) : new Date();
            const dateStr = `${dateObj.getDate().toString().padStart(2, '0')}/${(dateObj.getMonth() + 1).toString().padStart(2, '0')}`;

            const descHtml = c.description ? `<span style="display:block; font-size: 0.75rem; color: #9ca3af; font-weight: 400; margin-top: 2px;">${c.description}</span>` : '';

            item.innerHTML = `
                <div class="commitment-icon">${c.type === 'DEBT' ? '🔴' : '🟢'}</div>
                <div class="commitment-details">
                    <div class="commitment-title" style="${isPaid ? 'text-decoration: line-through;' : ''}">
                        ${c.title} <small style="display:block; font-size: 0.75rem; color: var(--text-muted);">${dateStr}</small>
                        ${descHtml}
                    </div>
                    <div class="commitment-amount">$${c.total_amount.toLocaleString()}</div>
                </div>
                <div class="commitment-action">
                    <button class="btn-check" data-id="${c.id}">${isPaid ? '✅' : '⬜'}</button>
                </div>
            `;
            item.querySelector('.btn-check').addEventListener('click', () => this.toggleCommitmentStatus(c));
            list.appendChild(item);
        });

        this.renderPagination('compromisos-pagination', data.length, itemsPerPage, page, (p) => {
            this.renderCompromisos(data, p);
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }

    async toggleCommitmentStatus(commitment) {
        const newStatus = commitment.status === 'PENDING' ? 'PAID' : 'PENDING';
        try {
            const response = await fetch(`/api/v3/commitments/${commitment.id}`, {
                method: 'PATCH',
                headers: { ...this.getHeaders(), 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: newStatus, paid_amount: newStatus === 'PAID' ? commitment.total_amount : 0 })
            });
            if (response.ok) await this.loadCompromisos();
        } catch (e) { console.error(e); }
    }

    async handleCommitmentSubmit() {
        const titleVal = document.getElementById('comm-title').value;
        const amountVal = document.getElementById('comm-amount').value;

        if (!titleVal || !amountVal) {
            alert('⚠️ Por favor completa el título y el monto.');
            return;
        }

        const descVal = document.getElementById('comm-description') ? document.getElementById('comm-description').value : null;

        const payload = {
            title: titleVal,
            description: descVal || null,
            type: document.querySelector('input[name="comm-type"]:checked').value,
            total_amount: parseInt(amountVal),
            due_date: document.getElementById('comm-date').value || null,
            status: "PENDING"
        };

        try {
            const response = await fetch(`/api/v3/commitments/`, {
                method: 'POST',
                headers: { ...this.getHeaders(), 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (response.ok) {
                const resData = await response.json();
                // Alert with debug info
                alert(`✅ Compromiso guardado!\nID: ${resData.id}\nUserID: ${resData.user_id}`);

                document.getElementById('modal-add-commitment').classList.remove('active');
                this.toggleBodyModal(false);
                document.getElementById('commitment-form').reset(); // Clear form

                // Force reload of compromisos
                await this.loadCompromisos();
            } else {
                const err = await response.json();
                console.error("Server Error:", err); // Extra debug
                alert(`❌ Error al guardar: ${err.detail || 'Intenta de nuevo'}`);
            }
        } catch (error) {
            console.error(error);
            alert('⚠️ Error de conexión al guardar el compromiso.');
        }
    }

    async handleAddCategory(section) {
        const name = prompt(`Nueva categoría para ${section}:`);
        if (!name) return;
        const budget = parseInt(prompt(`Presupuesto:`, "0")) || 0;
        try {
            const response = await fetch(`${CONFIG.API_BASE}/expenses/categories/`, {
                method: 'POST',
                headers: { ...this.getHeaders(), 'Content-Type': 'application/json' },
                body: JSON.stringify({ section, category: name, budget })
            });
            if (response.ok) {
                document.getElementById('modal-detail').classList.remove('active');
                this.toggleBodyModal(false);
                await this.refreshData();
            }
        } catch (e) { console.error(e); }
    }

    openEditModal(section, category, currentBudget) {
        this.editTarget = { section, category };
        const modal = document.getElementById('modal-edit-budget');
        const nameEl = document.getElementById('edit-cat-name');
        const nameInput = document.getElementById('edit-cat-name-input');
        const input = document.getElementById('edit-cat-amount');

        if (nameEl) nameEl.textContent = `${category} (${section})`;
        if (nameInput) nameInput.value = category;
        input.value = currentBudget;

        modal.classList.add('active');
        this.toggleBodyModal(true);
        setTimeout(() => input.focus(), 100);
    }

    async submitEditCategory() {
        if (!this.editTarget) return;

        const nameInput = document.getElementById('edit-cat-name-input');
        const amountInput = document.getElementById('edit-cat-amount');
        const newBudget = parseInt(amountInput.value);
        const newCategoryName = nameInput ? nameInput.value.trim() : this.editTarget.category;

        if (isNaN(newBudget) || newBudget < 0 || !newCategoryName) {
            alert('⚠️ Ingresa un nombre y monto válidos');
            return;
        }

        const btn = document.getElementById('btn-save-edit-cat');
        btn.textContent = 'Guardando...';
        btn.disabled = true;

        try {
            const { section, category } = this.editTarget;
            console.log(`[DEBUG] Submitting Edit: ${category} -> ${newCategoryName} (Budget: ${newBudget})`);

            const response = await fetch(`${CONFIG.API_BASE}/expenses/categories/`, {
                method: 'PATCH',
                headers: { ...this.getHeaders(), 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    section,
                    category,
                    new_budget: newBudget,
                    new_category: newCategoryName
                })
            });

            if (response.ok) {
                const res = await response.json();
                console.log('[DEBUG] Server response:', res);
                document.getElementById('modal-edit-budget').classList.remove('active');
                this.toggleBodyModal(false);
                await this.refreshData(); // This refreshes the detail modal too if logic supports it, or we need to close detail?
                // Actually refreshData refreshes dashboardData.
                // We should also close the detail modal to force user to re-open and see new data, or re-render detail.
                // For simplicity, let's close all modals or just refresh.
                // But wait, if Detail Modal is open, we need to update it.
                // Simplest: Close Edit Modal, and call showCategoryDetail again?
                // refreshData() updates this.sectionsData.
                // Then we need to re-render the detail view if it's open.
                if (document.getElementById('modal-detail').classList.contains('active')) {
                    this.showCategoryDetail(section);
                }
            } else {
                alert('❌ Error al actualizar');
            }
        } catch (e) {
            console.error(e);
            alert('Error de conexión');
        } finally {
            btn.textContent = 'Guardar Cambios';
            btn.disabled = false;
        }
    }

    // Old handleUpdateCategory replaced by openEditModal call
    handleUpdateCategory(section, category, currentBudget) {
        this.openEditModal(section, category, currentBudget);
    }

    async handleAddCategory(folderId) {
        const name = prompt(`Nueva subcategoría/ítem:`);
        if (!name) return;
        const budget = parseInt(prompt("Monto/Presupuesto Mensual:", "0")) || 0;
        const type = prompt("Tipo (FIJO o CON_SALDO):", "FIJO").toUpperCase();

        if (type !== 'FIJO' && type !== 'CON_SALDO') {
            alert("Tipo inválido. Debe ser FIJO o CON_SALDO.");
            return;
        }

        try {
            const response = await fetch(`${CONFIG.API_BASE}/expenses/items`, {
                method: 'POST',
                headers: { ...this.getHeaders(), 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    folder_id: folderId,
                    name: name.trim(),
                    budget: budget,
                    type: type
                })
            });

            if (response.ok) {
                alert('✅ Ítem agregado');
                await this.refreshData();
                const folder = this.dashboardData.folders.find(f => f.id === folderId);
                if (folder) this.showCategoryDetail(folder.name);
            } else {
                const err = await response.json();
                alert(`❌ Error: ${err.detail || 'Fallo al agregar'}`);
            }
        } catch (e) {
            console.error(e);
            alert('⚠️ Error de conexión');
        }
    }

    async handleAddSection() {
        const name = prompt("Nombre Nueva Carpeta (ej: HOGAR):");
        if (!name) return;
        const balance = parseInt(prompt("Presupuesto/Saldo Inicial para esta carpeta:", "0")) || 0;

        try {
            const response = await fetch(`${CONFIG.API_BASE}/expenses/folders`, {
                method: 'POST',
                headers: { ...this.getHeaders(), 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, initial_balance: balance })
            });

            if (response.ok) {
                alert('✅ Carpeta creada');
                await this.refreshData();
            } else {
                const err = await response.json();
                alert(`❌ Error: ${err.detail || 'Fallo al crear'}`);
            }
        } catch (e) {
            console.error(e);
            alert('⚠️ Error de conexión');
        }
    }

    async handleDeleteSection(folderId) {
        if (!confirm('¿Estás seguro de eliminar esta carpeta completa? Se perderán todos los datos asociados.')) return;

        try {
            const response = await fetch(`${CONFIG.API_BASE}/expenses/folders/${folderId}`, {
                method: 'DELETE',
                headers: this.getHeaders()
            });

            if (!response.ok) throw new Error("Error deleting folder");

            this.toggleBodyModal(false);
            document.getElementById('modal-detail').classList.remove('active');
            await this.loadDashboard();

        } catch (e) {
            console.error(e);
            alert("No se pudo eliminar la carpeta");
        }
    }

    async handleDeleteItem(itemId, sectionName) {
        if (!confirm('¿Eliminar este ítem y todos sus gastos asociados?')) return;
        try {
            const res = await fetch(`${CONFIG.API_BASE}/expenses/items/${itemId}`, {
                method: 'DELETE',
                headers: this.getHeaders()
            });
            if (!res.ok) {
                const err = await res.json();
                alert(`Error: ${err.detail || 'No se pudo eliminar el ítem'}`);
                return;
            }
            await this.loadDashboard();
            this.showCategoryDetail(sectionName);
        } catch (e) {
            console.error(e);
            alert('Error de conexión al eliminar ítem');
        }
    }

    async handleDeleteSporadic(folderId, sectionName) {
        if (!confirm('¿Vaciar todos los gastos esporádicos de esta carpeta? Esta acción no se puede deshacer.')) return;
        try {
            const res = await fetch(`${CONFIG.API_BASE}/expenses/folders/${folderId}/sporadic`, {
                method: 'DELETE',
                headers: this.getHeaders()
            });
            if (!res.ok) throw new Error("Error deleting sporadic");
            this.showCategoryDetail(sectionName); // Refresh modal
            this.loadDashboard(); // Refresh background stats
        } catch (e) {
            console.error(e);
            alert("Error al vaciar gastos esporádicos");
        }
    }

    async handleDeleteCategory(sectionName, catName) {
        const folder = (this.dashboardData.folders || []).find(f => f.name === sectionName);
        if (!folder) return;
        try {
            const resDetails = await fetch(`${CONFIG.API_BASE}/expenses/folders/${folder.id}`, { headers: this.getHeaders() });
            const data = await resDetails.json();
            const item = (data.items || []).find(i => i.name === catName);
            if (!item) return;

            if (!confirm(`¿Estás seguro de ELIMINAR "${catName}"?`)) return;

            const response = await fetch(`${CONFIG.API_BASE}/expenses/items/${item.id}`, {
                method: 'DELETE',
                headers: this.getHeaders()
            });

            if (response.ok) {
                alert('🗑️ Ítem eliminado');
                this.showCategoryDetail(sectionName);
                await this.refreshData();
            } else {
                const err = await response.json();
                alert(`❌ Error: ${err.detail || 'No se pudo borrar'}`);
            }
        } catch (e) {
            console.error(e);
            alert('⚠️ Error de conexión');
        }
    }

    async handleGmailSync() {
        if (!confirm('Esto buscará correos recientes de bancos (Chile, Santander) y agregará los gastos automáticamente. ¿Continuar?')) return;

        const btn = document.getElementById('btn-sync-gmail');
        if (btn) {
            btn.disabled = true;
            btn.textContent = 'Sincronizando... ⏳';
        }

        try {
            const headers = this.getHeaders();
            console.log('Gmail Sync: Sending request with headers', headers);

            const response = await fetch(`${CONFIG.API_BASE}/expenses/sync-gmail`, {
                method: 'POST',
                headers: headers
            });

            console.log('Gmail Sync: Response status', response.status);
            const data = await response.json();
            console.log('Gmail Sync: Response data', data);

            if (response.ok) {
                if (data.processed > 0) {
                    alert(`✅ ¡Éxito! Se encontraron ${data.processed} gastos nuevos:\n\n` + data.details.join('\n'));
                    await this.refreshData();
                } else {
                    alert('✅ Proceso completado, pero no se encontraron nuevos correos de compra compatibles.');
                }
            } else {
                // Handle 401 specifically
                if (response.status === 401) {
                    alert('❌ Error de autenticación.\n\nPor favor:\n1. Cierra sesión\n2. Vuelve a iniciar sesión\n3. Intenta sincronizar de nuevo');
                    // Redirect to login
                    this.token = null;
                    localStorage.removeItem('auth_token');
                    this.showLogin();
                } else {
                    alert(`❌ Error: ${data.detail || 'Fallo en la sincronización'}`);
                }
            }
        } catch (error) {
            console.error('Gmail Sync Error:', error);
            alert('⚠️ Error de conexión con el servidor.');
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.textContent = '🔃 Sincronizar Ahora';
            }
        }
    }

    async initPushNotifications() {
        console.log('[PUSH] Iniciando activación...');
        if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
            console.warn('Push not supported on this browser.');
            throw new Error('Push no soportado en este navegador');
        }

        try {
            console.log('[PUSH] Solicitando permiso...');
            const permission = await Notification.requestPermission();
            console.log('[PUSH] Permiso:', permission);
            if (permission !== 'granted') {
                throw new Error('Permiso de notificaciones denegado');
            }

            console.log('[PUSH] Esperando Service Worker ready...');
            // Timeout de 5s para el ready
            const registration = await Promise.race([
                navigator.serviceWorker.ready,
                new Promise((_, reject) => setTimeout(() => reject(new Error('Timeout de Service Worker')), 5000))
            ]);

            console.log('[PUSH] Suscribiendo al servidor de push...');
            const subscribeOptions = {
                userVisibleOnly: true,
                applicationServerKey: this.urlBase64ToUint8Array(CONFIG.VAPID_PUBLIC_KEY)
            };

            const subscription = await registration.pushManager.subscribe(subscribeOptions);
            console.log('[PUSH] Suscripción obtenida:', subscription);

            const response = await fetch(`${CONFIG.API_BASE}/agent/push-subscribe`, {
                method: 'POST',
                headers: { ...this.getHeaders(), 'Content-Type': 'application/json' },
                body: JSON.stringify(subscription)
            });

            if (!response.ok) {
                throw new Error('Error al guardar suscripción en el servidor');
            }

            console.log('Push Subscription saved.');
        } catch (error) {
            console.error('Push error detailed:', error);
            throw error; // Re-throw to handle in the UI
        }
    }

    urlBase64ToUint8Array(base64String) {
        const padding = '='.repeat((4 - base64String.length % 4) % 4);
        const base64 = (base64String + padding).replace(/\-/g, '+').replace(/_/g, '/');
        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);
        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }
}

// Initialize immediately so onclick handlers work
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.financeApp = new FinanceApp();
    });
} else {
    // DOM already loaded
    window.financeApp = new FinanceApp();
}
