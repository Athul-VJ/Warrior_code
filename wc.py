import subprocess
import time
import netifaces
import random
from stem import SocketError
from stem import CircStatus
from stem.control import Controller

def read_ip_addresses(file_path):
    try:
        with open(file_path, 'r') as file:
            ip_addresses = file.read().splitlines()
            return ip_addresses
    except Exception as e:
        print(f'Error reading IP addresses: {e}')
        return []

def get_original_default_route():
    try:
        output = subprocess.check_output(['/usr/bin/sudo', 'ip', 'route', 'show', 'default']).decode('utf-8').strip()
        return output
    except Exception as e:
        print(f'Error getting original default route: {e}')
        return None

def delete_default_route():
    try:
        subprocess.run(['/usr/bin/sudo', 'ip', 'route', 'del', 'default'])
    except Exception as e:
        print(f'Error deleting default route: {e}')

def add_default_route(route):
    try:
        subprocess.run(['/usr/bin/sudo', 'ip', 'route', 'add', route])
    except Exception as e:
        print(f'Error adding default route: {e}')

def is_tor_running():
    try:
        output = subprocess.check_output(['/usr/bin/sudo', 'systemctl', 'is-active', '--quiet', 'tor']).decode('utf-8').strip()
        return output == "active"
    except Exception as e:
        print(f'Error checking Tor status: {e}')
        return False

def get_tor_server_ip():
    try:
        with Controller.from_port(port=9051) as controller:
            controller.authenticate()  # Authenticate with the Tor controller
            circuit_id = next(controller.get_circuits()).id
            for entry in controller.get_circuit(circuit_id).path:
                if entry.status == CircStatus.BUILT:
                    return entry.address
    except SocketError as e:
        if "Network is unreachable" in str(e):
            print('Tor is not reachable. Make sure Tor is running and accessible.')
        else:
            print(f'Error getting Tor server IP: {e}')
        return None
    except StopIteration as e:
        print(f'Error getting Tor server IP: {e}')
        return None

def change_ip(new_ip, interface_name, use_tor=False):
    if interface_name:
        try:
            print(f'Changing IP address to {new_ip} on interface {interface_name}')

            # Flush existing IP configuration
            subprocess.run(['/usr/bin/sudo', 'ip', 'addr', 'flush', 'dev', interface_name])

            # Set the new IP address
            subprocess.run(['/usr/bin/sudo', 'ip', 'addr', 'add', f'{new_ip}/24', 'dev', interface_name])

            # Bring the interface up
            subprocess.run(['/usr/bin/sudo', 'ip', 'link', 'set', 'dev', interface_name, 'up'])

            # Randomize MAC address
            subprocess.run(['/usr/bin/sudo', 'macchanger', '-r', interface_name])

            # If using Tor, set default route through Tor
            if use_tor:
                if is_tor_running():
                    tor_server_ip = get_tor_server_ip()
                    if tor_server_ip:
                        delete_default_route()  # Delete existing default route
                        add_default_route(f'default via {tor_server_ip} dev lo')  # Add default route via Tor
                    else:
                        print('Failed to get Tor server IP. Skipping Tor route.')
                else:
                    print('Tor is not running. Skipping Tor route.')
            else:
                # Restore the original default route
                original_default_route = get_original_default_route()
                if original_default_route:
                    delete_default_route()  # Delete existing default route
                    add_default_route(original_default_route)  # Restore original default route

            print(f'Successfully changed IP address to {new_ip}')
        except Exception as e:
            print(f'Error changing IP address: {e}')
    else:
        print('Invalid network interface.')

# Path to the file containing IP addresses
ip_addresses_file_path = 'ip_addresses.txt'

# Get a list of available network interfaces
available_interfaces = netifaces.interfaces()

while True:
    print('Available network interfaces:', available_interfaces)

    # Read IP addresses from the local file
    ip_addresses = read_ip_addresses(ip_addresses_file_path)

    if ip_addresses:
        for ip in ip_addresses:
            for selected_interface in available_interfaces:
                try:
                    # Change the IP address for the current interface and route through Tor
                    change_ip(ip, selected_interface, use_tor=True)

                    # Sleep for a random duration (between 3 to 7 seconds) before changing to the next IP address
                    time.sleep(random.uniform(3, 7))
                finally:
                    # Restore the original default route
                    delete_default_route()
                    add_default_route(get_original_default_route())
    else:
        # Sleep for a random duration (between 3 to 7 seconds) before attempting to read IP addresses again
        time.sleep(random.uniform(3, 7))
