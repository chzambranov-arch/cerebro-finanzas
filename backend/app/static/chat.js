
(function () {
    console.log("Chat Module Loading...");

    // 1. Resolve FinanceApp Class
    // In global scope, 'class FinanceApp' might not be on 'window' property directly
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

    // Extend prototype
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

                    // Focus input
                    setTimeout(() => {
                        const input = document.getElementById('chat-input');
                        if (input) input.focus();
                    }, 300);
                }
            } else {
                console.error("Chat overlay element #chat-overlay not found in DOM");
            }
        },

        sendChatMessage: async function () {
            const input = document.getElementById('chat-input');
            const msgText = input.value.trim();
            if (!msgText) return;

            // 1. Add User Message
            this.addChatMessage(msgText, 'user');
            input.value = '';

            // 2. Add Thinking Message
            const thinkingDiv = this.addChatMessage('Pensando...', 'bot', true);

            try {
                // Determine API Base
                // If CONFIG is not available, try to infer or fallback
                let apiBase = '/api/v1';
                if (typeof CONFIG !== 'undefined') apiBase = CONFIG.API_BASE;
                else if (window.CONFIG) apiBase = window.CONFIG.API_BASE;

                const payload = { message: msgText };
                if (this.activePendingId) {
                    payload.pending_id = this.activePendingId;
                    // Reset after sending to not reuse it accidentally
                    this.activePendingId = null;
                }

                const response = await fetch('/api/v3/lucio/chat', {
                    method: 'POST',
                    headers: { ...this.getHeaders(), 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                // Remove thinking
                if (thinkingDiv && thinkingDiv.parentNode) {
                    thinkingDiv.parentNode.removeChild(thinkingDiv);
                }

                if (response.ok) {
                    const data = await response.json();
                    console.log("[DEBUG] Lúcio (n8n) Response:", data);

                    // Support both v1 (message) and v2/n8n (reply) response formats
                    const botReply = data.reply || data.message || data.output || "No pude generar una respuesta.";
                    this.addChatMessage(botReply, 'bot');

                    // If intent is not TALK, it means we likely changed data (CREATE/UPDATE/DELETE)
                    if (data.action_taken || (data.intent && data.intent !== 'TALK')) {
                        console.log(`[DEBUG] Modification detected. Intent: ${data.intent}. Refreshing...`);

                        const refresh = async () => {
                            try {
                                console.log("[DEBUG] Calling refreshData()...");
                                if (window.financeApp && window.financeApp.refreshData) {
                                    await window.financeApp.refreshData();
                                } else if (this.refreshData) {
                                    await this.refreshData();
                                }
                            } catch (e) {
                                console.error("Error refreshing data:", e);
                            }
                        };

                        // Triple refresh for stability (PWA/Local sync)
                        refresh();
                        setTimeout(refresh, 500);
                        setTimeout(refresh, 1500);

                        // Receipt Card safety
                        if (data.expense_data) {
                            setTimeout(() => this.addReceiptCard(data.expense_data), 200);
                        }
                    }
                } else {
                    const errTxt = await response.text();
                    console.error("Agent Error:", errTxt);
                    this.addChatMessage('Tuve un problema de conexión. Intenta de nuevo.', 'bot');
                }

            } catch (e) {
                console.error("Network Error:", e);
                // Remove thinking if error
                if (thinkingDiv && thinkingDiv.parentNode) {
                    thinkingDiv.parentNode.removeChild(thinkingDiv);
                }
                this.addChatMessage('Error de red. Revisa tu conexión.', 'bot');
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
                // Asegurar que sea string para evitar errores de .replace
                const safeText = (typeof text === 'string') ? text : JSON.stringify(text);
                content = safeText.replace(/\n/g, '<br>');
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
    }, 1000);

})();
