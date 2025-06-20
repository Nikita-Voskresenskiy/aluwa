from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import paramiko
from paramiko import SSHClient, Ed25519Key
import socket
from typing import Optional, Tuple

from env_settings import EnvSettings

settings = EnvSettings()
Base = declarative_base()


class DatabaseConnectionManager:
    def __init__(self):
        self.engine = None
        self.tunnel = None
        self._initialize_connection()

    def _initialize_connection(self):
        """Initialize either direct or tunneled connection"""
        if getattr(settings, 'LOCAL', False):
            self._setup_ssh_tunnel()

        db_url = f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{self._get_db_host()}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
        #self.engine = create_async_engine(db_url, echo=True)
        # In your database.py
        self.engine = create_async_engine(
            db_url,
            pool_size=20,
            max_overflow=10,
            pool_timeout=30,
            pool_recycle=3600,  # Recycle connections after 1 hour
            pool_pre_ping=True,  # Enable connection health checks,
            echo=True,
            connect_args={
                "timeout": 5,         # Socket timeout (seconds)
                "command_timeout": 10 # Fail if query takes too long
            }
        )

    def _get_db_host(self) -> str:
        """Returns the appropriate database host based on connection type"""
        return 'localhost' if settings.LOCAL else settings.POSTGRES_HOST

    def _setup_ssh_tunnel(self):
        """Establish SSH tunnel for local development"""
        self.tunnel = SSHTunnel()
        self.tunnel.start(
            ssh_host=settings.SSH_HOST,
            ssh_port=settings.SSH_PORT,
            ssh_username=settings.SSH_USERNAME,
            ssh_pkey_path=settings.SSH_PRIVATE_KEY_PATH,
            remote_host=settings.POSTGRES_HOST,
            remote_port=settings.POSTGRES_PORT
        )

    async def close(self):
        """Clean up all resources"""
        if self.engine:
            await self.engine.dispose()
        if self.tunnel:
            self.tunnel.close()


class SSHTunnel:
    def __init__(self):
        self.ssh: Optional[SSHClient] = None
        self.local_port: Optional[int] = None

    def start(self, ssh_host: str, ssh_port: int, ssh_username: str,
              ssh_pkey_path: str, remote_host: str, remote_port: int) -> int:
        """Start SSH tunnel and return local bound port"""
        self.ssh = SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            pkey = Ed25519Key.from_private_key_file(ssh_pkey_path)
        except Exception as e:
            raise ValueError(f"Failed to load SSH key: {str(e)}")

        self.ssh.connect(
            hostname=ssh_host,
            port=ssh_port,
            username=ssh_username,
            pkey=pkey,
            look_for_keys=False,
            allow_agent=False,
            timeout=10
        )

        # Find an available local port
        with socket.socket() as s:
            s.bind(('', 0))
            self.local_port = s.getsockname()[1]

        # Forward local port to remote host:port
        # Enable keepalive
        transport = self.ssh.get_transport()
        if transport:
            pass#transport.set_keepalive(30)  # Send keepalive every 30 seconds
        else:
            raise RuntimeError("SSH transport could not be established")

        transport.request_port_forward('', self.local_port)
        transport.open_channel(
            'direct-tcpip',
            ('localhost', remote_port),
            ('localhost', self.local_port)
        )

        return self.local_port

    def close(self):
        if self.ssh:
            self.ssh.close()
            self.ssh = None


# Initialize connection manager
db_manager = DatabaseConnectionManager()
engine = db_manager.engine
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_connections():
    """Application shutdown handler"""
    await db_manager.close()