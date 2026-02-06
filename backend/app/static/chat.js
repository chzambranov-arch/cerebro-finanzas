
(function () {
    // Ensure FinanceApp exists
    if (!window.FinanceApp) {
        console.error("FinanceApp not found. Chat module cannot load.");
        return;
    }

    // Extend prototype with Chat methods
    Object.assign(FinanceApp.prototype, {

        toggleChat: function () {
            const overlay = document.getElementById('chat-overlay');
            if (overlay) {
                const isActive = overlay.classList.contains('active');
                if (isActive) {
                    overlay.classList.remove('active');
                    this.toggleBodyModal(false);
                } else {
                    overlay.classList.add('active');
                    this.toggleBodyModal(true);
                    setTimeout(() => {
                        const input = document.getElementById('chat-input');
                        if (input) input.focus();
                    }, 300);
                }
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
                // Use CONFIG from app.js scope if available, else assume standard path
                const apiBase = window.CONFIG ? window.CONFIG.API_BASE : '/api/v1';

                const response = await fetch(`${apiBase}/agent/chat`, {
                    method: 'POST',
                    headers: { ...this.getHeaders(), 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: msgText })
                });

                // Remove logic for thinking bubble
                if (thinkingDiv && thinkingDiv.parentNode) {
                    thinkingDiv.parentNode.removeChild(thinkingDiv);
                }

                if (response.ok) {
                    const data = await response.json();
                    this.addChatMessage(data.message, 'bot');

                    if (data.action_taken) {
                        // Refresh Dashboard Data in Background
                        this.refreshData();
                        // Maybe show a mini receipt card in chat?
                        if (data.expense_data) {
                            this.addReceiptCard(data.expense_data);
                        }
                    }
                } else {
                    this.addChatMessage('Tuve un pequeño error con el servidor. Intenta de nuevo.', 'bot');
                }

            } catch (e) {
                console.error(e);
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
                // Determine if text contains newlines, replace with <br>
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
            const cardDiv = document.createElement('div');
            cardDiv.className = 'message bot';
            // Use receipt-card class from css
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
        }
    });

    console.log('FinanceApp Chat Module Loaded');

    // Setup Enter Key listener for chat
    const chatInput = document.getElementById('chat-input');
    if (chatInput) {
        chatInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                // Need to call the method on the instance
                // We assume 'window.financeApp' is the instance name in app.js
                // app.js: window.financeApp = new FinanceApp();
                if (window.financeApp) window.financeApp.sendChatMessage();
            }
        });
    }

})();
