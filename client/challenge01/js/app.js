// KSP Client-Side Controller (Challenge 01 Conversational AI)

function resolveApiBase() {
    const hostname = window.location.hostname;
    if (hostname === "localhost" || hostname === "127.0.0.1") {
        return "http://localhost:3000/server/ksp_functions";
    }
    return "/server/ksp_functions";
}

let API_BASE = resolveApiBase();
console.log("Resolved API Base URL:", API_BASE);

// State Store
let conversationHistory = [];

// ==========================================
// CHALLENGE 01: Intelligent Conversational AI
// ==========================================

function sendQuery() {
    const chatInput = document.getElementById("chatInput");
    const queryText = chatInput.value.trim();
    if (!queryText) return;

    // Clear input
    chatInput.value = "";
    
    // Disable inputs
    chatInput.disabled = true;
    
    // Add user bubble
    appendMessageBubble("user", queryText);

    // Get Simulated User Role
    const userRole = localStorage.getItem("ksp_user_role") || "investigator";
    const userEmail = localStorage.getItem("ksp_user_email") || "io.patil@ksp.gov.in";

    // Call API
    fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            query: queryText,
            history: conversationHistory,
            user: { email: userEmail, role: userRole }
        })
    })
    .then(res => {
        if (res.status === 429) {
            throw new Error("Rate limit exceeded. Please wait a minute.");
        }
        return res.json();
    })
    .then(data => {
        if (data.error) {
            appendMessageBubble("assistant", `Security alert: ${data.error}`);
            return;
        }
        // Update history
        conversationHistory = data.history;

        // Append assistant bubble
        appendMessageBubble("assistant", data.answer, data.sql, data.results);

        // Voice Output (Speech Synthesis) if checked
        const ttsToggle = document.getElementById("ttsToggle");
        if (ttsToggle && ttsToggle.checked) {
            speakResponse(data.answer);
        }
    })
    .catch(err => {
        console.error("Chat error:", err);
        appendMessageBubble("assistant", `Sorry, an error occurred: ${err.message || "Connection error with backend."}`);
    })
    .finally(() => {
        chatInput.disabled = false;
        chatInput.focus();
    });
}

function appendMessageBubble(role, text, sql = null, results = null) {
    const chatMessages = document.getElementById("chatMessages");
    if (!chatMessages) return;

    const bubble = document.createElement("div");
    bubble.className = `message-bubble ${role === 'user' ? 'message-user' : 'message-assistant'}`;
    
    // Convert newlines to breaks
    bubble.innerHTML = text.replace(/\n/g, "<br>");

    // Add metadata for assistant (SQL explainability)
    if (role === 'assistant' && sql) {
        const metaDiv = document.createElement("div");
        metaDiv.className = "message-meta";
        
        const explainBtn = document.createElement("button");
        explainBtn.className = "btn-explain";
        explainBtn.innerText = "Explain Query (Transparency)";
        
        // Escape characters for injection
        const escapedSql = sql.replace(/'/g, "\\'").replace(/"/g, '\\"');
        const escapedResults = JSON.stringify(results).replace(/'/g, "\\'").replace(/"/g, '\\"');
        
        explainBtn.onclick = () => openExplainDrawer(escapedSql, escapedResults);
        
        metaDiv.appendChild(explainBtn);
        bubble.appendChild(metaDiv);
    }

    chatMessages.appendChild(bubble);
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Voice Output via Backend (Sarvam AI TTS)
async function speakResponse(text) {
    const cleanText = text.replace(/[*#]/g, ""); // remove markdown markers
    
    // Check language
    const langSelect = document.getElementById("langSelect");
    let lang = "en-IN";
    if (langSelect && langSelect.value.startsWith("kn")) {
        lang = "kn-IN"; // Kannada voice
    }
    
    // Fallback directly to native TTS to save 2+ seconds API delay
    fallbackTTS(cleanText, lang);
}

// Fallback to browser's native TTS if Sarvam fails or is unconfigured
function fallbackTTS(text, lang) {
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel(); 
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = lang;
        window.speechSynthesis.speak(utterance);
    }
}

// Voice Input (Web Speech API)
let recognition = null;
function toggleSpeech() {
    const micBtn = document.getElementById("micBtn");
    if (!micBtn) return;

    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        alert("Web Speech Input is not supported by this browser.");
        return;
    }

    if (recognition) {
        recognition.stop();
        recognition = null;
        micBtn.classList.remove("recording");
        return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    
    // Set language based on dropdown
    const langSelect = document.getElementById("langSelect");
    recognition.lang = langSelect ? langSelect.value : "en-US";
    recognition.interimResults = false;
    
    recognition.onstart = function() {
        micBtn.classList.add("recording");
    };
    
    recognition.onresult = function(event) {
        const transcript = event.results[0][0].transcript;
        document.getElementById("chatInput").value = transcript;
        sendQuery(); // auto-submit query
    };
    
    recognition.onerror = function(event) {
        console.error("Speech recognition error:", event.error);
        micBtn.classList.remove("recording");
    };
    
    recognition.onend = function() {
        micBtn.classList.remove("recording");
        recognition = null;
    };
    
    recognition.start();
}

// Export Chat History to PDF
function exportConversationPDF() {
    if (conversationHistory.length === 0) {
        alert("Conversation history is empty.");
        return;
    }
    
    fetch(`${API_BASE}/api/export-pdf`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ history: conversationHistory })
    })
    .then(res => {
        if (res.status === 429) {
            throw new Error("Rate limit exceeded. Please wait a minute.");
        }
        return res.blob();
    })
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "ksp_investigation_report.pdf";
        document.body.appendChild(a);
        a.click();
        a.remove();
    })
    .catch(err => {
        console.error("PDF export error:", err);
        alert(`Failed to export PDF report: ${err.message || "Connection error."}`);
    });
}

function clearConversation() {
    conversationHistory = [];
    const chatMessages = document.getElementById("chatMessages");
    if (chatMessages) {
        chatMessages.innerHTML = `
            <div class="message-bubble message-assistant">
                Chat history cleared. How can I assist you with your investigation now?
            </div>
        `;
    }
}

// Explainability Slide-out Drawer
function openExplainDrawer(sql, resultsJson) {
    const drawer = document.getElementById("explainDrawer");
    const drawerSql = document.getElementById("drawerSql");
    const tableHead = document.getElementById("drawerTableHead");
    const tableBody = document.getElementById("drawerTableBody");
    
    if (!drawer || !drawerSql) return;

    drawerSql.innerText = sql;
    
    const results = JSON.parse(resultsJson);
    
    // Build table
    tableHead.innerHTML = "";
    tableBody.innerHTML = "";
    
    if (results && results.length > 0) {
        // Headers
        const headers = Object.keys(results[0]);
        headers.forEach(h => {
            const th = document.createElement("th");
            th.innerText = h;
            tableHead.appendChild(th);
        });
        
        // Rows
        results.forEach(row => {
            const tr = document.createElement("tr");
            headers.forEach(h => {
                const td = document.createElement("td");
                td.innerText = row[h] !== null ? row[h] : "NULL";
                tr.appendChild(td);
            });
            tableBody.appendChild(tr);
        });
    } else {
        tableHead.innerHTML = "<th>Columns</th>";
        tableBody.innerHTML = "<tr><td>No records returned or query returned empty.</td></tr>";
    }

    drawer.classList.add("open");
}

function closeDrawer() {
    const drawer = document.getElementById("explainDrawer");
    if (drawer) {
        drawer.classList.remove("open");
    }
}
