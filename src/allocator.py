import ipaddress

class IPAllocator:
    def __init__(self, intent_data):
        self.intent_data = intent_data
        self.routers = intent_data["routers"]
        self.links = intent_data["links"]
        self.ip_config = intent_data["ip_allocation"]
        self.protocols = intent_data["protocols"]

    def allocate(self):
        """Allocates IP addresses to loopbacks and links based on the intent schema."""
        allocated_topology = {router: {
            "name": router,
            "as": info["as"],
            "loopback_id": info["loopback_id"],
            "coordinates": info.get("coordinates", {"x": 0, "y": 0}),
            "loopback": {},
            "interfaces": {}
        } for router, info in self.routers.items()}

        # 1. Allocate Loopbacks
        for router_name, router_info in self.routers.items():
            asn = str(router_info["as"])
            loopback_range = self.ip_config["as_networks"][asn]["loopback_range"]
            loopback_net = ipaddress.IPv4Network(loopback_range)
            # Allocate IP based on loopback_id
            loopback_ip = loopback_net.network_address + router_info["loopback_id"]
            allocated_topology[router_name]["loopback"] = {
                "ip": str(loopback_ip),
                "mask": "255.255.255.255",
                "prefix_len": 32
            }

        # 2. Subnet Generators for internal physical links
        as_subnets = {}
        for asn, ranges in self.ip_config["as_networks"].items():
            physical_range = ranges["physical_range"]
            net = ipaddress.IPv4Network(physical_range)
            # Create a generator for /30 subnets
            as_subnets[int(asn)] = net.subnets(new_prefix=30)

        # 3. Inter-AS Link subnets
        inter_as_subnets = {}
        for inter_link in self.ip_config.get("inter_as_links", []):
            pair_key = tuple(sorted(inter_link["routers"]))
            inter_as_subnets[pair_key] = ipaddress.IPv4Network(inter_link["subnet"])

        # 4. Allocate Links
        for link in self.links:
            node_a, node_b = link["nodes"]
            int_a, int_b = link["interfaces"]

            as_a = self.routers[node_a]["as"]
            as_b = self.routers[node_b]["as"]

            if as_a == as_b:
                # Internal Link
                asn = as_a
                subnet = next(as_subnets[asn])
                hosts = list(subnet.hosts())
                ip_a, ip_b = hosts[0], hosts[1]
                netmask = str(subnet.netmask)
                prefix_len = subnet.prefixlen
                conn_type = "internal"
                igp_type = self.protocols["igp"][str(asn)]["type"].lower()
            else:
                # Inter-AS Link (External)
                pair_key = tuple(sorted([node_a, node_b]))
                if pair_key in inter_as_subnets:
                    subnet = inter_as_subnets[pair_key]
                else:
                    raise ValueError(f"No subnet specified for inter-AS link between {node_a} and {node_b}")
                
                hosts = list(subnet.hosts())
                # Order host assignments alphabetically to ensure consistency
                if node_a < node_b:
                    ip_a, ip_b = hosts[0], hosts[1]
                else:
                    ip_a, ip_b = hosts[1], hosts[0]
                netmask = str(subnet.netmask)
                prefix_len = subnet.prefixlen
                conn_type = "external"
                igp_type = "none" # Do not run IGP on inter-AS links

            # Check for customized OSPF costs
            cost_a = None
            cost_b = None
            if igp_type == "ospf":
                for cost_rule in self.protocols.get("ospf_costs", []):
                    rule_nodes = cost_rule["nodes"]
                    if node_a in rule_nodes and node_b in rule_nodes:
                        cost_a = cost_rule["cost"]
                        cost_b = cost_rule["cost"]

            # Store allocations
            allocated_topology[node_a]["interfaces"][int_a] = {
                "ip": str(ip_a),
                "mask": netmask,
                "prefix_len": prefix_len,
                "peer_node": node_b,
                "peer_interface": int_b,
                "peer_ip": str(ip_b),
                "type": conn_type,
                "igp": igp_type,
                "ospf_cost": cost_a
            }

            allocated_topology[node_b]["interfaces"][int_b] = {
                "ip": str(ip_b),
                "mask": netmask,
                "prefix_len": prefix_len,
                "peer_node": node_a,
                "peer_interface": int_a,
                "peer_ip": str(ip_a),
                "type": conn_type,
                "igp": igp_type,
                "ospf_cost": cost_b
            }

        return allocated_topology
