# Network Automation Engine (GNS3 & Cisco IOS)

This repository contains a Python-based network automation solution designed to automatically plan, address, generate configurations for, and deploy a symmetrical multi-AS Cisco IOS network topology in GNS3. Using a JSON-based network intent definition, the engine automates IP address allocation, compiles Cisco IOS startup configuration files, places routers on the GNS3 canvas according to coordinate properties, wires physical adapters, and boots the entire topology via the GNS3 REST API.

The project features a **retro monochrome** web dashboard with a clean, classic light-mode CRT visual theme. The dashboard provides an interactive network schematic, collapsible sidebars, a JSON intent editor, real-time status logging, and a router configuration inspector.

---

## Interactive Web Dashboard

The web dashboard (served by [server.py](file:///Users/mohamadyoussef/src/gns/server.py)) is designed to give you a full visual management panel for your automated network:
* **Interactive SVG Topology Canvas**: Renders the network topology live as interactive SVG lines. Links are color-coded:
  * **Blue links**: RIPv2 domain (AS 100)
  * **Purple links**: OSPFv2 domain (AS 200)
  * **Red dashed links**: External eBGP connections between Autonomous Systems
* **Full-Screen Maximize**: Click the **`[Maximize]`** button to expand the canvas across your screen for easier inspection, and **`[Restore]`** to show the sidebars again.
* **Intent Editor**: A built-in code editor that lets you view, edit, and save [intent.json](file:///Users/mohamadyoussef/src/gns/config/intent.json) directly from your browser.
* **Node Inspector**: Click any router in the topology diagram to load its IP addressing plan, active physical interfaces, neighbor nodes, and the fully generated **Cisco IOS startup-config**.
* **Deploy Console**: Trigger deployment and watch the step-by-step automation logs stream in real-time.

---

## Key Features

### 1. Auto IP Address Planner & Subnet Allocator
Implemented in [allocator.py](file:///Users/mohamadyoussef/src/gns/src/allocator.py), the subnet allocator:
* Allocates unique `/32` loopback IP addresses for all routers based on their assigned `loopback_id`.
* Automatically carves up the main AS physical network prefixes (e.g., `10.1.0.0/16` and `10.2.0.0/16`) into `/30` subnets for router-to-router point-to-point links.
* Automatically resolves and assigns IP addresses to interfaces on inter-AS links using the subnets specified under `inter_as_links`.
* Sets customized OSPF interface costs if specific cost mappings are defined in the intent configuration.

### 2. Cisco IOS Configuration Generator
Using Jinja2 templates ([cisco_ios.j2](file:///Users/mohamadyoussef/src/gns/templates/cisco_ios.j2)) and the generator class ([generator.py](file:///Users/mohamadyoussef/src/gns/src/generator.py)), the engine compiles ready-to-run startup configuration files for each router:
* **Base Settings**: Disables DNS lookup, enables IP routing, configures Cisco Express Forwarding (CEF), sets synchronous logging, and configures no execution timeouts on Console lines.
* **RIPv2 Routing (AS 100 / AS X)**: Configures version 2, disables auto-summary, advertises the classful block, and marks all non-RIP interfaces (such as loopbacks and eBGP links) as `passive-interface` to prevent security leaks.
* **OSPFv2 Routing (AS 200 / AS Y)**: Configures OSPF process ID `1`, sets the BGP router-id to the router's loopback IP, adds network ranges to Area 0, and adjusts the OSPF interface cost where specified in the intent file.
* **BGP Routing & Peering Policies**:
  * **iBGP Mesh**: Builds a full mesh of internal BGP connections between all routers in the same AS, peering via Loopback0 interfaces using `update-source Loopback0` and enabling community propagation via `send-community`.
  * **Border Router Next-Hop-Self**: Border routers automatically modify the BGP next-hop attribute to themselves (`next-hop-self`) when advertising external prefixes to internal iBGP neighbors.
  * **eBGP Sessions**: Establishes point-to-point peerings on inter-AS boundary links using physical interface IPs.

### 3. Relationship Routing Policies (BGP Communities)
To control route propagation and enforce business agreements across the AS boundary, the engine configures granular BGP policy route-maps on border routers:
* **Community Tagging on Import**: Advertisements received from external neighbors are tagged with additive communities depending on the peering relationship configured:
  * **Customer**: Tagged with `AS:300` and assigned a **Local Preference of 300** (highest priority).
  * **Peer**: Tagged with `AS:200` and assigned a **Local Preference of 200**.
  * **Provider**: Tagged with `AS:100` and assigned a **Local Preference of 100** (lowest priority).
* **Transit-Free Export Filtering**:
  * Outbound traffic to customers receives all routes.
  * Outbound advertisements to peers and providers are restricted. They **only** advertise local prefixes and routes learned from customers (identified by matching community list tag `AS:300`). They do not transit traffic between two providers or peers.
  * Uses an empty AS-path filter (`^$`) to ensure that border routers only advertise prefixes originated within their own AS.

### 4. Automated GNS3 API Deployer
The client wrapper [gns3_client.py](file:///Users/mohamadyoussef/src/gns/src/gns3_client.py) communicates with the GNS3 server REST API:
* **Automatic Server Launch**: If the server is offline, it will attempt to spawn the GNS3 application (on macOS) and poll the API until it initializes.
* **Canvas Reset**: Wipes out existing nodes and links in the selected project to build the topology from a clean state.
* **Dynamic Node Creation & Coordinates Grid**: Instantiates Dynamips Cisco 7200 routers, applies custom SVG router icons, and places them at the precise X/Y pixel coordinates defined in [intent.json](file:///Users/mohamadyoussef/src/gns/config/intent.json) to form a neat, symmetrical layout.
* **Automated Interface Wiring**: Parses interface names (e.g. `FastEthernet1/0` is adapter 1, port 0) and makes HTTP POST requests to GNS3 to connect the correct physical adapter slots.
* **Startup Config Upload**: Direct-copies config contents into GNS3 project files or uploads them via GNS3's file API so that routers load the generated configs upon boot.
* **Synchronized Startup**: Powers on all routers, writes the project state, and saves it.

---

## Project Structure

```text
gns/
├── Makefile                          # Automation commands (install, generate, deploy, server, clean)
├── main.py                           # CLI automation runner (IP allocator, config writer, and GNS3 pusher)
├── server.py                         # Backend web server (HTTP and API JSON endpoints)
├── requirements.txt                   # Python packages required (requests, jinja2)
├── README.md                         # Detailed project documentation (this file)
├── presentation_test_list.md          # Verification steps checklist for testing the live setup
│
├── config/
│   └── intent.json                   # Network design specification file (topology, IPs, links, rules)
│
├── gui/                              # Web Interface resources
│   ├── index.html                    # Web control center layout
│   ├── style.css                     # Stylesheet
│   └── app.js                        # Topology SVG drawing, interactive polling, and node selection logic
│
├── src/                              # Core Python module scripts
│   ├── parser.py                     # Schema validation and verification for intent.json
│   ├── allocator.py                  # Computes subnets (/30) and loopback addresses (/32)
│   ├── generator.py                  # Jinja2 environment manager that renders router configuration templates
│   ├── gns3_client.py                # Wrapper that makes REST requests to GNS3 API
│   └── console.py                    # Terminal outputs, colors, and console status spinners
│
└── templates/
    └── cisco_ios.j2                  # Cisco IOS startup-config Jinja2 template
```

---

## Getting Started & Setup

### Prerequisites
1. **GNS3 Software**: Install GNS3 on your local machine.
2. **Cisco 7200 Router Image**: Configure a template in GNS3 named exactly **`Cisco 7200 152-4.S5`** (or change `"router_template"` in [intent.json](file:///Users/mohamadyoussef/src/gns/config/intent.json) to match your local template name).
3. **Physical Interface Adapter Slots**:
   Ensure that the Cisco 7200 template has the correct network adapters configured:
   * **Slot 0**: `C7200-IO-FE` (provides `FastEthernet0/0`)
   * **Slot 1**: `PA-2FE-TX` (provides `FastEthernet1/0` and `FastEthernet1/1`)
   * **Slot 2**: `PA-2FE-TX` (provides `FastEthernet2/0` and `FastEthernet2/1`)
4. **Python 3**: Ensure Python 3.x is installed.

### Setup and Automation Commands
A [Makefile](file:///Users/mohamadyoussef/src/gns/Makefile) simplifies all management operations:

#### 1. Install Dependencies
Install all required libraries (`requests`, `jinja2`):
```bash
make install
```

#### 2. Local Configuration Generation (Dry-Run / Offline Mode)
Validate [intent.json](file:///Users/mohamadyoussef/src/gns/config/intent.json) and compile all Cisco IOS configurations locally inside `generated_configs/` without sending anything to GNS3:
```bash
make generate
```

#### 3. Deploy Network Topology to GNS3
Clear the GNS3 project canvas, rebuild the node network structure, establish links, write startup configurations, and boot all routers:
```bash
make deploy
```
*Note: Make sure your GNS3 application is running and the REST API is enabled on port 3080.*

#### 4. Launch the Web Console Dashboard
Run the HTTP and REST API backend server to view logs and control configuration adjustments from a web browser:
```bash
make server
```
Once the server is running, navigate to **[http://localhost:8080](http://localhost:8080)**.

#### 5. Reset and Cleanup
Delete all compiled configuration files inside `generated_configs/`:
```bash
make clean
```

---

## Intent Configuration Schema (`intent.json`)

The entire network design, coordinate placement, link connections, IP blocks, and routing policies are configured in [intent.json](file:///Users/mohamadyoussef/src/gns/config/intent.json). 

Below is an overview of the key configuration sections:

### `gns3`
```json
"gns3": {
  "server_url": "http://localhost:3080",
  "project_name": "Network_Automation_Project",
  "router_template": "Cisco 7200 152-4.S5",
  "node_symbol": ":/symbols/classic/router.svg",
  "autostart": true
}
```
Defines connection settings, project naming, and node templates on the GNS3 server.

### `ip_allocation`
```json
"ip_allocation": {
  "strategy": "automated",
  "as_networks": {
    "100": {
      "physical_range": "10.1.0.0/16",
      "loopback_range": "10.1.100.0/24"
    },
    "200": {
      "physical_range": "10.2.0.0/16",
      "loopback_range": "10.2.100.0/24"
    }
  },
  "inter_as_links": [
    { "routers": ["R6", "R8"], "subnet": "10.254.0.0/30" },
    { "routers": ["R7", "R9"], "subnet": "10.254.0.4/30" }
  ]
}
```
Instructs the engine on which IP prefix blocks are available for each AS. The engine dynamically carves `/30` subnets out of these blocks for intra-AS links, and `/32` subnet blocks for loopbacks.

### `routers`
```json
"routers": {
  "R1": { "as": 100, "loopback_id": 1, "coordinates": { "x": -500, "y": 0 } },
  "R2": { "as": 100, "loopback_id": 2, "coordinates": { "x": -360, "y": -90 } }
}
```
Maps each router to its respective Autonomous System, loops ID (for loopback IP creation), and absolute X/Y grid coordinates for canvas placement.

### `links`
```json
"links": [
  {
    "nodes": ["R1", "R2"],
    "interfaces": ["FastEthernet0/0", "FastEthernet0/0"]
  }
]
```
Wires physical interface connections. Make sure that the selected interfaces match the slots configured on the router template.

### `protocols`
```json
"protocols": {
  "igp": {
    "100": { "type": "rip" },
    "200": { "type": "ospf", "ospf_process_id": 1 }
  },
  "ospf_costs": [
    { "nodes": ["R9", "R11"], "cost": 50 }
  ],
  "bgp": {
    "100": { "peers": { "200": { "relationship": "peer", "remote_as": 200 } } },
    "200": { "peers": { "100": { "relationship": "peer", "remote_as": 100 } } }
  }
}
```
Maps IGPs (RIP for AS 100, OSPF for AS 200), specifies path cost overrides for OSPF links, and outlines the BGP peering policy relationships.

---

## Verification & Troubleshooting Guide

Once you run `make deploy`, check that the routers boot up in GNS3. You can verify that all protocols converged correctly by opening a Telnet session to the console of any router (or using the console interface inside GNS3).

For complete testing details, refer to the [presentation_test_list.md](file:///Users/mohamadyoussef/src/gns/presentation_test_list.md).

### 1. Verify RIP Routing (AS 100 / AS X)
On internal router **R1**, check the RIP routing table:
```ios
R1# show ip route rip
```
*   **Expected Behavior**: You should see RIP routes learned dynamically for loopbacks of all routers in AS 100 (`10.1.100.2/32` through `10.1.100.7/32`), and point-to-point subnets.

### 2. Verify OSPF Adjacency & Routing (AS 200 / AS Y)
On router **R10**, verify OSPF neighbors are up and routing table has updated:
```ios
R10# show ip ospf neighbor
R10# show ip route ospf
```
*   **Expected Behavior**: Neighbor status should show `FULL` state for adjacent routers. The routing table should contain routes for loopbacks `10.2.100.8/32` through `10.2.100.14/32`.
*   **OSPF Cost Verification**: Run `show ip route 10.2.100.11` to confirm that metric weights adjust according to your OSPF cost rule adjustments (like path R9-R11 setting a metric cost of 50).

### 3. Verify BGP Neighbor Status
On border router **R6**, check BGP state summaries:
```ios
R6# show ip bgp summary
```
*   **Expected Behavior**:
    *   Internal neighbors (routers R1–R5, R7) should list their states as established (indicated by showing a prefix count number in the final column, e.g. `7`).
    *   The external peer (eBGP neighbor `10.254.0.2` on R8) should show established status with a active exchange of prefixes.

### 4. Verify Peering Policies & Community Tags
On internal router **R1**, inspect how R14's loopback route is received:
```ios
R1# show ip bgp 10.2.100.14
```
*   **Expected Behavior**: The output must show that the route carries the community tag `100:200` (representing BGP peer tag for AS 100) and has a **Local Preference of 200**, enforcing the BGP policy defined in `intent.json`.

### 5. Verify Transit-Free Behavior (Export Restrictions)
On border router **R6**, review what routing prefixes are advertised to R8 (`10.254.0.2`):
```ios
R6# show ip bgp neighbor 10.254.0.2 advertised-routes
```
*   **Expected Behavior**: R6 should **only** advertise local AS 100 prefixes (normally 7 prefixes representing AS 100 loopbacks). It must not advertise routes learned from other external peers or providers to R8, demonstrating the transit-free route filtering policy.

### 6. Test Data-Plane End-to-End Connectivity
Verify connectivity across the RIP, BGP, and OSPF boundaries by pinging from AS 100's R1 loopback to AS 200's R14 loopback:
```ios
R1# ping 10.2.100.14 source Loopback0
```
*   **Expected Behavior**: The ping must succeed with a 100% success rate (`!!!!!`).

Run a traceroute from R1 to R14 sourcing from Loopback0:
```ios
R1# traceroute 10.2.100.14 source Loopback0 numeric
```
*   **Expected Behavior**: The trace should list hops path traversing internal AS 100 RIP routers (`10.1.0.x`), cross the eBGP point-to-point boundary (`10.254.0.2`), and continue through AS 200 OSPF routers (`10.2.0.x`) until reaching R14 (`10.2.100.14`).

---

## Technologies Used
* **Backend**: Python 3, Jinja2 (Cisco IOS templating), `requests` (REST API client)
* **Frontend**: HTML5, Vanilla CSS3 (Retro terminal layout theme), JavaScript (dynamic SVG topology mapping and live AJAX polling)
* **Emulation Environment**: GNS3 Server REST API, Cisco 7200 Dynamips routers running Cisco IOS 15.2
