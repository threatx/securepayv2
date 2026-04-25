/**
 * Awareness Chatbot Frontend
 * Manages in-memory chat history and communicates with /api/awareness/chat
 */

let chatHistory = [];

const messagesEl = document.getElementById('chat-messages');
const inputEl = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const sourcesPanel = document.getElementById('sources-panel');
const sourcesList = document.getElementById('sources-list');

// Enter key to send
inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Quick question buttons
document.querySelectorAll('.quick-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        inputEl.value = btn.dataset.msg;
        sendMessage();
    });
});

async function sendMessage() {
    const message = inputEl.value.trim();
    if (!message) return;

    // Add user message to UI
    addMessage(message, 'user');
    inputEl.value = '';

    // Disable input while waiting
    inputEl.disabled = true;
    sendBtn.disabled = true;

    // Hide quick questions after first message
    document.getElementById('quick-questions').style.display = 'none';

    // Show loading
    const loadingEl = document.createElement('div');
    loadingEl.className = 'loading-message';
    loadingEl.innerHTML = 'Thinking<span class="loading-dots"></span>';
    messagesEl.appendChild(loadingEl);
    scrollToBottom();

    try {
        const response = await fetch('/api/awareness/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                history: chatHistory
            })
        });

        loadingEl.remove();

        if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: 'Request failed' }));
            throw new Error(err.detail || 'Request failed');
        }

        const data = await response.json();

        // Add assistant response
        addMessage(data.response, 'assistant');

        // Update history
        chatHistory.push({ role: 'user', content: message });
        chatHistory.push({ role: 'assistant', content: data.response });

        // Show sources
        if (data.sources && data.sources.length > 0) {
            showSources(data.sources);
        }

    } catch (err) {
        loadingEl.remove();
        addMessage('Sorry, something went wrong: ' + err.message, 'assistant');
    }

    // Re-enable input
    inputEl.disabled = false;
    sendBtn.disabled = false;
    inputEl.focus();
}

function addMessage(content, role) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}-message`;

    if (role === 'assistant') {
        const label = document.createElement('div');
        label.className = 'message-label';
        label.textContent = 'SecurePay Assistant';
        msgDiv.appendChild(label);
    }

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = formatResponse(content);
    msgDiv.appendChild(contentDiv);

    messagesEl.appendChild(msgDiv);
    scrollToBottom();
}

function formatResponse(text) {
    // Convert markdown-style formatting to HTML
    let html = text
        // Bold
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        // Bullet points
        .replace(/^[-*]\s+(.+)$/gm, '<li>$1</li>')
        // Numbered lists
        .replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>')
        // Line breaks
        .replace(/\n\n/g, '</p><p>')
        .replace(/\n/g, '<br>');

    // Wrap consecutive <li> items in <ul>
    html = html.replace(/(<li>.*?<\/li>(\s*<br>)?)+/gs, (match) => {
        const cleaned = match.replace(/<br>/g, '');
        return '<ul>' + cleaned + '</ul>';
    });

    return '<p>' + html + '</p>';
}

function showSources(sources) {
    sourcesList.innerHTML = '';
    sources.forEach(s => {
        const span = document.createElement('span');
        span.className = 'source-item';
        span.textContent = `${s.title} (${(s.similarity * 100).toFixed(0)}%)`;
        sourcesList.appendChild(span);
    });
    sourcesPanel.classList.remove('hidden');
}

function clearChat() {
    chatHistory = [];
    messagesEl.innerHTML = '';

    // Re-add welcome message
    const welcome = document.createElement('div');
    welcome.className = 'message assistant-message';
    welcome.innerHTML = `
        <div class="message-label">SecurePay Assistant</div>
        <div class="message-content">
            Welcome! I can help you learn about UPI fraud in India. Ask me about:
            <ul>
                <li>Types of UPI scams (QR code fraud, KYC scams, etc.)</li>
                <li>How to stay safe while using UPI</li>
                <li>What to do if you've been scammed</li>
                <li>Red flags to watch out for</li>
            </ul>
        </div>
    `;
    messagesEl.appendChild(welcome);

    // Show quick questions again
    document.getElementById('quick-questions').style.display = 'flex';

    // Hide sources
    sourcesPanel.classList.add('hidden');
}

function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
}
