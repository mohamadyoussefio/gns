# GNS3 Network Automation - Video Presentation Test Checklist

Use this structured test list as a script and visual guide during your video presentation to demonstrate the complete, successful operation of your automated multi-AS network topology.

---

## Phase 1: GUI Web Console Demonstration (2 Minutes)

* **Objective**: Show the automated intent parser, retro styling, and inspector capabilities.
* **Steps**:
  1. Open a browser and load **`http://localhost:8080`**.
  2. Point out the **Retro Monochrome Design** (IBM Plex Mono typography, sharp corners, solid shadows).
  3. Show the **Maximize Button**: Click **`[Maximize]`** on the Topology Canvas panel header to expand the network map full-screen, showing the colorized schematic SVG:
     * Blue nodes/links represent RIP (AS 100).
     * Purple nodes/links represent OSPF (AS 200).
     * Red dashed lines represent eBGP boundary links.
  4. Click **`[Restore]`** to show the sidebars again.
  5. Select a router (e.g., **`R6`** or **`R10`**) from the topology diagram:
     * Show that the right **Operations Control Panel** dynamically loads its loopback IP, active physical interfaces, neighbor nodes, and the fully-generated **Cisco IOS startup-config**.

---

## Phase 2: IGP Domain Verification (2 Minutes)

* **Objective**: Verify RIP (AS X) and OSPF (AS Y) are functioning correctly and that loopbacks are routable within each domain.
* **Commands to run**:
  
  ### Test AS X (RIP Domain)
  Double-click **`R1`** in the GNS3 GUI to open its terminal console. Run:
  ```ios
  R1# show ip route rip
  ```
  * **What to highlight**: Point out that RIP has dynamically learned the loopback addresses of all other routers in AS 100 (`10.1.100.2/32` through `10.1.100.7/32`) and the inter-AS link subnets (`10.254.0.0/30` and `10.254.0.4/30`).
  
  ### Test AS Y (OSPF Domain)
  Double-click **`R10`** in the GNS3 GUI to open its terminal console. Run:
  ```ios
  R10# show ip OSPF neighbor
  R10# show ip route ospf
  ```
  * **What to highlight**: Show that OSPF neighbor adjacencies are in the `FULL` state. Point out that the routing table has learned all loopbacks in AS 200 (`10.2.100.8/32` through `10.2.100.14/32`). Highlight the customized OSPF path costs (e.g., metric adjustments matching `intent.json` configurations).

---

## Phase 3: BGP Peerings & Relationship Policies (3 Minutes)

* **Objective**: Prove BGP is peering correctly and enforcing business relationships.
* **Commands to run**:

  ### Verify Peer Status on Border Router R6
  Open the console for **`R6`** (AS 100 border router) and run:
  ```ios
  R6# show ip bgp summary
  ```
  * **What to highlight**: Show that iBGP neighbors (using loopback IPs `10.1.100.X`) are fully established (`Up/Down` column). Show that the eBGP neighbor session with **`10.254.0.2`** (R8 in AS 200) is established and receiving **`7` prefixes**.

  ### Verify Peering Policies & Communities
  Open the console for **`R1`** (AS 100 internal router) and query the BGP table for R14's loopback:
  ```ios
  R1# show ip bgp 10.2.100.14
  ```
  * **What to highlight**: Show that the route carries the community tag **`100:200`** (AS 100 Peer tag) and has a **Local Preference of `200`** applied by the border router on import, matching the Peer relationship defined in the intent config.

  ### Verify Transit-Free Behavior
  On **`R6`**, show what is advertised to R8:
  ```ios
  R6# show ip bgp neighbor 10.254.0.2 advertised-routes
  ```
  * **What to highlight**: Show that R6 only advertises local AS 100 prefixes (`Total number of prefixes 7`). It does *not* leak peer or provider routes, validating the BGP export route-maps.

---

## Phase 4: End-to-End Connectivity (1 Minute)

* **Objective**: Prove end-to-end connectivity across RIP, BGP, and OSPF boundaries.
* **Commands to run**:
  
  ### Ping from RIP Loopback to OSPF Loopback
  Open the console for **`R1`** and ping R14's loopback interface:
  ```ios
  R1# ping 10.2.100.14 source Loopback0
  ```
  * **What to highlight**: Point out the **100% success rate (5/5)**, verifying that routing tables are fully synchronized across RIP, BGP, and OSPF boundaries.

  ### Reverse Ping
  Open the console for **`R14`** and ping R1's loopback:
  ```ios
  R14# ping 10.1.100.1 source Loopback0
  ```
  * **What to highlight**: Another **100% success rate (5/5)**, confirming bidirectional data plane functionality.
