import paramiko
import requests
from env_settings import EnvSettings
settings = EnvSettings()

# Set up SSH client

#ssh.load_system_host_keys()
#ssh.set_missing_host_key_policy(paramiko.WarningPolicy())
pkey = paramiko.Ed25519Key.from_private_key_file(settings.SSH_PRIVATE_KEY_PATH)

server = paramiko.SSHTunnelForwarder(hostname=settings.SSH_HOST, port=settings.SSH_PORT, username=settings.SSH_USERNAME, pkey=pkey, remote_bind_address=('localhost', 5432))
server.start()

# Open the tunnel (like ssh -L)
server.close()
#channel = ssh.get_transport().request_port_forward()
try:
    if channel.active:
        print("✅ Tunnel active. Sending HTTP request...")

        # Keep the connection alive while making requests
        while True:
            response = requests.get("http://localhost:5433/")
            print(f"Status: {response.status_code}, Response: {response.text[:100]}...")

            # Add delay between requests


except KeyboardInterrupt:
    print("\nClosing tunnel...")
finally:
    # Only close when done
    channel.close()
    ssh.close()
    print("Connection closed")