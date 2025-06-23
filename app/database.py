from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import paramiko
from paramiko import SSHClient, Ed25519Key
import socket
from typing import Optional
from contextlib import contextmanager
from sqlalchemy.orm import Session
import logging
from env_settings import EnvSettings
import psycopg2
settings = EnvSettings()
Base = declarative_base()


class SSHTunnel:
    def __init__(self):
        self.ssh: Optional[SSHClient] = None
        self.local_port: Optional[int] = None
        self.is_active = False

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
        '''
        # Find an available local port
        with socket.socket() as s:
            s.bind(('', 0))
            self.local_port = s.getsockname()[1]
        '''
        self.local_port = 5433
        # Forward local port to remote host:port
        transport = self.ssh.get_transport()
        if not transport:
            raise RuntimeError("SSH transport could not be established")

        #transport.request_port_forward('', self.local_port)

        channel = transport.open_channel(
            'direct-tcpip',
            dest_addr=(remote_host, remote_port),
            src_addr=('localhost', self.local_port)
        )

        # Enable keepalive
        transport.set_keepalive(30)
        return self.local_port

    def get_debug_info(self) -> dict:
        """Return debug information about the tunnel"""
        if not self.ssh:
            return {"status": "not_connected"}

        transport = self.ssh.get_transport()
        return {
            "status": "active" if transport and transport.is_active() else "inactive",
            "local_port": self.local_port,
            "ssh_session_active": transport.is_active() if transport else False,
            "remote_host": transport.getpeername() if transport else None
        }

    def log_debug_info(self):
        """Log current tunnel status"""
        logger = logging.getLogger(__name__)
        info = self.get_debug_info()
        logger.debug(f"SSH Tunnel Status: {info}")

    def close(self):
        if self.ssh:
            self.ssh.close()
            self.ssh = None


class DatabaseConnectionManager:
    def __init__(self):
        self.engine = None
        self.tunnel = None
        try:
            self._initialize_connection()
            self._verify_connection()
        except Exception as e:
            self.close()
            raise RuntimeError(f"Failed to initialize database connection: {str(e)}")

    def _initialize_connection(self):
        """Initialize either direct or tunneled connection"""
        try:
            if settings.LOCAL:
                self._setup_ssh_tunnel()

            db_url = f"postgresql+psycopg2://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{self._get_db_host()}:{self._get_db_port()}/{settings.POSTGRES_DB}"

            self.engine = create_engine(
                db_url,
                pool_size=5,
                max_overflow=10,
                pool_recycle=3600,
                pool_pre_ping=True,
                connect_args={
                    "connect_timeout": 10,
                    "keepalives": 1,
                    "keepalives_idle": 30,
                    "keepalives_interval": 10,
                    "keepalives_count": 5
                }
            )
        except Exception as e:
            raise RuntimeError(f"Engine creation failed: {str(e)}")

    def _verify_connection(self):
        """Enhanced connection verification with detailed debugging"""
        logger = logging.getLogger(__name__)

        # Test 1: Verify tunnel exists
        if not self.tunnel or not self.tunnel.is_active():
            raise RuntimeError("SSH tunnel not active")

        logger.info("Testing database connection through tunnel...")

        # Test 2: Raw socket connectivity
        try:
            with socket.create_connection(('localhost', self.tunnel.local_port), timeout=5) as s:
                logger.debug("Socket connection to tunnel endpoint successful")
                # PostgreSQL will send SSL handshake first
                banner = s.recv(1024)
                if not banner:
                    raise RuntimeError("No response from PostgreSQL - service may not be running")
                logger.debug(f"PostgreSQL banner: {banner[:100].decode('ascii', errors='ignore')}")
        except Exception as e:
            raise RuntimeError(f"Raw socket connection failed: {str(e)}")

        # Test 3: Full SQLAlchemy connection
        try:
            with self.engine.connect() as conn:
                result = conn.execute("SELECT 1")
                if result.scalar() != 1:
                    raise RuntimeError("Test query failed")
                logger.info("Database connection verified successfully")
        except Exception as e:
            raise RuntimeError(f"SQLAlchemy connection failed: {str(e)}")

    def _get_db_host(self) -> str:
        """Returns the appropriate database host based on connection type"""
        return 'localhost' if settings.LOCAL else settings.POSTGRES_HOST

    def _get_db_port(self) -> int:
        """Returns the appropriate database host based on connection type"""
        return 5433 if settings.LOCAL else settings.POSTGRES_PORT


    def _setup_ssh_tunnel(self):
        """Establish SSH tunnel with enhanced debugging"""
        logger = logging.getLogger(__name__)

        logger.info("Starting SSH tunnel setup...")

        # 1. Verify SSH parameters
        if not all([settings.SSH_HOST, settings.SSH_PORT, settings.SSH_USERNAME, settings.SSH_PRIVATE_KEY_PATH]):
            error_msg = "Missing SSH configuration parameters"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # 2. Initialize tunnel
        self.tunnel = SSHTunnel()
        try:
            logger.info("Starting SSH tunnel...")
            local_port = self.tunnel.start(
                ssh_host=settings.SSH_HOST,
                ssh_port=settings.SSH_PORT,
                ssh_username=settings.SSH_USERNAME,
                ssh_pkey_path=settings.SSH_PRIVATE_KEY_PATH,
                remote_host='localhost',
                remote_port=settings.POSTGRES_PORT
            )
            logger.info(f"SSH tunnel established on local port {local_port}")

            # 3. Verify PostgreSQL connectivity through tunnel
            try:
                conn = psycopg2.connect(
                    host='localhost',
                    port=local_port,
                    user=settings.POSTGRES_USER,
                    password=settings.POSTGRES_PASSWORD,
                    database=settings.POSTGRES_DB,
                    connect_timeout=5
                )
                conn.close()
                logger.info("Successfully connected to PostgreSQL through tunnel")
            except psycopg2.OperationalError as e:
                error_msg = (f"PostgreSQL connection through tunnel failed. "
                             f"Verify PostgreSQL is running on remote server and "
                             f"accepting connections. Error: {str(e)}")
                logger.error(error_msg)
                self.tunnel.close()
                raise ConnectionError(error_msg)

        except Exception as e:
            error_msg = f"SSH tunnel setup failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if self.tunnel:
                self.tunnel.close()
            raise ConnectionError(error_msg)

    def close(self):
        """Clean up all resources"""
        if self.engine:
            self.engine.dispose()
        if self.tunnel:
            self.tunnel.close()


# Initialize connection manager
db_manager = DatabaseConnectionManager()
engine = db_manager.engine
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)

'''
@contextmanager
def get_db():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
'''

def close_connections():
    """Application shutdown handler"""
    db_manager.close()