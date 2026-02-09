
(function () {
    console.log("Chat Module Loading...");

    let targetClass = null;
    try {
        if (typeof FinanceApp !== 'undefined') {
            targetClass = FinanceApp;
        } else if (window.FinanceApp && typeof window.FinanceApp === 'function') {
            targetClass = window.FinanceApp;
        }
    } catch (e) {
        console.error("Error finding FinanceApp", e);
    }

    if (!targetClass) {
        console.error("FinanceApp Class NOT found. Chat methods not attached.");
        return;
    }

    console.log("FinanceApp Class found. Extending prototype with Chat capabilities.");

    Object.assign(targetClass.prototype, {

        toggleChat: function () {
            console.log("toggleChat called");
            const overlay = document.getElementById('chat-overlay');
            if (overlay) {
                const isActive = overlay.classList.contains('active');
                if (isActive) {
                    overlay.classList.remove('active');
                    if (this.toggleBodyModal) this.toggleBodyModal(false);
                } else {
                    overlay.classList.add('active');
                    if (this.toggleBodyModal) this.toggleBodyModal(true);
                    setTimeout(() => {
                        const input = document.getElementById('chat-input');
                        if (input) input.focus();
                    }, 300);
                }
            }
        },

        sendChatMessage: async function () {
            console.log("[DEBUG] sendChatMessage initiation");
            const input = document.getElementById('chat-input');
            const photoInput = document.getElementById('chat-photo-input');
            const msgText = input.value.trim();
            const photoFile = photoInput?.files[0];

            if (!msgText && !photoFile) return;

            // Clear inputs and preview immediately
            input.value = '';
            this.removeChatPreview();

            // 1. Add User Message (Handle image sequentially with Promise)
            try {
                if (photoFile) {
                    console.log("[DEBUG] Image selected, reading...");
                    const imageData = await new Promise((resolve, reject) => {
                        const reader = new FileReader();
                        reader.onload = (e) => resolve(e.target.result);
                        reader.onerror = (e) => reject(e);
                        reader.readAsDataURL(photoFile);
                    });
                    this.addChatMessage(`<img src="${imageData}" style="max-width:100%; border-radius:12px; margin-bottom:8px; display:block;">${msgText}`, 'user');
                } else {
                    this.addChatMessage(msgText, 'user');
                }
            } catch (err) {
                console.error("Error loading image for preview:", err);
                this.addChatMessage(msgText || "[Imagen error]", 'user');
            }

            // 2. Add Thinking Message
            const thinkingDiv = this.addChatMessage('Lúcio está analizando...', 'bot', true);

            try {
                let apiBase = '/api/v1';
                if (typeof CONFIG !== 'undefined') apiBase = CONFIG.API_BASE;
                else if (window.CONFIG) apiBase = window.CONFIG.API_BASE;

                const formData = new FormData();
                formData.append('message', msgText);
                if (photoFile) {
                    formData.append('image', photoFile, photoFile.name);
                }

                // Clear input file after adding to FormData
                if (photoInput) photoInput.value = '';

                if (this.activePendingId) {
                    formData.append('pending_id', this.activePendingId);
                    this.activePendingId = null;
                }

                console.log("[DEBUG] Sending request to:", `${apiBase}/agent/chat`);
                const response = await fetch(`${apiBase}/agent/chat`, {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${this.token || localStorage.getItem('auth_token')}` },
                    body: formData
                });

                // Remove thinking
                if (thinkingDiv && thinkingDiv.parentNode) {
                    thinkingDiv.parentNode.removeChild(thinkingDiv);
                }

                if (response.ok) {
                    const data = await response.json();
                    console.log("[DEBUG] Agent Response Success:", data);
                    this.addChatMessage(data.message, 'bot');

                    if (data.action_taken || (data.intent && data.intent !== 'TALK')) {
                        console.log(`[DEBUG] Action detected. Refreshing...`);
                        const refresh = () => this.refreshData && this.refreshData();
                        refresh();
                        setTimeout(refresh, 1000);

                        if (data.expense_data) {
                            setTimeout(() => this.addReceiptCard(data.expense_data), 200);
                        }
                    }
                } else {
                    const errTxt = await response.text();
                    console.error("[DEBUG] Server rejected request:", response.status, errTxt);
                    this.addChatMessage('Lúcio tuvo un problema procesando eso. Intenta de nuevo por favor.', 'bot');
                }
            } catch (e) {
                console.error("[DEBUG] Network Error:", e);
                if (thinkingDiv && thinkingDiv.parentNode) thinkingDiv.parentNode.removeChild(thinkingDiv);
                this.addChatMessage('Error de red. Asegúrate de tener conexión y que el servidor funcione.', 'bot');
            }
        },

        addChatMessage: function (text, sender, isThinking = false) {
            const container = document.getElementById('chat-messages');
            if (!container) return null;

            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${sender}`;

            let content = text;
            if (isThinking) {
                content = '<span class="thinking-dots">...</span>';
            } else {
                // Allow HTML for images but escape newlines for text
                content = text.replace(/\n/g, '<br>');
            }

            msgDiv.innerHTML = `
                <div class="bubble">${content}</div>
                <div class="time">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
            `;

            container.appendChild(msgDiv);
            container.scrollTop = container.scrollHeight;
            return msgDiv;
        },

        addReceiptCard: function (data) {
            const container = document.getElementById('chat-messages');
            if (!container) return;

            const cardDiv = document.createElement('div');
            cardDiv.className = 'message bot';
            cardDiv.innerHTML = `
                <div class="bubble receipt-card">
                    <div style="font-weight:bold; margin-bottom:4px;">✅ Gasto Registrado</div>
                    <div style="font-size:0.9rem;">
                        $${data.amount.toLocaleString()} <br>
                        <small>${data.category} / ${data.concept}</small>
                    </div>
                </div>
                <div class="time">Sistema</div>
            `;
            container.appendChild(cardDiv);
            container.scrollTop = container.scrollHeight;
        },

        checkPendingGasto: async function () {
            try {
                let apiBase = '/api/v1';
                if (typeof CONFIG !== 'undefined') apiBase = CONFIG.API_BASE;
                else if (window.CONFIG) apiBase = window.CONFIG.API_BASE;

                const response = await fetch(`${apiBase}/agent/check-pending`, {
                    headers: { 'Authorization': `Bearer ${this.token || localStorage.getItem('auth_token')}` }
                });

                if (response.ok) {
                    const data = await response.json();
                    if (data.intent === 'ASK_CATEGORY') {
                        this.activePendingId = data.pending_id;
                        const overlay = document.getElementById('chat-overlay');
                        if (overlay && !overlay.classList.contains('active')) {
                            this.toggleChat();
                        }
                        this.addChatMessage(data.message, 'bot');
                    }
                }
            } catch (e) {
                console.error("Error in checkPendingGasto:", e);
            }
        },

        handleChatPhotoSelect: function (event) {
            const file = event.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = (e) => {
                const previewArea = document.getElementById('chat-preview-area');
                const previewImg = document.getElementById('chat-preview-img');
                if (previewArea && previewImg) {
                    previewImg.src = e.target.result;
                    previewArea.style.display = 'flex';
                }
            };
            reader.readAsDataURL(file);
        },

        removeChatPreview: function () {
            const previewArea = document.getElementById('chat-preview-area');
            const previewImg = document.getElementById('chat-preview-img');
            const photoInput = document.getElementById('chat-photo-input');
            if (previewArea) previewArea.style.display = 'none';
            if (previewImg) previewImg.src = '';
            if (photoInput) photoInput.value = '';
        }
    });

    // Handle Enter Key
    setTimeout(() => {
        const chatInput = document.getElementById('chat-input');
        if (chatInput) {
            chatInput.addEventListener('keypress', function (e) {
                if (e.key === 'Enter') {
                    if (window.financeApp && window.financeApp.sendChatMessage) {
                        window.financeApp.sendChatMessage();
                    }
                }
            });
        }

        const chatPhotoInput = document.getElementById('chat-photo-input');
        if (chatPhotoInput) {
            chatPhotoInput.addEventListener('change', function (e) {
                if (window.financeApp && window.financeApp.handleChatPhotoSelect) {
                    window.financeApp.handleChatPhotoSelect(e);
                }
            });
        }
    }, 1000);

})();
