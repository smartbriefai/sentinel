document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('chat-form');
    const input = document.getElementById('user-input');
    const chatHistory = document.getElementById('chat-history');
    const typingIndicator = document.getElementById('typing-indicator');

    // Create a unique session ID for this window (new conversation)
    const sessionId = 'web-session-' + Math.random().toString(36).substr(2, 9);
    
    // Get or create a persistent user ID for this browser to test "Returning Patient" memory
    let userId = localStorage.getItem('sentinel_user_id');
    if (!userId) {
        userId = 'patient-' + Math.random().toString(36).substr(2, 9);
        localStorage.setItem('sentinel_user_id', userId);
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const messageText = input.value.trim();
        if (!messageText) return;

        // 1. Add user message to UI
        appendMessage('user', messageText);
        input.value = '';
        
        // 2. Show typing indicator
        typingIndicator.style.display = 'block';
        chatHistory.scrollTop = chatHistory.scrollHeight;

        try {
            // 3. Send request to FastAPI backend
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: userId,
                    session_id: sessionId,
                    message: messageText
                })
            });

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            const data = await response.json();
            
            // 4. Hide typing and add AI response
            typingIndicator.style.display = 'none';
            appendMessage('ai', data.response);

        } catch (error) {
            typingIndicator.style.display = 'none';
            appendMessage('ai', '⚠️ Connection error. Sentinel is currently unreachable. Please ensure the backend server is running.');
            console.error('Error:', error);
        }
    });

    function appendMessage(sender, text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;
        
        let avatarSvg = '';
        if (sender === 'ai') {
            avatarSvg = `<svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>`;
        } else {
            avatarSvg = `<svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" stroke-width="2" fill="none"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>`;
        }

        // Convert newlines to <br> for HTML display
        const formattedText = text.replace(/\n/g, '<br>');

        messageDiv.innerHTML = `
            <div class="avatar">${avatarSvg}</div>
            <div class="message-content">${formattedText}</div>
        `;
        
        chatHistory.appendChild(messageDiv);
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }
});
