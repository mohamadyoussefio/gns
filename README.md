# Network Automation Engine (GNS3 & Cisco IOS)

This repository contains a Python-based network automation solution to set up, address, configure, and deploy a symmetrical multi-AS Cisco IOS network topology in GNS3. Using a JSON intent file, the engine automates IP address allocation, generates Cisco IOS startup configuration files, places routers on the grid, connects interfaces, and deploys the project via the GNS3 REST API.

It features a **retro monochrome** web dashboard with a clean light-mode CRT visual theme, interactive network schematics, collapsible sidebars, and real-time status indicators.

---

## Features

* **Auto IP Address Planner**: We wrote a Python script that calculates all the IP subnets automatically. It splits the main AS ranges into `/30` subnets for the router-to-router links, and assigns `/32` loopback IPs to each router so we don't have to do it by hand.
* **Cisco IOS Config Generator**: Uses Jinja2 templates to generate `.cfg` startup files. It automatically sets up hostnames, IP interfaces, OSPF (for AS Y/AS 200), RIPv2 (for AS X/AS 100), and creates a full mesh of iBGP connections inside both ASs.
* **BGP Policy Tagging**: Implements routing policies for different BGP relationships (like customer, peer, or provider). It tags routes with BGP communities and sets local preferences. It also uses empty AS-path filters (`^$`) so border routers actually advertise their own AS loopbacks.
* **Automatic GNS3 Deployment**: Integrates with the GNS3 REST API. It connects to the local GNS3 server, cleans up the canvas, places the Cisco 7200 routers using X/Y coordinates, wires up all the links, uploads the generated configurations, and starts all the nodes.
* **Web Dashboard**: A control panel built with standard HTML/CSS/JS. It lets you:
  * Click a **`[Maximize]`** button to make the topology map full-screen.
  * See the network topology rendered as colored SVG lines (blue for RIP, purple for OSPF, red for eBGP).
  * Click on any router to inspect its interface IP addresses and read its generated startup configuration.

---

## Project Structure

```text
gns/
├── Makefile                         # Automation targets (install, generate, deploy, server, clean)
├── main.py                          # CLI automation runner
├── server.py                        # Backend web server and status endpoints
├── requirements.txt                  # Python dependencies (requests, jinja2)
├── README.md                        # Documentation
├── GNS3_Project_Specification_and_Plan.md # Professir Pdf
│
├── config/
│   └── intent.json                  # JSON-based network intent specification
│
├── gui/                             # Web Interface assets
│   ├── index.html                   # Console layout structure
│   ├── style.css                    # Retro monochrome stylesheet
│   └── app.js                       # SVG topology rendering and polling logic
│
├── src/                             # Core automation engine
│   ├── parser.py                    # Schema validation and parsing
│   ├── allocator.py                 # IP subnet allocator
│   ├── generator.py                 # Jinja2 configuration compiler
│   ├── gns3_client.py               # GNS3 REST API connection wrapper
│   └── console.py                   # Terminal styling and logger utilities
│
└── templates/
    └── cisco_ios.j2                 # Cisco IOS startup-config template
```

---

## Getting Started

A `Makefile` is included to simplify setup and operations:

### 1. Installation
Install python dependencies:
```bash
make install
```

### 2. Local Configuration Generation
Validate the intent file and generate startup-configs locally inside `generated_configs/` (offline mode):
```bash
make generate
```

### 3. Deploy to GNS3
Wipe the active GNS3 canvas, rebuild the topology, wire links, push configurations, and power on all routers:
```bash
make deploy
```

### 4. Start the Web Console
Run the backend web server to manage the deployment and view the topology via your browser:
```bash
make server
```
Once started, navigate to **[http://localhost:8080](http://localhost:8080)**.

### 5. Cleanup
Delete generated configuration files:
```bash
make clean
```

---

## Intent Configuration (`intent.json`)

The network's physical layout, templates, IP blocks, and routing domains are defined in `config/intent.json`. 

> [!IMPORTANT]
> **Port Mappings**: Cisco 7200 templates must have physical interfaces mapped to correct slots.
> * Slot 0 (`C7200-IO-FE`): FastEthernet0/0
> * Slot 1 (`PA-2FE-TX`): FastEthernet1/0, FastEthernet1/1
> * Slot 2 (`PA-2FE-TX`): FastEthernet2/0, FastEthernet2/1
> 
> *Note: In the R2 <---> R3 link, `R2` connects via `FastEthernet1/0` (not `FastEthernet0/0` which is reserved for R1) to avoid interface conflicts.*

---

## Verification Procedures

Log in to any router console inside GNS3 (e.g. `telnet localhost 5001` for R1) to verify:

### 1. Check Routing Tables
Verify that RIP (AS 100) or OSPF (AS 200) loopback routes have converged:
```ios
R1# show ip route rip
R10# show ip route ospf
```

### 2. Verify BGP Neighbor Status
Verify that internal iBGP and external eBGP peerings are active:
```ios
R6# show ip bgp summary
```

### 3. Check Route Advertisement & Policies
Verify that loopbacks are advertised across AS boundaries and carry the correct relationship communities (e.g., Peer = `100:200` with local-preference `200`):
```ios
R1# show ip bgp 10.2.100.14
```

### 4. Test Connectivity
Confirm end-to-end reachability by pinging across the AS boundary, sourcing from Loopback0:
```ios
R1# ping 10.2.100.14 source Loopback0
```
Pings must complete with a 100% success rate.
