import json
import os
import sys

class IntentParser:
    def __init__(self, file_path):
        self.file_path = file_path

    def load_and_validate(self):
        """Loads and validates the intent JSON file structure."""
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Intent file not found at {self.file_path}")
        
        try:
            with open(self.file_path, 'r') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}")

        # Basic validations
        required_root_keys = ["project_name", "ip_allocation", "routers", "links", "protocols"]
        for key in required_root_keys:
            if key not in data:
                raise KeyError(f"Missing required root key: '{key}' in intent file.")

        # Validate routers
        for router_name, router_info in data["routers"].items():
            if "as" not in router_info or "loopback_id" not in router_info:
                raise KeyError(f"Router '{router_name}' must specify 'as' and 'loopback_id'.")

        # Validate links
        for idx, link in enumerate(data["links"]):
            if "nodes" not in link or len(link["nodes"]) != 2:
                raise ValueError(f"Link index {idx} must specify exactly 2 'nodes'.")
            if "interfaces" not in link or len(link["interfaces"]) != 2:
                raise ValueError(f"Link index {idx} must specify exactly 2 'interfaces'.")
            
            # Ensure referenced nodes exist
            for node in link["nodes"]:
                if node not in data["routers"]:
                    raise ValueError(f"Link index {idx} references unknown node '{node}'.")

        # Validate protocols
        protocols = data["protocols"]
        if "igp" not in protocols:
            raise KeyError("Missing 'igp' configurations under protocols.")
        
        for asn, igp_info in protocols["igp"].items():
            if "type" not in igp_info:
                raise KeyError(f"IGP configuration for AS {asn} must specify 'type'.")
            if igp_info["type"].lower() not in ["rip", "ospf"]:
                raise ValueError(f"Unsupported IGP type '{igp_info['type']}' for AS {asn}. Supported: 'rip', 'ospf'.")

        # Validate BGP
        if "bgp" in protocols:
            for asn, bgp_info in protocols["bgp"].items():
                if "peers" in bgp_info:
                    for peer_asn, peer_info in bgp_info["peers"].items():
                        if "relationship" not in peer_info:
                            raise KeyError(f"BGP peering under AS {asn} with AS {peer_asn} must specify 'relationship'.")
                        if peer_info["relationship"].lower() not in ["customer", "provider", "peer"]:
                            raise ValueError(f"Unsupported relationship '{peer_info['relationship']}'. Must be customer, provider, or peer.")

        return data
