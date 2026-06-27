# Network Automation Engine (GNS3 & Cisco IOS)

This repository contains a Python-based network automation solution to set up, address, configure, and deploy a symmetrical multi-AS Cisco IOS network topology in GNS3. Using a JSON intent file, the engine automates IP address allocation, generates Cisco IOS startup configuration files, places routers on the grid, connects interfaces, and deploys the project via the GNS3 REST API.

It features a **retro monochrome** web dashboard with a clean light-mode CRT visual theme, interactive network schematics, collapsible sidebars, and real-time status indicators.

---

## Features

* **Automated IP Subnetting**: Divides classless blocks into `/30` point-to-point subnets for physical connections, and allocates `/32` host loopbacks from dedicated AS ranges.
* **Jinja2 Configuration Engine**: Renders clean, production-ready Cisco IOS configs including interface bindings, RIPv2 (AS X), OSPFv2 (AS Y), and a full-mesh iBGP peering core.
* **BGP Transit-Free Peering Policies**: Implements BGP communities and Local Preference tags to enforce Customer, Provider, and Peer relationships. Empty AS-path matching (`^$`) enables advertisement of locally originated AS loopbacks across boundaries.
* **GNS3 REST API Deployer**: Wipes active canvas workspaces, places Dynamips node templates symmetrically, wires link interfaces, pushes startup configs, and powers on the network.
* **Retro Monochrome Web GUI**: A stark monochrome control panel featuring:
  * Collapsible layout with a **[Maximize]** canvas mode.
  * SVG wireframe map representing RIP (AS 100, blue) and OSPF (AS 200, purple) routing protocols.
  * Node configuration inspector, interactive addressing directory, and real-time operational logging.

---

## Project Structure

```text
gns/
├── Makefile                         # Automation targets (install, generate, deploy, server, clean)
├── main.py                          # CLI automation runner
├── server.py                        # Backend web server and status endpoints
├── requirements.txt                  # Python dependencies (requests, jinja2)
├── README.md                        # Documentation
├── GNS3_Project_Specification_and_Plan.md # Engineering design and specifications
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
