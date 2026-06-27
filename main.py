#!/usr/bin/env python3
import argparse
import sys
import os

from src.parser import IntentParser
from src.allocator import IPAllocator
from src.generator import ConfigGenerator
from src.gns3_client import GNS3Client
from src.console import (
    ConsoleSpinner, print_success, print_warning, print_error, print_info, print_section
)

def main():
    parser = argparse.ArgumentParser(description="Network Automation Engine for GNS3 Configurations.")
    parser.add_argument("--config", default="config/intent.json", help="Path to network intent JSON file.")
    parser.add_argument("--output-dir", default="generated_configs", help="Directory where startup-configs will be written.")
    parser.add_argument("--deploy", action="store_true", default=True, help="Deploy the topology and configs to GNS3 REST API.")
    parser.add_argument("--no-deploy", dest="deploy", action="store_false", help="Do not deploy to GNS3; only generate files locally.")
    
    args = parser.parse_args()

    print_section("Network Automation CLI")
    print(f"  \033[2mIntent Spec:\033[0m  {args.config}")
    print(f"  \033[2mOutput Path:\033[0m  {args.output_dir}")
    print(f"  \033[2mGNS3 Deploy:\033[0m  {'Enabled (Local REST API)' if args.deploy else 'Disabled'}")

    # 1. Parse Intent File
    try:
        with ConsoleSpinner("Loading and validating Intent Configuration...") as spinner:
            parser_engine = IntentParser(args.config)
            intent_data = parser_engine.load_and_validate()
        print_success("Network intent loaded and validated.")
    except Exception as e:
        print_error(f"Parsing intent failed: {e}")
        sys.exit(1)

    # 2. IP Address Allocation
    print_section("IP Address Planning")
    try:
        with ConsoleSpinner("Allocating IP subnets and loopback addresses...") as spinner:
            allocator = IPAllocator(intent_data)
            allocated_topology = allocator.allocate()
        print_success("Auto-subnetting complete. Generated addressing details:")
        
        # Draw a box-drawn table for addressing plans
        print("\n  ┌" + "─"*8 + "┬" + "─"*6 + "┬" + "─"*16 + "┬" + "─"*58 + "┐")
        print("  │ " + f"{'Router':<6}" + " │ " + f"{'AS':<4}" + " │ " + f"{'Loopback IP':<14}" + " │ " + f"{'Physical Interfaces & Neighbors':<56}" + " │")
        print("  ├" + "─"*8 + "┼" + "─"*6 + "┼" + "─"*16 + "┼" + "─"*58 + "┤")
        for r_name, r_data in allocated_topology.items():
            intf_summaries = []
            for intf_name, intf_data in r_data["interfaces"].items():
                short_intf = intf_name.replace("FastEthernet", "F")
                short_peer_int = intf_data["peer_interface"].replace("FastEthernet", "F")
                intf_summaries.append(f"{short_intf}:{intf_data['ip']}➔{intf_data['peer_node']}({short_peer_int})")
            
            # Wrap interfaces list neatly or truncate if it goes over terminal limit
            interfaces_str = ", ".join(intf_summaries)
            if len(interfaces_str) > 56:
                interfaces_str = interfaces_str[:53] + "..."
            
            loop_ip = r_data['loopback']['ip']
            print("  │ " + f"{r_name:<6}" + " │ " + f"AS{r_data['as']:<2}" + " │ " + f"{loop_ip:<14}" + " │ " + f"{interfaces_str:<56}" + " │")
        print("  └" + "─"*8 + "┴" + "─"*6 + "┴" + "─"*16 + "┴" + "─"*58 + "┘\n")
            
    except Exception as e:
        print_error(f"IP Allocation failed: {e}")
        sys.exit(1)

    # 3. Generate Cisco IOS Configurations
    print_section("Configuration Generation")
    try:
        with ConsoleSpinner("Generating Cisco IOS configurations...") as spinner:
            generator = ConfigGenerator(allocated_topology, intent_data)
            generated_configs = generator.generate_configs(args.output_dir)
        print_success(f"Generated startup configs for {len(generated_configs)} routers in: '{args.output_dir}/'")
    except Exception as e:
        print_error(f"Configuration generation failed: {e}")
        sys.exit(1)

    # 4. GNS3 Auto-Placement & Deployment
    if args.deploy:
        print_section("GNS3 Deployment")
        client = GNS3Client(intent_data)
        
        # Connect to GNS3 REST API, launch if not running
        if client.check_and_start_gns3():
            try:
                # Open or create project
                project = client.get_or_create_project()
                
                # Build topology nodes & links
                client.build_topology(allocated_topology)
                
                # Copy/upload configurations
                client.deploy_configs(generated_configs)
                
                print_section("Deployment Summary")
                print_success("Network topology successfully active in GNS3!")
                print_info(f"Project Name:  {client.project_name}")
                print_info(f"API Endpoint:  {client.server_url}/projects/{client.project_id}")
                print_warning("Open GNS3 GUI client to inspect topology adjacencies and connectivity.")
            except Exception as e:
                print_error(f"GNS3 Deployment failed: {e}")
                sys.exit(1)
        else:
            print_warning("Skipping GNS3 Deployment because server is not available.")
            print_info("Generated configurations are available locally in: " + args.output_dir)

    print_success("Execution complete.\n")

if __name__ == "__main__":
    main()
