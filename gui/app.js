// GNS3 Automation Controller Client
const API_BASE = "";

// DOM Elements
const editor = document.getElementById("intent-editor");
const saveBtn = document.getElementById("save-intent-btn");
const generateBtn = document.getElementById("generate-configs-btn");
const deployBtn = document.getElementById("deploy-btn");
const statusBadge = document.getElementById("gns-status");
const consoleLog = document.getElementById("console-log");
const tableBody = document.getElementById("address-table-body");
const canvas = document.getElementById("topology-canvas");
const detailsName = document.getElementById("details-node-name");
const detailsBody = document.getElementById("details-body");
const copyConfigBtn = document.getElementById("copy-config-btn");
const clearLogsBtn = document.getElementById("clear-logs-btn");
const maximizeBtn = document.getElementById("maximize-canvas-btn");

let globalTopology = null;
let activeNode = null;
let isDeploying = false;
let deployPollInterval = null;
let lastLogCount = 0;

// Initialize app
window.addEventListener("DOMContentLoaded", () => {
  appendLog("System initialized. Connecting to backend services...");
  fetchIntent();
  fetchTopology();
  checkGNS3Status();
  
  // Set up periodic check for GNS3 Status
  setInterval(checkGNS3Status, 5000);
});

// Event Listeners
saveBtn.addEventListener("click", saveIntent);
generateBtn.addEventListener("click", generateConfigs);
deployBtn.addEventListener("click", deployTopology);
clearLogsBtn.addEventListener("click", () => {
  consoleLog.innerHTML = "";
  appendLog("Logs cleared.");
});
copyConfigBtn.addEventListener("click", copyConfigToClipboard);
maximizeBtn.addEventListener("click", toggleMaximizeCanvas);

function toggleMaximizeCanvas() {
  const grid = document.querySelector(".dashboard-grid");
  grid.classList.toggle("canvas-maximized");
  if (grid.classList.contains("canvas-maximized")) {
    maximizeBtn.textContent = "Restore";
    appendLog("Canvas view maximized.");
  } else {
    maximizeBtn.textContent = "Maximize";
    appendLog("Canvas view restored.");
  }
}

// Logging Helper
function appendLog(message, type = "info") {
  const line = document.createElement("div");
  line.className = `log-line-${type}`;
  
  const timestamp = new Date().toLocaleTimeString();
  line.textContent = `[${timestamp}] ${message}`;
  
  consoleLog.appendChild(line);
  consoleLog.scrollTop = consoleLog.scrollHeight;
}

// Fetch intent.json
async function fetchIntent() {
  try {
    const res = await fetch(`${API_BASE}/api/intent`);
    if (!res.ok) throw new Error("Failed to load intent file");
    const data = await res.json();
    editor.value = JSON.stringify(data, null, 2);
    appendLog("Loaded intent configuration file.", "success");
  } catch (err) {
    appendLog(`Error loading intent: ${err.message}`, "error");
  }
}

// Save intent.json
async function saveIntent() {
  try {
    let parsedJson;
    try {
      parsedJson = JSON.parse(editor.value);
    } catch (e) {
      alert("Invalid JSON syntax. Please check your config.");
      appendLog("JSON syntax check failed. Save aborted.", "error");
      return;
    }

    appendLog("Saving intent configuration...");
    const res = await fetch(`${API_BASE}/api/intent`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(parsedJson)
    });
    if (!res.ok) throw new Error(await res.text());
    
    appendLog("Saved intent.json successfully.", "success");
    // Reload topology
    fetchTopology();
  } catch (err) {
    appendLog(`Save failed: ${err.message}`, "error");
  }
}

// Fetch GNS3 Server connection status
async function checkGNS3Status() {
  const gnsStatusValue = document.getElementById("gns-status-value");
  try {
    const res = await fetch(`${API_BASE}/api/gns-status`);
    const status = await res.json();
    if (status.online) {
      statusBadge.textContent = `GNS3 Online (${status.server})`;
      statusBadge.className = "connection-badge";
      if (gnsStatusValue) {
        gnsStatusValue.innerHTML = `<span class="kpi-status-dot online"></span>Online`;
      }
    } else {
      statusBadge.textContent = "GNS3 Offline";
      statusBadge.className = "connection-badge disconnected";
      if (gnsStatusValue) {
        gnsStatusValue.innerHTML = `<span class="kpi-status-dot offline"></span>Offline`;
      }
    }
  } catch (e) {
    statusBadge.textContent = "GNS3 Offline";
    statusBadge.className = "connection-badge disconnected";
    if (gnsStatusValue) {
      gnsStatusValue.innerHTML = `<span class="kpi-status-dot offline"></span>Offline`;
    }
  }
}

// Fetch Addressing and Topology details
async function fetchTopology() {
  try {
    const res = await fetch(`${API_BASE}/api/topology`);
    if (!res.ok) throw new Error("Failed to allocate IP subnets");
    const data = await res.json();
    globalTopology = data;
    renderAddressTable(data);
    drawTopologyCanvas(data);
    appendLog("Calculated IP plans and refreshed topology map.", "success");
  } catch (err) {
    appendLog(`Topology error: ${err.message}`, "error");
  }
}

// Render IP addressing table
function renderAddressTable(data) {
  tableBody.innerHTML = "";
  
  for (const routerName in data) {
    const rData = data[routerName];
    const tr = document.createElement("tr");
    
    const loopbackStr = `${rData.loopback.ip} (Loopback0)`;
    const externalLinks = [];
    const internalLinks = [];
    
    for (const intfName in rData.interfaces) {
      const intf = rData.interfaces[intfName];
      const shortIntName = intfName.replace("FastEthernet", "F");
      const shortPeerName = intf.peer_interface.replace("FastEthernet", "F");
      const desc = `${shortIntName}: ${intf.ip} ➔ ${intf.peer_node} (${shortPeerName})`;
      if (intf.type === "external") {
        externalLinks.push(desc);
      } else {
        const costStr = intf.ospf_cost ? ` (cost: ${intf.ospf_cost})` : "";
        internalLinks.push(`${desc}${costStr}`);
      }
    }
    
    const igpDomain = rData.as === 100 ? "AS X (RIP)" : "AS Y (OSPF)";
    
    tr.innerHTML = `
      <td style="font-weight:700; color:var(--accent-blue);">${rData.name}</td>
      <td>AS ${rData.as}</td>
      <td style="font-weight:600; color:${rData.as === 100 ? 'var(--accent-blue)' : 'var(--accent-purple)'};">${igpDomain}</td>
      <td style="font-family:'JetBrains Mono', monospace; font-weight: 500;">${loopbackStr}</td>
      <td style="font-family:'JetBrains Mono', monospace; font-size:11px; color: var(--accent-red);">${externalLinks.join("<br>") || "None"}</td>
      <td style="font-family:'JetBrains Mono', monospace; font-size:11px;">${internalLinks.join("<br>")}</td>
    `;
    tableBody.appendChild(tr);
  }
}

// Draw Symmetrical network topology in SVG
function drawTopologyCanvas(data) {
  // Clear SVG canvas
  canvas.innerHTML = `
    <defs>
      <marker id="arrow" viewBox="0 0 10 10" refX="28" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(0,0,0,0.2)" />
      </marker>
    </defs>
  `;
  
  // Set explicit viewBox on SVG for scaling and responsive behavior
  canvas.setAttribute("viewBox", "0 0 1100 480");
  
  // GNS3 coordinate limits mapping
  const mapX = (gx) => ((gx + 520) / 1040) * 940 + 80;
  const mapY = (gy) => ((gy + 110) / 220) * 360 + 60;

  // 1. Draw Links first (under nodes)
  const drawnLinks = new Set();
  
  for (const routerName in data) {
    const nodeA = data[routerName];
    const ax = mapX(nodeA.coordinates.x);
    const ay = mapY(nodeA.coordinates.y);
    
    for (const intfName in nodeA.interfaces) {
      const intf = nodeA.interfaces[intfName];
      const peerName = intf.peer_node;
      const nodeB = data[peerName];
      
      if (!nodeB) continue;
      
      const bx = mapX(nodeB.coordinates.x);
      const by = mapY(nodeB.coordinates.y);
      
      const linkKey = [routerName, peerName].sort().join("-");
      if (drawnLinks.has(linkKey)) continue;
      drawnLinks.add(linkKey);
      
      // Calculate offset line endpoints to stop cleanly outside node circles
      const dx = bx - ax;
      const dy = by - ay;
      const len = Math.sqrt(dx*dx + dy*dy);
      
      let x1 = ax, y1 = ay, x2 = bx, y2 = by;
      if (len > 0) {
        // Offset link ends by 22px from node centers
        x1 = ax + (dx / len) * 22;
        y1 = ay + (dy / len) * 22;
        x2 = bx - (dx / len) * 22;
        y2 = by - (dy / len) * 22;
      }
      
      // Line Element
      const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
      line.setAttribute("x1", x1);
      line.setAttribute("y1", y1);
      line.setAttribute("x2", x2);
      line.setAttribute("y2", y2);
      
      let linkClass = "network-link";
      if (intf.type === "external") {
        linkClass += " inter-as";
      } else if (nodeA.as === 100) {
        linkClass += " as-100";
      } else {
        linkClass += " as-200";
      }
      
      line.setAttribute("class", linkClass);
      canvas.appendChild(line);
      
      if (len > 0) {
        // Aligned positions for port/interface labels (offset by 33px)
        const lx1 = ax + (dx / len) * 33;
        const ly1 = ay + (dy / len) * 33;
        const lx2 = bx - (dx / len) * 33;
        const ly2 = by - (dy / len) * 33;
        
        const shortIntfA = intfName.replace("FastEthernet", "F");
        const shortIntfB = intf.peer_interface.replace("FastEthernet", "F");
        
        const labelA = document.createElementNS("http://www.w3.org/2000/svg", "text");
        labelA.setAttribute("x", lx1);
        labelA.setAttribute("y", ly1 + 3);
        labelA.setAttribute("class", "link-label");
        labelA.setAttribute("text-anchor", "middle");
        labelA.textContent = shortIntfA;
        canvas.appendChild(labelA);
        
        const labelB = document.createElementNS("http://www.w3.org/2000/svg", "text");
        labelB.setAttribute("x", lx2);
        labelB.setAttribute("y", ly2 + 3);
        labelB.setAttribute("class", "link-label");
        labelB.setAttribute("text-anchor", "middle");
        labelB.textContent = shortIntfB;
        canvas.appendChild(labelB);
      }
    }
  }

  // 2. Draw Nodes (Router cards)
  for (const routerName in data) {
    const node = data[routerName];
    const nx = mapX(node.coordinates.x);
    const ny = mapY(node.coordinates.y);
    
    const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
    group.setAttribute("class", "node-group");
    group.setAttribute("transform", `translate(${nx}, ${ny})`);
    
    // Add Click listener to show node operational details
    group.addEventListener("click", () => inspectNode(node));
    
    // Clean outer ring circle (radius 16px)
    const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    circle.setAttribute("cx", "0");
    circle.setAttribute("cy", "0");
    circle.setAttribute("r", "16");
    circle.setAttribute("id", `circle-${node.name}`);
    circle.setAttribute("class", `node-circle ${node.as === 200 ? 'as-200' : 'as-100'}`);
    
    // Concentric core dot (radius 5px)
    const coreDot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    coreDot.setAttribute("cx", "0");
    coreDot.setAttribute("cy", "0");
    coreDot.setAttribute("r", "5");
    coreDot.setAttribute("class", "node-core");
    
    // Router Name (placed cleanly above the node circle)
    const textName = document.createElementNS("http://www.w3.org/2000/svg", "text");
    textName.setAttribute("x", "0");
    textName.setAttribute("y", "-22");
    textName.setAttribute("text-anchor", "middle");
    textName.setAttribute("class", "node-text");
    textName.textContent = node.name;
    
    // Router Loopback IP (placed cleanly below the node circle)
    const textIp = document.createElementNS("http://www.w3.org/2000/svg", "text");
    textIp.setAttribute("x", "0");
    textIp.setAttribute("y", "26");
    textIp.setAttribute("text-anchor", "middle");
    textIp.setAttribute("class", "node-ip-text");
    textIp.textContent = node.loopback.ip;
    
    group.appendChild(circle);
    group.appendChild(coreDot);
    group.appendChild(textName);
    group.appendChild(textIp);
    canvas.appendChild(group);
  }
}

// Click Node to Inspect details in Operations Control Panel
async function inspectNode(node) {
  activeNode = node.name;
  detailsName.textContent = `Router: ${node.name}`;
  copyConfigBtn.style.display = "inline-flex";
  
  // Highlight node selection in diagram map
  document.querySelectorAll(".node-circle").forEach(c => c.classList.remove("selected"));
  const activeCircle = document.getElementById(`circle-${node.name}`);
  if (activeCircle) {
    activeCircle.classList.add("selected");
  }
  
  let interfacesHtml = "";
  for (const name in node.interfaces) {
    const intf = node.interfaces[name];
    const costText = intf.ospf_cost ? `<span style="color:var(--accent-purple);">Cost: ${intf.ospf_cost}</span>` : "";
    const shortPeerInt = intf.peer_interface.replace("FastEthernet", "F");
    const shortIntName = name.replace("FastEthernet", "F");
    
    interfacesHtml += `
      <div style="border-bottom:1px dashed var(--border-color-dim); padding:6px 0; display:flex; justify-content:space-between; font-size:11px;">
        <span style="font-family:monospace; font-weight:600;">${shortIntName}</span>
        <span style="font-family:monospace; color:var(--accent-blue);">${intf.ip}</span>
        <span style="color:var(--text-secondary); font-size:10px;">➔ ${intf.peer_node} (${shortPeerInt}) ${costText}</span>
      </div>
    `;
  }
  
  detailsBody.innerHTML = `
    <div class="details-row">
      <span class="details-label">AS Number</span>
      <span class="details-value">AS ${node.as}</span>
    </div>
    <div class="details-row">
      <span class="details-label">IGP Domain</span>
      <span class="details-value" style="text-transform:uppercase; color:${node.as === 100 ? 'var(--accent-blue)' : 'var(--accent-purple)'}; font-weight:700;">${node.as === 100 ? "RIP" : "OSPF"}</span>
    </div>
    <div class="details-row">
      <span class="details-label">Loopback IP</span>
      <span class="details-value" style="font-family:monospace; color:var(--accent-green);">${node.loopback.ip}</span>
    </div>
    
    <div style="margin-top:10px; display:flex; flex-direction:column; gap:4px;">
      <span class="details-label" style="font-size:11px; font-weight:600; text-transform:uppercase;">Physical Interfaces:</span>
      ${interfacesHtml}
    </div>
    
    <div style="margin-top:12px; display:flex; flex-direction:column;">
      <span class="details-label" style="font-size:11px; font-weight:600; text-transform:uppercase;">Generated Cisco IOS Config:</span>
      <textarea id="router-config-view" readonly>Loading config...</textarea>
    </div>
  `;

  // Fetch Startup-config content for this router
  try {
    const res = await fetch(`${API_BASE}/api/config?router=${node.name}`);
    const data = await res.json();
    const configTextarea = document.getElementById("router-config-view");
    if (configTextarea) {
      if (res.ok) {
        configTextarea.value = data.config;
      } else {
        configTextarea.value = `[ERROR] ${data.error}`;
      }
    }
  } catch (err) {
    const configTextarea = document.getElementById("router-config-view");
    if (configTextarea) {
      configTextarea.value = `Failed to load configuration: ${err.message}`;
    }
  }
}

// Copy Cisco IOS Config to Clipboard
function copyConfigToClipboard() {
  const configTextarea = document.getElementById("router-config-view");
  if (configTextarea && configTextarea.value) {
    navigator.clipboard.writeText(configTextarea.value);
    const origText = copyConfigBtn.textContent;
    copyConfigBtn.textContent = "Copied!";
    setTimeout(() => {
      copyConfigBtn.textContent = origText;
    }, 1500);
  }
}

// Trigger Config Generation API
async function generateConfigs() {
  try {
    appendLog("Triggering configuration generation...");
    const res = await fetch(`${API_BASE}/api/generate`, { method: "POST" });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    
    appendLog(`Generation complete. Generated configs for ${data.count} routers.`, "success");
    if (activeNode) {
      // Refresh current node inspection config
      const node = globalTopology[activeNode];
      if (node) inspectNode(node);
    }
  } catch (err) {
    appendLog(`Generation failed: ${err.message}`, "error");
  }
}

// Trigger GNS3 API Deployment with Real-time Polling Progress
async function deployTopology() {
  if (isDeploying) return;
  
  try {
    appendLog("Initiating deployment on GNS3 server...", "warning");
    isDeploying = true;
    deployBtn.disabled = true;
    deployBtn.style.opacity = "0.5";
    
    // Toggle Panels: Hide inspector, Show Stepper
    document.getElementById("node-inspector").style.display = "none";
    document.getElementById("deployment-progress-card").style.display = "block";
    
    const res = await fetch(`${API_BASE}/api/deploy`, { method: "POST" });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    
    if (data.success) {
      appendLog("Deployment process spawned in background. Polling server...", "info");
      lastLogCount = 0;
      // Start short-polling status
      deployPollInterval = setInterval(pollDeploymentStatus, 1000);
    } else {
      throw new Error(data.error || "Failed to launch deployment");
    }
  } catch (err) {
    appendLog(`Deployment start failed: ${err.message}`, "error");
    resetDeployUI();
  }
}

async function pollDeploymentStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/deploy/status`);
    if (!res.ok) throw new Error("Failed to communicate with API server");
    const statusData = await res.json();
    
    // 1. Update visual stepper
    renderStepper(statusData.steps);
    
    // 2. Append new log lines to terminal
    renderLogs(statusData.logs);
    
    // 3. Evaluate completion status
    if (statusData.status === "success") {
      appendLog("Deployment completed successfully!", "success");
      resetDeployUI();
      checkGNS3Status();
    } else if (statusData.status === "error") {
      appendLog(`Deployment failed: ${statusData.error_message}`, "error");
      resetDeployUI();
      checkGNS3Status();
    }
  } catch (err) {
    appendLog(`Status query error: ${err.message}`, "error");
  }
}

function renderStepper(steps) {
  const stepperList = document.getElementById("stepper-list");
  stepperList.innerHTML = "";
  
  steps.forEach((step, idx) => {
    const stepEl = document.createElement("div");
    stepEl.className = `step ${step.status}`;
    
    let iconContent = "";
    if (step.status === "completed") {
      iconContent = "✔";
    } else if (step.status === "failed") {
      iconContent = "✖";
    } else if (step.status === "running") {
      iconContent = "⠋";
    } else {
      iconContent = idx + 1;
    }
    
    stepEl.innerHTML = `
      <div class="step-icon">${iconContent}</div>
      <div class="step-name">${step.name}</div>
    `;
    stepperList.appendChild(stepEl);
  });
}

function renderLogs(logs) {
  if (logs.length === lastLogCount) return;
  
  consoleLog.innerHTML = "";
  logs.forEach(log => {
    const line = document.createElement("div");
    line.className = `log-line-${log.level || 'info'}`;
    line.textContent = `[${log.time}] ${log.message}`;
    consoleLog.appendChild(line);
  });
  consoleLog.scrollTop = consoleLog.scrollHeight;
  lastLogCount = logs.length;
}

function resetDeployUI() {
  isDeploying = false;
  deployBtn.disabled = false;
  deployBtn.style.opacity = "1";
  if (deployPollInterval) {
    clearInterval(deployPollInterval);
    deployPollInterval = null;
  }
  
  // Restore panels: Show inspector, Hide Stepper (with small delay for user reading)
  setTimeout(() => {
    if (!isDeploying) {
      document.getElementById("node-inspector").style.display = "block";
      document.getElementById("deployment-progress-card").style.display = "none";
    }
  }, 5000);
}
