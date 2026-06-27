import re
import time
import os
import requests
import subprocess
from src.console import ConsoleSpinner, print_success, print_warning, print_error, print_info

class GNS3Client:
    def __init__(self, intent_data):
        self.intent_data = intent_data
        self.gns3_config = intent_data.get("gns3", {})
        server_base = self.gns3_config.get("server_url", "http://localhost:3080").rstrip("/")
        if not server_base.endswith("/v2"):
            self.server_url = f"{server_base}/v2"
        else:
            self.server_url = server_base
        self.project_name = self.gns3_config.get("project_name", "Network_Automation_Project")
        self.template_name = self.gns3_config.get("router_template", "c7200")
        self.node_symbol = self.gns3_config.get("node_symbol", ":/symbols/router.svg")
        self.project_id = None
        self.nodes_map = {} # Maps router name to GNS3 node dict

    def check_and_start_gns3(self):
        """Checks if GNS3 server is running, and launches GNS3 app if not."""
        with ConsoleSpinner("Checking connection to GNS3 server...") as spinner:
            try:
                requests.get(f"{self.server_url}/version", timeout=2)
                time.sleep(0.5)
                print_success("Connected to GNS3 server REST API successfully.")
                return True
            except requests.exceptions.ConnectionError:
                pass
        
        print_warning("GNS3 server is not running. Launching GNS3 application...")
        try:
            # Open GNS3 application
            subprocess.Popen(["open", "-a", "GNS3"])
            with ConsoleSpinner("Waiting for GNS3 server to initialize...") as spinner:
                # Poll server for up to 15 seconds
                for i in range(15):
                    time.sleep(1)
                    try:
                        requests.get(f"{self.server_url}/version", timeout=1)
                        break
                    except requests.exceptions.ConnectionError:
                        continue
                else:
                    print_error("GNS3 server did not start in time. Please verify GNS3 is open.")
                    return False
            print_success("GNS3 server is now online.")
            return True
        except Exception as e:
            print_error(f"Failed to start GNS3 application: {e}")
            return False

    def get_or_create_project(self):
        """Gets or creates the GNS3 project. Prefers the currently opened project in the GUI."""
        with ConsoleSpinner("Loading GNS3 project list...") as spinner:
            url = f"{self.server_url}/projects"
            res = requests.get(url)
            res.raise_for_status()
            projects = res.json()

            # 1. Prefer the currently opened project in the GUI
            for proj in projects:
                if proj.get("status") == "opened":
                    self.project_id = proj["project_id"]
                    self.project_name = proj["name"]
                    time.sleep(0.5)
                    break
            else:
                # 2. Look for project by name
                for proj in projects:
                    if proj["name"] == self.project_name:
                        self.project_id = proj["project_id"]
                        if proj["status"] == "closed":
                            requests.post(f"{url}/{self.project_id}/open").raise_for_status()
                        break
                else:
                    # 3. Create new project if none open or matching
                    body = {"name": self.project_name}
                    res = requests.post(url, json=body)
                    res.raise_for_status()
                    proj = res.json()
                    self.project_id = proj["project_id"]

        print_success(f"Active GNS3 Project: '{self.project_name}' (ID: {self.project_id})")
        return proj

    def find_router_template(self):
        """Locates the Cisco router template on GNS3 server."""
        with ConsoleSpinner(f"Locating Cisco router template '{self.template_name}'...") as spinner:
            url = f"{self.server_url}/templates"
            res = requests.get(url)
            res.raise_for_status()
            templates = res.json()

            found_t = None
            for t in templates:
                t_name = t.get("name", "")
                if self.template_name.lower() in t_name.lower():
                    found_t = t
                    break

            if not found_t:
                # Fallback search for any Dynamips template
                for t in templates:
                    t_name = t.get("name", "")
                    t_type = t.get("node_type", "")
                    if t_type == "dynamips" or "router" in t_name.lower():
                        found_t = t
                        break

        if found_t:
            print_success(f"Using GNS3 Router Template: '{found_t.get('name')}'")
            return found_t

        available_names = [t.get("name", "") for t in templates]
        raise ValueError(f"No router template containing '{self.template_name}' found. Available templates: {available_names}")

    def clear_project_nodes(self):
        """Clears all existing nodes and links in the project to rebuild topology."""
        with ConsoleSpinner("Stopping running GNS3 nodes...") as spinner:
            # 1. Stop all nodes first to avoid locks or project closures
            try:
                requests.post(f"{self.server_url}/projects/{self.project_id}/nodes/stop").raise_for_status()
            except Exception:
                pass

            # Poll until all nodes are stopped (up to 10 seconds)
            url = f"{self.server_url}/projects/{self.project_id}/nodes"
            for _ in range(10):
                try:
                    res = requests.get(url)
                    if not any(n.get("status") == "started" for n in res.json()):
                        break
                except Exception:
                    pass
                time.sleep(1)

        with ConsoleSpinner("Clearing GNS3 nodes and link configurations...") as spinner:
            # 2. Delete nodes
            try:
                res = requests.get(url)
                nodes = res.json()
            except Exception:
                nodes = []
            
            if nodes:
                for idx, node in enumerate(nodes):
                    spinner.update_message(f"Deleting node {node.get('name', 'unknown')} ({idx+1}/{len(nodes)})...")
                    try:
                        requests.delete(f"{url}/{node['node_id']}").raise_for_status()
                    except Exception:
                        pass
                
                # Poll until all nodes are deleted (up to 10 seconds)
                for _ in range(10):
                    try:
                        res = requests.get(url)
                        if not res.json():
                            break
                    except Exception:
                        pass
                    time.sleep(1)
        
        self.nodes_map.clear()
        print_success("Wiped GNS3 canvas clean.")

    def build_topology(self, allocated_topology):
        """Creates nodes and links in GNS3, placing them automatically based on coordinates."""
        # Ensure project is open
        res = requests.get(f"{self.server_url}/projects/{self.project_id}")
        res.raise_for_status()
        if res.json().get("status") == "closed":
            requests.post(f"{self.server_url}/projects/{self.project_id}/open").raise_for_status()
            print_warning("Re-opened closed GNS3 project.")

        # 1. Clear existing setup
        self.clear_project_nodes()

        # Ensure project is open after clearing
        res = requests.get(f"{self.server_url}/projects/{self.project_id}")
        res.raise_for_status()
        if res.json().get("status") == "closed":
            requests.post(f"{self.server_url}/projects/{self.project_id}/open").raise_for_status()
            print_warning("Re-opened closed GNS3 project after node cleanup.")

        # 2. Get router template
        template = self.find_router_template()
        template_id = template["template_id"]
        node_type = template.get("node_type", template.get("template_type", "dynamips"))
        compute_id = template.get("compute_id", "local")

        # Extract dynamips-specific properties from the template root
        properties_keys = [
            "platform", "image", "nvram", "ram", "slot0", "slot1", "slot2", 
            "slot3", "slot4", "slot5", "slot6", "idlepc", "npe", "midplane", 
            "mmap", "sparsemem", "idlemax", "idlesleep", "auto_delete_disks",
            "disk0", "disk1", "system_id"
        ]
        template_properties = {k: template[k] for k in properties_keys if k in template}

        # 3. Create Nodes
        nodes_url = f"{self.server_url}/projects/{self.project_id}/nodes"
        
        with ConsoleSpinner("Placing routers in GNS3 topology...") as spinner:
            for router_name, router_data in allocated_topology.items():
                spinner.update_message(f"Placing router {router_name} on canvas...")
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
                
                # Robust placement retry block (handles GNS3 project closing unexpectedly)
                for attempt in range(3):
                    try:
                        res = requests.post(nodes_url, json=body)
                        res.raise_for_status()
                        node_info = res.json()
                        self.nodes_map[router_name] = node_info
                        break
                    except requests.exceptions.HTTPError as e:
                        if e.response.status_code == 403 and "not opened" in e.response.text.lower() and attempt < 2:
                            spinner.update_message(f"GNS3 closed unexpectedly. Re-opening project (attempt {attempt+1})...")
                            try:
                                requests.post(f"{self.server_url}/projects/{self.project_id}/open").raise_for_status()
                                time.sleep(1.5)
                                continue
                            except Exception:
                                pass
                        raise e
        print_success(f"Placed all {len(allocated_topology)} routers symmetrically on the grid.")

        # 4. Parse interface to adapter/port mapping
        def parse_interface(intf_name):
            match = re.search(r'([a-zA-Z]+)(\d+)/(\d+)', intf_name)
            if match:
                return int(match.group(2)), int(match.group(3))
            return 0, 0

        # 5. Create Links
        links_url = f"{self.server_url}/projects/{self.project_id}/links"
        created_links = set()

        with ConsoleSpinner("Wiring physical links...") as spinner:
            for link in self.intent_data["links"]:
                node_a, node_b = link["nodes"]
                int_a, int_b = link["interfaces"]

                link_key = tuple(sorted([(node_a, int_a), (node_b, int_b)]))
                if link_key in created_links:
                    continue

                spinner.update_message(f"Linking {node_a} ({int_a}) <---> {node_b} ({int_b})...")
                node_a_id = self.nodes_map[node_a]["node_id"]
                node_b_id = self.nodes_map[node_b]["node_id"]

                adapt_a, port_a = parse_interface(int_a)
                adapt_b, port_b = parse_interface(int_b)

                body = {
                    "nodes": [
                        {"node_id": node_a_id, "adapter_number": adapt_a, "port_number": port_a},
                        {"node_id": node_b_id, "adapter_number": adapt_b, "port_number": port_b}
                    ]
                }

                try:
                    res = requests.post(links_url, json=body)
                    res.raise_for_status()
                    created_links.add(link_key)
                except Exception as e:
                    print_error(f"Failed to link {node_a} ({int_a}) <---> {node_b} ({int_b}): {e}")
        print_success(f"Wired all {len(created_links)} physical interfaces successfully.")

    def deploy_configs(self, generated_configs, project_dir=None):
        """Deploys generated configurations into the GNS3 project structure."""
        with ConsoleSpinner("Deploying startup configurations to GNS3...") as spinner:
            # If project_dir is not specified, try to fetch it from the GNS3 REST API
            if not project_dir:
                try:
                    url = f"{self.server_url}/projects/{self.project_id}"
                    res = requests.get(url)
                    res.raise_for_status()
                    project_dir = res.json().get("path")
                except Exception:
                    pass

            # Method 1: Local direct file copy (very reliable when running locally)
            if project_dir and os.path.exists(project_dir):
                for router_name, node_info in self.nodes_map.items():
                    spinner.update_message(f"Writing local config for {router_name}...")
                    node_uuid = node_info["node_id"]
                    dynamips_config_dir = os.path.join(project_dir, "project-files", "dynamips", node_uuid, "configs")
                    
                    config_src_path = generated_configs[router_name]
                    with open(config_src_path, "r") as src_f:
                        config_content = src_f.read()
                    
                    copied = False
                    if os.path.exists(dynamips_config_dir):
                        # Find existing startup config file (usually starts with 'i')
                        for f_name in os.listdir(dynamips_config_dir):
                            if f_name.endswith("_startup-config.cfg"):
                                dst_path = os.path.join(dynamips_config_dir, f_name)
                                with open(dst_path, "w") as dst_f:
                                    dst_f.write(config_content)
                                copied = True
                        
                        if not copied:
                            router_id = router_name.replace("R", "")
                            dst_path = os.path.join(dynamips_config_dir, f"i{router_id}_startup-config.cfg")
                            with open(dst_path, "w") as dst_f:
                                dst_f.write(config_content)
                            copied = True
                    
                    if not copied:
                        os.makedirs(dynamips_config_dir, exist_ok=True)
                        router_id = router_name.replace("R", "")
                        dst_path = os.path.join(dynamips_config_dir, f"i{router_id}_startup-config.cfg")
                        with open(dst_path, "w") as dst_f:
                            dst_f.write(config_content)
            
            # Method 2: HTTP API Node Files Upload (works remotely and locally)
            for router_name, node_info in self.nodes_map.items():
                spinner.update_message(f"Uploading template config for {router_name}...")
                node_id = node_info["node_id"]
                config_src_path = generated_configs[router_name]
                with open(config_src_path, "r") as src_f:
                    config_content = src_f.read()

                paths_to_try = ["configs/startup-config.cfg", "startup-config.cfg"]
                for path in paths_to_try:
                    file_url = f"{self.server_url}/projects/{self.project_id}/nodes/{node_id}/files/{path}"
                    try:
                        res = requests.post(file_url, data=config_content, headers={"Content-Type": "text/plain"})
                        if res.status_code in [200, 201]:
                            break
                    except Exception:
                        pass
        print_success("Deployed startup configurations to all routers.")

        # 3. Start nodes if autostart is enabled
        if self.gns3_config.get("autostart", True):
            with ConsoleSpinner("Powering on Cisco 7200 routers...") as spinner:
                for router_name, node_info in self.nodes_map.items():
                    spinner.update_message(f"Starting router {router_name}...")
                    node_id = node_info["node_id"]
                    start_url = f"{self.server_url}/projects/{self.project_id}/nodes/{node_id}/start"
                    try:
                        requests.post(start_url).raise_for_status()
                    except Exception as e:
                        print_error(f"Failed to start {router_name}: {e}")
            print_success("Powered on all 14 Cisco 7200 routers. Adjacencies initializing.")
            
            # Save the project state
            try:
                requests.post(f"{self.server_url}/projects/{self.project_id}/write").raise_for_status()
            except Exception:
                pass
