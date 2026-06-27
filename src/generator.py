import os
from jinja2 import Environment, FileSystemLoader

class ConfigGenerator:
    def __init__(self, allocated_topology, intent_data, template_dir="templates"):
        self.topology = allocated_topology
        self.intent_data = intent_data
        self.template_dir = template_dir
        self.env = Environment(loader=FileSystemLoader(self.template_dir), trim_blocks=True, lstrip_blocks=True)
        self.template = self.env.get_template("cisco_ios.j2")

    def generate_configs(self, output_dir="generated_configs"):
        """Generates configuration files for all routers in the topology."""
        os.makedirs(output_dir, exist_ok=True)
        generated_files = {}

        for router_name, router_data in self.topology.items():
            # Find iBGP peers (all other routers in the same AS)
            internal_bgp_peers = []
            for peer_name, peer_data in self.topology.items():
                if peer_name != router_name and peer_data["as"] == router_data["as"]:
                    internal_bgp_peers.append((peer_name, peer_data))

            # Find eBGP sessions (interfaces of type "external")
            external_bgp_interfaces = []
            border_router = False
            
            for intf_name, intf_data in router_data["interfaces"].items():
                if intf_data["type"] == "external":
                    border_router = True
                    peer_node = intf_data["peer_node"]
                    peer_as = self.topology[peer_node]["as"]
                    
                    # Look up relationship policy in bgp protocol configuration
                    local_as_str = str(router_data["as"])
                    peer_as_str = str(peer_as)
                    
                    bgp_protocols = self.intent_data["protocols"].get("bgp", {})
                    relationship = "peer"  # Default
                    
                    if local_as_str in bgp_protocols and "peers" in bgp_protocols[local_as_str]:
                        peer_policy = bgp_protocols[local_as_str]["peers"].get(peer_as_str, {})
                        relationship = peer_policy.get("relationship", "peer").lower()
                    
                    # Determine BGP policy attributes based on relationship
                    if relationship == "customer":
                        comm_tag = 300
                        local_pref = 300
                    elif relationship == "provider":
                        comm_tag = 100
                        local_pref = 100
                    else:  # peer
                        comm_tag = 200
                        local_pref = 200

                    external_bgp_interfaces.append({
                        "interface": intf_name,
                        "peer_node": peer_node,
                        "peer_as": peer_as,
                        "peer_ip": intf_data["peer_ip"],
                        "relationship": relationship,
                        "comm_tag": comm_tag,
                        "local_pref": local_pref
                    })

            # Render template
            config_content = self.template.render(
                router=router_data,
                internal_bgp_peers=internal_bgp_peers,
                external_bgp_interfaces=external_bgp_interfaces,
                border_router=border_router
            )

            file_path = os.path.join(output_dir, f"{router_name}_startup-config.cfg")
            with open(file_path, "w") as f:
                f.write(config_content)
            
            generated_files[router_name] = file_path

        return generated_files
