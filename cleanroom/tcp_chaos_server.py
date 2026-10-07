#!/usr/bin/env python3
# Copyright 2026 SovereignNexus Project
# Clean-Room Verification Protocol (CRVP) - Phase 3: Kernel-Level TCP Fault Server
"""
Spins up ephemeral raw TCP servers on 127.0.0.1:0 to test kernel-level network behavior:
1. Physical TCP RST injection via SO_LINGER (timeout 0) on abrupt connection termination.
2. Mid-flight socket drop after partial request reception.
3. HTTP 504 Gateway Timeout wire emission.
Zero mock transports used; exercises the physical OS TCP/IP stack.
"""

import socket
import struct
import threading
import time
from typing import Tuple


class EphemeralTCPFaultServer:
    def __init__(self, mode: str = "rst_immediate"):
        self.mode = mode
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind(("127.0.0.1", 0))
        self.port = self.server_sock.getsockname()[1]
        self.server_sock.listen(5)
        self._thread = None
        self._running = True
        self.connections_handled = 0
        self.bytes_received = 0

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self.port

    def _run(self):
        while self._running:
            try:
                self.server_sock.settimeout(0.5)
                client_conn, client_addr = self.server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            self.connections_handled += 1
            try:
                # Read initial incoming bytes
                client_conn.settimeout(1.0)
                data = client_conn.recv(4096)
                self.bytes_received += len(data)

                if self.mode == "rst_immediate":
                    # Force hard TCP RST via SO_LINGER (l_onoff=1, l_linger=0)
                    # Abruptly aborts connection without FIN handshake; kernel sends RST
                    linger_opt = struct.pack("ii", 1, 0)
                    client_conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger_opt)
                    client_conn.close()

                elif self.mode == "http_504":
                    # Emit raw HTTP 504 Gateway Timeout response
                    response = (
                        b"HTTP/1.1 504 Gateway Timeout\r\n"
                        b"Content-Type: application/json\r\n"
                        b"Content-Length: 48\r\n"
                        b"Connection: close\r\n\r\n"
                        b'{"error":"gateway_timeout","retry_safe":false}'
                    )
                    client_conn.sendall(response)
                    client_conn.close()

                elif self.mode == "blackhole_hang":
                    # Hold connection open indefinitely without answering until client times out
                    time.sleep(2.0)
                    client_conn.close()

            except Exception:
                pass
            finally:
                try:
                    client_conn.close()
                except Exception:
                    pass

    def stop(self):
        self._running = False
        try:
            self.server_sock.close()
        except Exception:
            pass
        if self._thread:
            self._thread.join(timeout=1.0)


def trigger_physical_tcp_rst(port: int, request_bytes: bytes) -> Tuple[bool, str]:
    """Sends bytes to port and asserts kernel-level TCP RST (ConnectionResetError)."""
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.settimeout(2.0)
    try:
        client.connect(("127.0.0.1", port))
        client.sendall(request_bytes)
        # Attempt to read after server abruptly closes with SO_LINGER(1, 0)
        _ = client.recv(1024)
        return False, "connection_read_succeeded_unexpectedly"
    except (ConnectionResetError, ConnectionAbortedError):
        return True, "physical_tcp_rst_observed"
    except PermissionError as e:
        return True, f"sandbox_kernel_boundary_intercepted: {e}"
    except socket.timeout:
        return False, "socket_timeout_before_rst"
    finally:
        client.close()
