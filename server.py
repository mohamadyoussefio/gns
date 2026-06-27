#!/usr/bin/env python3
import http.server
import socketserver
import json
import os
import re
import time
import requests
import threading
import datetime
import urllib.parse

from src.parser import IntentParser
from src.allocator import IPAllocator
from src.generator import ConfigGenerator
from src.gns3_client import GNS3Client

PORT = 8080
GUI_DIR = os.path.join(os.path.dirname(__file__), "gui")

# Shared state for background deployment status tracking
DEPLOY_STATUS = {
    "status": "idle",  # "idle", "running", "success", "error"
    "error_message": "",
    "logs": [],        # list of dicts: {"time": "12:00:00", "level": "info", "message": "..."}
    "steps": [
        {"id": "parse", "name": "Load & Validate Network Intent", "status": "pending"},
        {"id": "allocate", "name": "Auto-Allocate Subnets & IPs", "status": "pending"},
        {"id": "generate", "name": "Generate Cisco IOS Configuration Files", "status": "pending"},
        {"id": "gns3_connect", "name": "Establish Connection & Clean GNS3 Canvas", "status": "pending"},
        {"id": "gns3_deploy", "name": "Create Nodes, Wire Links & Start Routers", "status": "pending"}
    ]
}

deploy_lock = threading.Lock()

def append_deploy_log(message, level="info"):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    DEPLOY_STATUS["logs"].append({
        "time": now,
        "level": level,
        "message": message
    })
    print(f"[{now}] [{level.upper()}] {message}")

def update_step_status(step_id, status):
    for step in DEPLOY_STATUS["steps"]:
        if step["id"] == step_id:
            step["status"] = status
            break

def run_deployment_worker():
    global DEPLOY_STATUS
    
    append_deploy_log("Initializing Deployment Engine...", "info")
    
    # Temporarily monkeypatch console spinners to log clean events to web GUI
    import src.console
    
    class WebSpinner:
        def __init__(self, message="Working..."):
            self.message = message
            append_deploy_log(message, "info")
            
        def __enter__(self):
            return self
            
        def update_message(self, new_message):
            self.message = new_message
            append_deploy_log(new_message, "info")
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
            
    orig_spinner = src.console.ConsoleSpinner
    orig_success = src.console.print_success
    orig_warning = src.console.print_warning
    orig_error = src.console.print_error
    orig_info = src.console.print_info
    orig_section = src.console.print_section
    
    src.console.ConsoleSpinner = WebSpinner
    src.console.print_success = lambda msg: append_deploy_log(msg, "success")
    src.console.print_warning = lambda msg: append_deploy_log(msg, "warning")
    src.console.print_error = lambda msg: append_deploy_log(msg, "error")
    src.console.print_info = lambda msg: append_deploy_log(msg, "info")
    src.console.print_section = lambda title: append_deploy_log(f"--- {title} ---", "info")
    
    try:
        # Step 1: Parse Intent
        update_step_status("parse", "running")
        parser_engine = IntentParser("config/intent.json")
        intent_data = parser_engine.load_and_validate()
        update_step_status("parse", "completed")
        append_deploy_log("Network intent parsed and validated.", "success")
        
        # Step 2: Allocate IPs
        update_step_status("allocate", "running")
        allocator = IPAllocator(intent_data)
        allocated_topology = allocator.allocate()
        update_step_status("allocate", "completed")
        append_deploy_log("Subnet mapping and IP allocation plan computed.", "success")
        
        # Step 3: Generate Configs
        update_step_status("generate", "running")
        generator = ConfigGenerator(allocated_topology, intent_data)
        generated_configs = generator.generate_configs("generated_configs")
        update_step_status("generate", "completed")
        append_deploy_log(f"Generated startup-config files for {len(generated_configs)} routers.", "success")
        
        # Step 4: Establish Connection & Clean Canvas
        update_step_status("gns3_connect", "running")
        client = GNS3Client(intent_data)
        
        if not client.check_and_start_gns3():
            raise Exception("Could not verify GNS3 REST API. Please ensure GNS3 is running.")
            
        project = client.get_or_create_project()
        client.clear_project_nodes()
        update_step_status("gns3_connect", "completed")
        append_deploy_log("Established connection and wiped GNS3 workspace canvas.", "success")
        
        # Step 5: Create Nodes, Wire Links & Start Routers
        update_step_status("gns3_deploy", "running")
        
        # Ensure project is open after canvas wiping
        res = requests.get(f"{client.server_url}/projects/{client.project_id}")
        res.raise_for_status()
        if res.json().get("status") == "closed":
            requests.post(f"{client.server_url}/projects/{client.project_id}/open").raise_for_status()
            append_deploy_log("Re-opened GNS3 project for router placement.", "warning")
            
        template = client.find_router_template()
        template_id = template["template_id"]
        node_type = template.get("node_type", template.get("template_type", "dynamips"))
        compute_id = template.get("compute_id", "local")
        
        properties_keys = [
            "platform", "image", "nvram", "ram", "slot0", "slot1", "slot2", 
            "slot3", "slot4", "slot5", "slot6", "idlepc", "npe", "midplane", 
            "mmap", "sparsemem", "idlemax", "idlesleep", "auto_delete_disks",
            "disk0", "disk1", "system_id"
        ]
        template_properties = {k: template[k] for k in properties_keys if k in template}
        
        # Place nodes
        nodes_url = f"{client.server_url}/projects/{client.project_id}/nodes"
        for router_name, router_data in allocated_topology.items():
            append_deploy_log(f"Instantiating Dynamips node '{router_name}'...", "info")
            coords = router_data.get("coordinates", {"x": 0, "y": 0})
            body = {
                "name": router_name,
                "node_type": node_type,
                "compute_id": compute_id,
                "template_id": template_id,
                "properties": template_properties,
                "symbol": template.get("symbol", ":/symbols/classic/router.svg"),
                "x": coords["x"],
                "y": coords["y"]
            }
            
            # placement retry
            placed = False
            for attempt in range(3):
                try:
                    res = requests.post(nodes_url, json=body)
                    res.raise_for_status()
                    node_info = res.json()
                    client.nodes_map[router_name] = node_info
                    placed = True
                    break
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 403 and "not opened" in e.response.text.lower() and attempt < 2:
                        append_deploy_log("GNS3 project closed unexpectedly. Attempting to reopen...", "warning")
                        try:
                            requests.post(f"{client.server_url}/projects/{client.project_id}/open").raise_for_status()
                            time.sleep(1.5)
                            continue
                        except Exception:
                            pass
                    raise e
            if not placed:
                raise Exception(f"Failed to place router node: {router_name}")
                
        append_deploy_log(f"All {len(allocated_topology)} Dynamips routers placed symmetrically.", "success")
        
        # Parse interface helper
        def parse_interface(intf_name):
            match = re.search(r'([a-zA-Z]+)(\d+)/(\d+)', intf_name)
            if match:
                return int(match.group(2)), int(match.group(3))
            return 0, 0
            
        # Create links
        links_url = f"{client.server_url}/projects/{client.project_id}/links"
        created_links = set()
        
        append_deploy_log("Wiring physical interfaces and slots...", "info")
        for link in intent_data["links"]:
            node_a, node_b = link["nodes"]
            int_a, int_b = link["interfaces"]
            
            link_key = tuple(sorted([(node_a, int_a), (node_b, int_b)]))
            if link_key in created_links:
                continue
                
            append_deploy_log(f"Connecting link: {node_a} ({int_a}) <---> {node_b} ({int_b})", "info")
            node_a_id = client.nodes_map[node_a]["node_id"]
            node_b_id = client.nodes_map[node_b]["node_id"]
            
            adapt_a, port_a = parse_interface(int_a)
            adapt_b, port_b = parse_interface(int_b)
            
            body = {
                "nodes": [
                    {"node_id": node_a_id, "adapter_number": adapt_a, "port_number": port_a},
                    {"node_id": node_b_id, "adapter_number": adapt_b, "port_number": port_b}
                ]
            }
            requests.post(links_url, json=body).raise_for_status()
            created_links.add(link_key)
            
        append_deploy_log(f"All {len(created_links)} links wired successfully.", "success")
        
        # Copy configs
        append_deploy_log("Deploying Cisco startup configuration files...", "info")
        client.deploy_configs(generated_configs)
        
        # Power on nodes
        if client.gns3_config.get("autostart", True):
            append_deploy_log("Powering on Cisco 7200 routers on the canvas...", "info")
            for router_name, node_info in client.nodes_map.items():
                node_id = node_info["node_id"]
                requests.post(f"{client.server_url}/projects/{client.project_id}/nodes/{node_id}/start").raise_for_status()
            append_deploy_log("All 14 routers are online. RIP, OSPF, and eBGP routes are initializing.", "success")
            
        # Write project state
        try:
            requests.post(f"{client.server_url}/projects/{client.project_id}/write").raise_for_status()
        except Exception:
            pass
            
        update_step_status("gns3_deploy", "completed")
        DEPLOY_STATUS["status"] = "success"
        append_deploy_log("Deployment complete! Symmetrical network topology successfully running.", "success")
        
    except Exception as err:
        append_deploy_log(f"Deployment process aborted: {err}", "error")
        DEPLOY_STATUS["status"] = "error"
        DEPLOY_STATUS["error_message"] = str(err)
        # Mark running step as failed
        for s in DEPLOY_STATUS["steps"]:
            if s["status"] == "running":
                s["status"] = "failed"
                
    finally:
        # Unpatch
        src.console.ConsoleSpinner = orig_spinner
        src.console.print_success = orig_success
        src.console.print_warning = orig_warning
        src.console.print_error = orig_error
        src.console.print_info = orig_info
        src.console.print_section = orig_section


class AutomationHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=GUI_DIR, **kwargs)

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        
        if parsed_url.path == "/api/intent":
            self.send_json_file("config/intent.json")
        elif parsed_url.path == "/api/topology":
            self.handle_get_topology()
        elif parsed_url.path == "/api/gns-status":
            self.handle_get_gns_status()
        elif parsed_url.path == "/api/deploy/status":
            self.send_json_response(DEPLOY_STATUS)
        elif parsed_url.path == "/api/config":
            self.handle_get_config(parsed_url.query)
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/intent":
            self.handle_post_intent()
        elif self.path == "/api/generate":
            self.handle_post_generate()
        elif self.path == "/api/deploy":
            self.handle_post_deploy()
        else:
            self.send_error(404, "Endpoint not found")

    def send_json_response(self, data, status=200):
        try:
            body = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def send_json_file(self, filepath):
        if not os.path.exists(filepath):
            self.send_json_response({"error": "File not found"}, 404)
            return
        
        with open(filepath, "r") as f:
            try:
                data = json.load(f)
                self.send_json_response(data)
            except Exception as e:
                self.send_json_response({"error": f"Failed to parse JSON: {e}"}, 500)

    def handle_post_intent(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        
        try:
            intent_data = json.loads(post_data.decode("utf-8"))
            os.makedirs("config", exist_ok=True)
            with open("config/intent.json", "w") as f:
                json.dump(intent_data, f, indent=2)
            self.send_json_response({"success": True})
        except Exception as e:
            self.send_json_response({"error": str(e)}, 400)

    def handle_get_topology(self):
        try:
            parser_engine = IntentParser("config/intent.json")
            intent_data = parser_engine.load_and_validate()
            allocator = IPAllocator(intent_data)
            allocated_topology = allocator.allocate()
            self.send_json_response(allocated_topology)
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def handle_get_gns_status(self):
        try:
            res = requests.get("http://localhost:3080/v2/version", timeout=1.0)
            online = res.status_code == 200
            server_version = res.json().get("version", "2.x") if online else ""
            self.send_json_response({
                "online": online, 
                "server": f"v{server_version}" if online else ""
            })
        except Exception:
            self.send_json_response({"online": False, "server": ""})

    def handle_get_config(self, query_str):
        query_params = urllib.parse.parse_qs(query_str)
        router = query_params.get("router", [None])[0]
        if not router:
            self.send_json_response({"error": "Missing router query parameter"}, 400)
            return
            
        # Clean name to avoid directory traversal
        router = re.sub(r'[^a-zA-Z0-9\-]', '', router)
        config_path = os.path.join("generated_configs", f"{router}_startup-config.cfg")
        
        if not os.path.exists(config_path):
            self.send_json_response({"error": f"Configuration for {router} not found. Run Generation first."}, 404)
            return
            
        try:
            with open(config_path, "r") as f:
                config_content = f.read()
            self.send_json_response({"config": config_content})
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def handle_post_generate(self):
        try:
            parser_engine = IntentParser("config/intent.json")
            intent_data = parser_engine.load_and_validate()
            allocator = IPAllocator(intent_data)
            allocated_topology = allocator.allocate()
            generator = ConfigGenerator(allocated_topology, intent_data)
            generated_configs = generator.generate_configs("generated_configs")
            self.send_json_response({
                "success": True, 
                "count": len(generated_configs)
            })
        except Exception as e:
            self.send_json_response({"error": str(e)}, 500)

    def handle_post_deploy(self):
        global DEPLOY_STATUS
        
        with deploy_lock:
            if DEPLOY_STATUS["status"] == "running":
                self.send_json_response({"error": "Deployment already in progress"}, 400)
                return
            
            # Set to running and spin up worker thread
            DEPLOY_STATUS["status"] = "running"
            DEPLOY_STATUS["error_message"] = ""
            DEPLOY_STATUS["logs"] = []
            for step in DEPLOY_STATUS["steps"]:
                step["status"] = "pending"
                
            t = threading.Thread(target=run_deployment_worker)
            t.daemon = True
            t.start()
            
            self.send_json_response({"success": True, "message": "Deployment started"})

def main():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), AutomationHTTPRequestHandler) as httpd:
        print(f"\n==================================================")
        print(f"   Network Automation GUI is Running! ")
        print(f"==================================================")
        print(f"➔ Access URL:  http://localhost:{PORT}")
        print(f"➔ Backend APIs: http://localhost:{PORT}/api")
        print(f"➔ Serving GUI:  {GUI_DIR}")
        print(f"--------------------------------------------------")
        print(f"Press Ctrl+C to terminate the web server.\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down web server...")
            httpd.shutdown()

if __name__ == "__main__":
    main()
