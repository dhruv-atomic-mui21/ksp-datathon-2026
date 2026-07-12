// KSP Client-Side Controller (Challenge 01 Chatbot & Challenge 02 Dashboard)

// 1. Dynamic API Base URL resolver for Zoho Catalyst environments (local and production)
let API_BASE = "/server/ksp_functions"; // Default relative path

const hostname = window.location.hostname;
if (hostname === "localhost" || hostname === "127.0.0.1") {
    API_BASE = "http://localhost:3000/server/ksp_functions";
} else {
    // Connect directly to live production Catalyst function URL
    API_BASE = "https://ksp-datathon-2026-60077655375.development.catalystserverless.in/server/ksp_functions";
}

console.log("Resolved API Base URL:", API_BASE);

// State Store
let conversationHistory = [];
let leafletMap = null;
let leafletMarkersLayer = null;
let leafletHotspotsLayer = null;
let visNetworkInstance = null;

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
    .then(res => res.json())
    .then(data => {
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
        appendMessageBubble("assistant", "Sorry, a connection error occurred with the Catalyst backend function.");
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

// Voice Output
function speakResponse(text) {
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel(); // stop previous speech
        const cleanText = text.replace(/[*#]/g, ""); // remove markdown markers
        const utterance = new SpeechSynthesisUtterance(cleanText);
        
        // Check language select
        const langSelect = document.getElementById("langSelect");
        if (langSelect && langSelect.value.startsWith("kn")) {
            utterance.lang = "kn-IN"; // Kannada voice
        } else {
            utterance.lang = "en-IN"; // Indian English voice
        }
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
    .then(res => res.blob())
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
        alert("Failed to export PDF report from Catalyst Functions.");
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

// ==========================================
// CHALLENGE 02: Analytics & Dashboard
// ==========================================

function switchDashboardTab(tabId, btn) {
    // Hide all contents
    const contents = document.querySelectorAll(".tab-content");
    contents.forEach(c => c.classList.remove("active"));
    
    // Deactivate all buttons
    const buttons = document.querySelectorAll(".tab-btn");
    buttons.forEach(b => b.classList.remove("active"));
    
    // Show active
    document.getElementById(tabId).classList.add("active");
    btn.classList.add("active");
}

// Tab 1: Geospatial Hotspots (Leaflet map + DBSCAN)
function loadGeospatialData() {
    const dist = document.getElementById("geoDistrictSelect") ? document.getElementById("geoDistrictSelect").value : "";
    const cat = document.getElementById("geoCategorySelect") ? document.getElementById("geoCategorySelect").value : "";
    
    const url = `${API_BASE}/api/geospatial?district=${encodeURIComponent(dist)}&category=${encodeURIComponent(cat)}`;
    
    fetch(url)
    .then(res => res.json())
    .then(data => {
        // 1. Initialize Map if not present
        if (!leafletMap) {
            leafletMap = L.map('map').setView([12.9716, 77.5946], 8);
            // Dark Mode CartoDB Tile Layer
            L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
                attribution: '&copy; CartoDB'
            }).addTo(leafletMap);
            
            leafletMarkersLayer = L.layerGroup().addTo(leafletMap);
            leafletHotspotsLayer = L.layerGroup().addTo(leafletMap);
        } else {
            leafletMarkersLayer.clearLayers();
            leafletHotspotsLayer.clearLayers();
        }

        // 2. Render Raw Case coordinate dots
        data.raw_cases.forEach(c => {
            L.circleMarker([c.lat, c.lng], {
                radius: 4,
                color: "#3b82f6",
                fillColor: "#3b82f6",
                fillOpacity: 0.8,
                weight: 1
            })
            .bindPopup(`<b>Crime No: ${c.no}</b><br>Category: ${c.category}<br>Date: ${c.date}`)
            .addTo(leafletMarkersLayer);
        });

        // 3. Render DBSCAN Hotspots (density clusters)
        data.hotspots.forEach(h => {
            // Draw a glowing radius ring
            L.circle([h.center_lat, h.center_lng], {
                radius: 1200, // meters
                color: "#ef4444",
                fillColor: "#ef4444",
                fillOpacity: 0.15,
                weight: 1.5
            })
            .bindPopup(`<b>DBSCAN Hotspot #${h.hotspot_id}</b><br>Crime Head: ${h.crime_category}<br>Density: ${h.case_count} cases<br>Peak Month: Month ${h.peak_month}`)
            .addTo(leafletHotspotsLayer);

            // Add center marker pin
            L.marker([h.center_lat, h.center_lng])
            .bindPopup(`<b>Hotspot #${h.hotspot_id} Centroid</b>`)
            .addTo(leafletHotspotsLayer);
        });

        // Fit map bounds if there are markers
        if (data.raw_cases.length > 0) {
            const group = new L.featureGroup(leafletMarkersLayer.getLayers());
            leafletMap.fitBounds(group.getBounds().pad(0.1));
        }

        // 4. Render Spike Alerts sidebar
        const alertsContainer = document.getElementById("spikeAlertsContainer");
        if (alertsContainer) {
            alertsContainer.innerHTML = "";
            if (data.spike_alerts && data.spike_alerts.length > 0) {
                data.spike_alerts.forEach(a => {
                    const alertDiv = document.createElement("div");
                    alertDiv.className = "glass-panel";
                    alertDiv.style.padding = "12px";
                    alertDiv.style.borderLeft = "4px solid var(--accent-red)";
                    
                    alertDiv.innerHTML = `
                        <div style="font-weight: 700; color: var(--accent-red); font-size: 0.8rem;">${a.status}</div>
                        <div style="font-weight: 600; font-size: 0.95rem; margin-top: 2px;">${a.district}</div>
                        <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 4px;">
                            Current Month: <b>${a.current_month_count} cases</b><br>
                            Historical Avg: <b>${a.historical_average} cases</b>
                        </div>
                    `;
                    alertsContainer.appendChild(alertDiv);
                });
            } else {
                alertsContainer.innerHTML = '<div style="color: var(--text-secondary); font-size: 0.85rem;">No active anomalies or district crime count spikes.</div>';
            }
        }
    })
    .catch(err => console.error("Geospatial fetch error:", err));
}

// Tab 2: Criminal Network Link Analysis (Vis.js + NetworkX)
function loadNetworkData() {
    const accusedName = document.getElementById("networkAccusedInput") ? document.getElementById("networkAccusedInput").value : "";
    
    let url = `${API_BASE}/api/network`;
    if (accusedName) {
        url += `?accused_name=${encodeURIComponent(accusedName)}`;
    }
    
    fetch(url)
    .then(res => res.json())
    .then(data => {
        const container = document.getElementById("networkContainer");
        if (!container) return;

        // Group colors for Vis.js representation
        const groupColors = {
            accused: { background: "#3b82f6", border: "#2563eb", highlight: { background: "#60a5fa", border: "#3b82f6" } },
            case: { background: "#ef4444", border: "#dc2626", highlight: { background: "#f87171", border: "#ef4444" } },
            phone: { background: "#f59e0b", border: "#d97706", highlight: { background: "#fbbf24", border: "#f59e0b" } },
            address: { background: "#10b981", border: "#059669", highlight: { background: "#34d399", border: "#10b981" } },
            bank: { background: "#8b5cf6", border: "#7c3aed", highlight: { background: "#a78bfa", border: "#8b5cf6" } }
        };

        // Format nodes
        const nodes = data.nodes.map(n => {
            const colors = groupColors[n.group] || groupColors.accused;
            return {
                id: n.id,
                label: n.label,
                shape: n.group === 'case' ? 'diamond' : 'dot',
                size: n.group === 'case' ? 16 : 12,
                color: colors,
                title: n.title,
                font: { color: "#f8fafc", size: 10 }
            };
        });

        // Initialize Vis.js network instance
        const graphData = {
            nodes: new vis.DataSet(nodes),
            edges: new vis.DataSet(data.edges)
        };
        
        const options = {
            physics: {
                barnesHut: { gravitationalConstant: -1800, centralGravity: 0.15, springLength: 95 }
            },
            interaction: { hover: true, tooltipDelay: 100 }
        };
        
        visNetworkInstance = new vis.Network(container, graphData, options);

        // Load repeat offenders in sidebar
        loadRepeatOffendersList();
    })
    .catch(err => console.error("Network analysis load error:", err));
}

function loadRepeatOffendersList() {
    fetch(`${API_BASE}/api/repeat-offenders`)
    .then(res => res.json())
    .then(data => {
        const container = document.getElementById("gangsListContainer");
        if (!container) return;

        container.innerHTML = "";
        data.forEach(o => {
            const card = document.createElement("div");
            card.className = "glass-panel";
            card.style.padding = "12px";
            card.style.cursor = "pointer";
            card.onclick = () => {
                document.getElementById("networkAccusedInput").value = o.name;
                loadNetworkData();
            };
            
            card.innerHTML = `
                <div style="font-weight: 700; color: var(--accent-blue);">${o.name}</div>
                <div style="color: var(--text-secondary); font-size: 0.8rem; margin-top: 4px;">
                    Linked Cases: <b>${o.case_count} cases</b><br>
                    Modus Operandi: <i>"${o.modus_operandi}"</i>
                </div>
            `;
            container.appendChild(card);
        });
    })
    .catch(err => console.error("Repeat offenders fetch error:", err));
}

function resetNetworkFilters() {
    if (document.getElementById("networkAccusedInput")) {
        document.getElementById("networkAccusedInput").value = "";
    }
    loadNetworkData();
}

// Tab 3: Risk Predictions & Isolation Forest Anomalies
function loadPredictiveData() {
    // 1. Get Risk Ratings (Random Forest + SHAP calculations)
    fetch(`${API_BASE}/api/predictive`)
    .then(res => res.json())
    .then(data => {
        const grid = document.getElementById("predictiveRiskGrid");
        if (!grid) return;

        grid.innerHTML = "";
        data.forEach(r => {
            const badgeClass = r.risk_rating === 'HIGH' ? 'badge-high' : (r.risk_rating === 'MEDIUM' ? 'badge-medium' : 'badge-low');
            const card = document.createElement("div");
            card.className = "glass-panel";
            card.style.padding = "20px";
            card.style.display = "flex";
            card.style.flexDirection = "column";
            card.style.justifyContent = "space-between";
            card.style.height = "160px";
            
            card.innerHTML = `
                <div>
                    <div style="font-weight: 700; font-size: 1.15rem; font-family: var(--font-header);">${r.district}</div>
                    <div style="margin-top: 6px;">
                        <span class="badge-risk ${badgeClass}">${r.risk_rating} Risk</span>
                    </div>
                </div>
                <button class="btn-primary" style="padding: 6px 12px; font-size: 0.75rem; width: fit-content;" onclick="openShapModal('${r.district}', '${JSON.stringify(r.explanations)}')">
                    SHAP Explanation
                </button>
            `;
            grid.appendChild(card);
        });
    })
    .catch(err => console.error("Predictive risk fetch error:", err));

    // 2. Get Flagged Anomalies (Isolation Forest)
    fetch(`${API_BASE}/api/anomalies`)
    .then(res => res.json())
    .then(data => {
        const tbody = document.getElementById("anomaliesTableBody");
        if (!tbody) return;

        tbody.innerHTML = "";
        data.forEach(a => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td style="font-weight: 600; color: var(--accent-blue);">${a.crime_no}</td>
                <td>${a.district}</td>
                <td>${a.crime_category}</td>
                <td style="color: var(--accent-red); font-weight: 600;">${a.reason_flagged}</td>
                <td><code>${a.anomaly_score}</code></td>
                <td style="font-size: 0.75rem; font-style: italic;">"${a.brief_facts.slice(0, 75)}..."</td>
            `;
            tbody.appendChild(tr);
        });
    })
    .catch(err => console.error("Anomalies load error:", err));
}

// SHAP modal handlers
function openShapModal(district, explanationsJson) {
    const modal = document.getElementById("shapModal");
    const title = document.getElementById("shapModalTitle");
    const container = document.getElementById("shapBarsContainer");
    
    if (!modal || !container) return;

    title.innerText = `${district} — Risk Explanation`;
    container.innerHTML = "";
    
    const expls = JSON.parse(explanationsJson.replace(/'/g, '"'));
    
    const labels = {
        historical_frequency: "Historical Crime Frequency",
        cybercrime_influence: "Cybercrime Ratio Influence",
        seasonal_susceptibility: "Seasonal Modifier Impact"
    };

    Object.entries(expls).forEach(([key, val]) => {
        const barWrapper = document.createElement("div");
        barWrapper.className = "contrib-bar-wrapper";
        
        // Percent calculations
        const widthVal = Math.min(Math.max(val * 10, 5), 100);
        
        barWrapper.innerHTML = `
            <div class="contrib-bar-label">
                <span>${labels[key] || key}</span>
                <strong>+${val}</strong>
            </div>
            <div class="contrib-bar-track">
                <div class="contrib-bar-fill" style="width: ${widthVal}%; background: ${key === 'seasonal_susceptibility' ? 'var(--accent-gold)' : 'var(--accent-blue)'};"></div>
            </div>
        `;
        container.appendChild(barWrapper);
    });

    modal.style.display = "flex";
}

function closeShapModal() {
    const modal = document.getElementById("shapModal");
    if (modal) modal.style.display = "none";
}

// Tab 4: Sociological Insights
function loadSociologicalData() {
    fetch(`${API_BASE}/api/sociological`)
    .then(res => res.json())
    .then(data => {
        // Render Age Demographics
        const ageContainer = document.getElementById("socioAgeContainer");
        if (ageContainer) {
            ageContainer.innerHTML = "";
            const dists = data.age_demographics.property_crime_distribution;
            const totals = data.age_demographics.overall_distribution;
            
            Object.keys(dists).forEach(bin => {
                const count = dists[bin];
                const total = totals[bin] || 1;
                const pct = Math.round((count / total) * 100);
                
                const barWrapper = document.createElement("div");
                barWrapper.className = "contrib-bar-wrapper";
                barWrapper.innerHTML = `
                    <div class="contrib-bar-label">
                        <span>Age Bracket: ${bin} yrs</span>
                        <strong>${count} thefts (${pct}% density)</strong>
                    </div>
                    <div class="contrib-bar-track">
                        <div class="contrib-bar-fill" style="width: ${pct}%; background: var(--accent-blue);"></div>
                    </div>
                `;
                ageContainer.appendChild(barWrapper);
            });
        }

        // Render Occupation Table
        const tbody = document.getElementById("socioOccTableBody");
        if (tbody) {
            tbody.innerHTML = "";
            // Sort occupation correlations by count descending
            const sortedOccs = data.occupation_correlations.sort((a,b) => b.incident_count - a.incident_count);
            sortedOccs.forEach(o => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td style="font-weight: 600;">${o.occupation}</td>
                    <td>${o.crime_type}</td>
                    <td><b>${o.incident_count}</b> cases registered</td>
                `;
                tbody.appendChild(tr);
            });
        }
    })
    .catch(err => console.error("Sociological fetch error:", err));
}

// Tab 5: Security Compliance Audit (RBAC Protection)
function loadAuditData() {
    const role = localStorage.getItem("ksp_user_role") || "investigator";
    const accessDeniedPanel = document.getElementById("auditAccessDenied");
    const logsPanel = document.getElementById("auditLogsPanel");
    
    if (!accessDeniedPanel || !logsPanel) return;

    if (role.toLowerCase() !== "supervisor" && role.toLowerCase() !== "policymaker") {
        accessDeniedPanel.style.display = "block";
        logsPanel.style.display = "none";
        return;
    }

    accessDeniedPanel.style.display = "none";
    logsPanel.style.display = "block";

    fetch(`${API_BASE}/api/audit-logs?role=${role}`)
    .then(res => res.json())
    .then(data => {
        const tbody = document.getElementById("auditTableBody");
        if (!tbody) return;

        tbody.innerHTML = "";
        data.forEach(log => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><code>${log.Timestamp}</code></td>
                <td>${log.UserEmail}</td>
                <td style="font-weight:600; color:var(--accent-gold); text-transform:uppercase;">${log.UserRole}</td>
                <td>${log.Action}</td>
                <td><code style="font-size:0.75rem; color:#34d399;">${log.QueryExecuted ? log.QueryExecuted.slice(0, 60) + "..." : "N/A"}</code></td>
            `;
            tbody.appendChild(tr);
        });
    })
    .catch(err => {
        console.error("Audit log load error:", err);
        tbody.innerHTML = "<tr><td colspan='5'>Error retrieving audit logs.</td></tr>";
    });
}
