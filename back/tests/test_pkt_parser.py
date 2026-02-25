"""Unit tests for pkt_parser.py - packet parsing utilities."""

import pytest
import dpkt
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO

# Import from src
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pkt_parser import (
    packet_uuid,
    is_ipv4_address,
    int_to_ip,
    is_dhcp,
    udp_packet_type,
    ip_packet_type,
)


class TestPacketUUID:
    """Tests for packet_uuid() function."""
    
    def test_uuid_default_size(self):
        """Generate UUID with default size (8)."""
        uuid = packet_uuid()
        assert uuid.startswith("pkt_")
        assert len(uuid) == 12  # "pkt_" (4) + 8 chars
    
    def test_uuid_custom_size(self):
        """Generate UUID with custom size."""
        uuid = packet_uuid(size=16)
        assert uuid.startswith("pkt_")
        assert len(uuid) == 20  # "pkt_" (4) + 16 chars
    
    def test_uuid_uniqueness(self):
        """Each UUID should be unique."""
        uuids = [packet_uuid() for _ in range(100)]
        assert len(set(uuids)) == 100
    
    def test_uuid_custom_chars(self):
        """UUID can use custom character set."""
        import string
        custom_chars = "ABC123"
        uuid = packet_uuid(size=8, chars=custom_chars)
        assert all(c in custom_chars or c == "_" for c in uuid)


class TestIsIPv4Address:
    """Tests for is_ipv4_address() function."""
    
    def test_valid_addresses(self):
        """Valid IPv4 addresses should return True."""
        valid = [
            "192.168.1.1",
            "10.0.0.1",
            "172.16.0.1",
            "255.255.255.255",
            "0.0.0.0",
            "127.0.0.1",
        ]
        for addr in valid:
            assert is_ipv4_address(addr) == True, f"Failed for {addr}"
    
    def test_invalid_addresses(self):
        """Invalid IPv4 addresses should return False."""
        invalid = [
            "256.0.0.0",      # Octet > 255
            "192.168.1",      # Too few octets
            "192.168.1.1.1",  # Too many octets
            "192.168.a.1",    # Non-digit
            "192.168.-1.1",   # Negative
            "",               # Empty
            "invalid",        # Non-numeric
            "192.168.1.1/24", # CIDR notation
        ]
        for addr in invalid:
            assert is_ipv4_address(addr) == False, f"Failed for {addr}"
    
    def test_boundary_values(self):
        """Test boundary octet values (0-255)."""
        assert is_ipv4_address("0.0.0.0") == True
        assert is_ipv4_address("255.255.255.255") == True
        assert is_ipv4_address("256.255.255.255") == False
        assert is_ipv4_address("0.0.0.256") == False


class TestIntToIP:
    """Tests for int_to_ip() function."""
    
    def test_common_addresses(self):
        """Convert common IP integers to addresses."""
        # 192.168.1.1 = (192 << 24) + (168 << 16) + (1 << 8) + 1
        assert int_to_ip(3232235777) == "192.168.1.1"
        
        # 10.0.0.0
        assert int_to_ip(167772160) == "10.0.0.0"
        
        # 127.0.0.1
        assert int_to_ip(2130706433) == "127.0.0.1"
    
    def test_boundary_values(self):
        """Test boundary integer values."""
        assert int_to_ip(0) == "0.0.0.0"
        assert int_to_ip(4294967295) == "255.255.255.255"
    
    def test_none_input(self):
        """None should return empty string."""
        assert int_to_ip(None) == ""
    
    def test_reconstruction(self):
        """IP → int → IP should be idempotent."""
        ips = ["192.168.1.1", "10.0.0.1", "172.16.0.1"]
        for ip in ips:
            # This tests round-trip if we had int_to_ip inverse
            octets = [int(x) for x in ip.split(".")]
            ip_int = (octets[0] << 24) + (octets[1] << 16) + (octets[2] << 8) + octets[3]
            assert int_to_ip(ip_int) == ip


class TestIsDHCP:
    """Tests for is_dhcp() function."""
    
    def test_dhcp_packet_discover(self):
        """DHCP Discover packet should be recognized."""
        # Create a minimal DHCP packet
        dhcp = dpkt.dhcp.DHCP()
        dhcp.op = dpkt.dhcp.DHCP_OP_REQUEST
        dhcp.opts = [
            (dpkt.dhcp.DHCP_OPT_MSGTYPE, bytes([dpkt.dhcp.DHCPDISCOVER]))
        ]
        
        # Wrap in UDP
        udp = dpkt.udp.UDP()
        udp.sport = 68
        udp.dport = 67
        udp.data = bytes(dhcp)
        
        assert is_dhcp(udp) == True
    
    def test_non_dhcp_udp(self):
        """Non-DHCP UDP packet should not be recognized."""
        udp = dpkt.udp.UDP()
        udp.sport = 53  # DNS port
        udp.dport = 53
        udp.data = b"random data"
        
        assert is_dhcp(udp) == False
    
    def test_malformed_dhcp(self):
        """Malformed DHCP should handle gracefully."""
        udp = dpkt.udp.UDP()
        udp.data = b"\\x00\\x01\\x02"  # Invalid DHCP
        
        # Should not raise exception
        result = is_dhcp(udp)
        assert result == False


class TestUDPPacketType:
    """Tests for udp_packet_type() function."""
    
    def test_dhcp_discover(self):
        """DHCP Discover packet."""
        dhcp = dpkt.dhcp.DHCP()
        dhcp.op = dpkt.dhcp.DHCP_OP_REQUEST
        dhcp.opts = [
            (dpkt.dhcp.DHCP_OPT_MSGTYPE, bytes([dpkt.dhcp.DHCPDISCOVER]))
        ]
        
        udp = dpkt.udp.UDP()
        udp.sport = 68
        udp.dport = 67
        udp.data = bytes(dhcp)
        
        result = udp_packet_type(udp)
        assert "DHCP Discover" in result
    
    def test_dhcp_offer(self):
        """DHCP Offer packet."""
        dhcp = dpkt.dhcp.DHCP()
        dhcp.yiaddr = 3232235777  # 192.168.1.1
        dhcp.opts = [
            (dpkt.dhcp.DHCP_OPT_MSGTYPE, bytes([dpkt.dhcp.DHCPOFFER])),
            (dpkt.dhcp.DHCP_OPT_NETMASK, bytes([255, 255, 255, 0])),
        ]
        
        udp = dpkt.udp.UDP()
        udp.data = bytes(dhcp)
        
        result = udp_packet_type(udp)
        assert "DHCP Offer" in result
        assert "192.168.1.1" in result
    
    def test_regular_udp(self):
        """Non-DHCP UDP packet."""
        udp = dpkt.udp.UDP()
        udp.sport = 8080
        udp.dport = 80
        udp.data = b"HTTP GET"
        
        result = udp_packet_type(udp)
        assert "UDP 8080 > 80" in result
    
    def test_udp_port_format(self):
        """UDP port format should be 'sport > dport'."""
        udp = dpkt.udp.UDP()
        udp.sport = 12345
        udp.dport = 80
        udp.data = b""
        
        result = udp_packet_type(udp)
        assert "12345" in result
        assert "80" in result


class TestIPPacketType:
    """Tests for ip_packet_type() function."""
    
    def test_icmp_packet(self):
        """ICMP packet should be recognized."""
        icmp = dpkt.icmp.ICMP()
        icmp.type = dpkt.icmp.ICMP_ECHO
        
        ip_pkt = dpkt.ip.IP()
        ip_pkt.data = icmp
        
        result = ip_packet_type(ip_pkt)
        assert "ICMP" in result or "Echo" in result
    
    def test_tcp_packet(self):
        """TCP packet should be recognized."""
        tcp = dpkt.tcp.TCP()
        tcp.flags = dpkt.tcp.TH_SYN
        
        ip_pkt = dpkt.ip.IP()
        ip_pkt.data = tcp
        
        result = ip_packet_type(ip_pkt)
        assert result is not None
    
    def test_udp_packet(self):
        """UDP packet should return the packet."""
        udp = dpkt.udp.UDP()
        
        ip_pkt = dpkt.ip.IP()
        ip_pkt.data = udp
        
        # Should return the same object or handle gracefully
        result = ip_packet_type(ip_pkt)
        assert result is not None


# Integration tests
class TestPacketParsingIntegration:
    """Integration tests for packet parsing functions."""
    
    def test_valid_ip_followed_by_conversion(self):
        """Validate IP then convert to int and back."""
        ip = "10.20.30.40"
        assert is_ipv4_address(ip) == True
        
        octets = [int(x) for x in ip.split(".")]
        ip_int = (octets[0] << 24) + (octets[1] << 16) + (octets[2] << 8) + octets[3]
        assert int_to_ip(ip_int) == ip
    
    def test_multiple_uuids_in_packet_flow(self):
        """Simulate packet flow with multiple UUIDs."""
        uuids = [packet_uuid() for _ in range(10)]
        assert len(set(uuids)) == 10
        assert all(u.startswith("pkt_") for u in uuids)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
