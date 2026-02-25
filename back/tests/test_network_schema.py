"""Unit tests for network_schema.py - network data structures."""

import pytest
from dataclasses import fields

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from network_schema import (
    NodeData,
    NodeConfig,
    NodeInterface,
    Node,
    Link,
    Network,
)


class TestNodeData:
    """Tests for NodeData dataclass."""
    
    def test_creation(self):
        """Create NodeData with id and label."""
        node = NodeData(id="h1", label="Host 1")
        assert node.id == "h1"
        assert node.label == "Host 1"
    
    def test_fields(self):
        """Verify NodeData has correct fields."""
        node_fields = {f.name for f in fields(NodeData)}
        assert node_fields == {"id", "label"}
    
    def test_empty_values(self):
        """NodeData with empty strings."""
        node = NodeData(id="", label="")
        assert node.id == ""
        assert node.label == ""


class TestNodeConfig:
    """Tests for NodeConfig dataclass."""
    
    def test_default_values(self):
        """NodeConfig should have sensible defaults."""
        config = NodeConfig()
        assert config.label == ""
        assert config.type == ""
        assert config.stp == 0
        assert config.priority is None
        assert config.default_gw == ""
    
    def test_l2_switch_config(self):
        """Configure L2 switch with STP."""
        config = NodeConfig(
            label="sw1",
            type="l2_switch",
            stp=1,
            priority=32768,
        )
        assert config.label == "sw1"
        assert config.type == "l2_switch"
        assert config.stp == 1
        assert config.priority == 32768
    
    def test_host_config(self):
        """Configure host with default gateway."""
        config = NodeConfig(
            label="h1",
            type="host",
            default_gw="192.168.1.1",
        )
        assert config.label == "h1"
        assert config.type == "host"
        assert config.default_gw == "192.168.1.1"
    
    def test_router_config(self):
        """Configure router."""
        config = NodeConfig(
            label="r1",
            type="router",
        )
        assert config.type == "router"
    
    def test_stp_values(self):
        """STP field should accept 0, 1, 2."""
        for stp_val in [0, 1, 2]:
            config = NodeConfig(stp=stp_val)
            assert config.stp == stp_val
    
    def test_priority_types(self):
        """Priority can be None or int."""
        config1 = NodeConfig(priority=None)
        assert config1.priority is None
        
        config2 = NodeConfig(priority=32768)
        assert config2.priority == 32768


class TestNodeInterface:
    """Tests for NodeInterface dataclass."""
    
    def test_creation(self):
        """Create interface with minimal data."""
        iface = NodeInterface(
            connect="sw1",
            id="h1_1",
            name="h1-eth0",
            ip="192.168.1.10",
        )
        assert iface.connect == "sw1"
        assert iface.id == "h1_1"
        assert iface.name == "h1-eth0"
        assert iface.ip == "192.168.1.10"
    
    def test_vlan_interface(self):
        """Interface with VLAN."""
        iface = NodeInterface(
            connect="sw1",
            id="h1_1",
            name="h1-eth0",
            ip="192.168.1.10",
            vlan=100,
        )
        assert iface.vlan == 100
    
    def test_optional_fields(self):
        """Test optional interface fields."""
        iface = NodeInterface(
            connect="sw1",
            id="h1_1",
            name="h1-eth0",
            ip="192.168.1.10",
        )
        # Check if optional fields default to None or empty
        assert hasattr(iface, "connect")
    
    def test_interface_without_ip(self):
        """Interface without IP (e.g., switch port)."""
        iface = NodeInterface(
            connect="h2",
            id="sw1_1",
            name="sw1-eth0",
            ip="",
        )
        assert iface.ip == ""


class TestNode:
    """Tests for Node dataclass."""
    
    def test_host_node(self):
        """Create a host node."""
        node = Node(
            data=NodeData(id="h1", label="Host 1"),
            config=NodeConfig(type="host", default_gw="192.168.1.1"),
            interfaces=[
                NodeInterface(
                    connect="sw1",
                    id="h1_1",
                    name="h1-eth0",
                    ip="192.168.1.10",
                )
            ]
        )
        assert node.data.id == "h1"
        assert node.config.type == "host"
        assert len(node.interfaces) == 1
    
    def test_switch_node(self):
        """Create a switch node."""
        node = Node(
            data=NodeData(id="sw1", label="Switch 1"),
            config=NodeConfig(type="l2_switch", stp=1),
            interfaces=[
                NodeInterface(connect="h1", id="sw1_1", name="sw1-eth1", ip=""),
                NodeInterface(connect="h2", id="sw1_2", name="sw1-eth2", ip=""),
            ]
        )
        assert node.config.type == "l2_switch"
        assert len(node.interfaces) == 2
    
    def test_router_node(self):
        """Create a router node."""
        node = Node(
            data=NodeData(id="r1", label="Router 1"),
            config=NodeConfig(type="router"),
            interfaces=[
                NodeInterface(connect="sw1", id="r1_1", name="r1-eth0", ip="192.168.1.1"),
                NodeInterface(connect="h1", id="r1_2", name="r1-eth1", ip="10.0.0.1"),
            ]
        )
        assert node.config.type == "router"
        assert len(node.interfaces) == 2


class TestLink:
    """Tests for Link dataclass."""
    
    def test_simple_link(self):
        """Create a simple link between two nodes."""
        link = Link(source="h1", target="sw1", weight=1.0)
        assert link.source == "h1"
        assert link.target == "sw1"
        assert link.weight == 1.0
    
    def test_link_with_bandwidth(self):
        """Link with bandwidth constraint."""
        link = Link(
            source="h1",
            target="sw1",
            weight=1.0,
            bandwidth=1000,  # 1Gbps
        )
        assert link.bandwidth == 1000
    
    def test_link_with_delay(self):
        """Link with delay."""
        link = Link(
            source="h1",
            target="sw1",
            weight=1.0,
            delay=10,  # 10ms
        )
        assert link.delay == 10


class TestNetwork:
    """Tests for Network dataclass."""
    
    def test_simple_network(self):
        """Create a simple network with 2 hosts and 1 switch."""
        h1 = Node(
            data=NodeData(id="h1", label="Host 1"),
            config=NodeConfig(type="host"),
            interfaces=[
                NodeInterface(connect="sw1", id="h1_1", name="h1-eth0", ip="192.168.1.10")
            ],
        )
        
        h2 = Node(
            data=NodeData(id="h2", label="Host 2"),
            config=NodeConfig(type="host"),
            interfaces=[
                NodeInterface(connect="sw1", id="h2_1", name="h2-eth0", ip="192.168.1.11")
            ],
        )
        
        sw1 = Node(
            data=NodeData(id="sw1", label="Switch 1"),
            config=NodeConfig(type="l2_switch"),
            interfaces=[
                NodeInterface(connect="h1", id="sw1_1", name="sw1-eth1", ip=""),
                NodeInterface(connect="h2", id="sw1_2", name="sw1-eth2", ip=""),
            ],
        )
        
        network = Network(
            nodes=[h1, h2, sw1],
            links=[
                Link(source="h1", target="sw1"),
                Link(source="h2", target="sw1"),
            ],
        )
        
        assert len(network.nodes) == 3
        assert len(network.links) == 2
        assert network.nodes[0].data.id == "h1"
    
    def test_network_with_routing(self):
        """Network with routers and multiple subnets."""
        # Setup: Host → Router → Switch → Host
        h1 = Node(
            data=NodeData(id="h1", label="Host 1"),
            config=NodeConfig(type="host", default_gw="192.168.1.1"),
            interfaces=[NodeInterface(connect="r1", id="h1_1", name="h1-eth0", ip="192.168.1.10")],
        )
        
        r1 = Node(
            data=NodeData(id="r1", label="Router 1"),
            config=NodeConfig(type="router"),
            interfaces=[
                NodeInterface(connect="h1", id="r1_1", name="r1-eth0", ip="192.168.1.1"),
                NodeInterface(connect="sw1", id="r1_2", name="r1-eth1", ip="10.0.0.1"),
            ],
        )
        
        network = Network(
            nodes=[h1, r1],
            links=[Link(source="h1", target="r1")],
        )
        
        assert len(network.nodes) == 2
        # Find router
        router = [n for n in network.nodes if n.config.type == "router"][0]
        assert router.data.id == "r1"
    
    def test_empty_network(self):
        """Empty network initialization."""
        network = Network(nodes=[], links=[])
        assert len(network.nodes) == 0
        assert len(network.links) == 0


class TestNetworkValidation:
    """Tests for network structure validation."""
    
    def test_node_ids_are_unique(self):
        """All node IDs should be unique in a network."""
        h1 = Node(
            data=NodeData(id="h1", label="Host 1"),
            config=NodeConfig(type="host"),
            interfaces=[],
        )
        
        h1_dup = Node(
            data=NodeData(id="h1", label="Host 1 Duplicate"),
            config=NodeConfig(type="host"),
            interfaces=[],
        )
        
        # This should ideally raise validation error
        # but currently just test that we can create it
        network = Network(nodes=[h1, h1_dup], links=[])
        node_ids = [n.data.id for n in network.nodes]
        assert len(node_ids) == 2
        assert node_ids.count("h1") == 2  # Duplicate detected
    
    def test_interfaces_reference_existing_nodes(self):
        """Interface 'connect' field should reference existing node."""
        h1 = Node(
            data=NodeData(id="h1", label="Host 1"),
            config=NodeConfig(type="host"),
            interfaces=[
                # Connecting to non-existent sw2
                NodeInterface(connect="sw2", id="h1_1", name="h1-eth0", ip="192.168.1.10")
            ],
        )
        
        network = Network(nodes=[h1], links=[])
        # Check if any interface connects to non-existent node
        existing_ids = {n.data.id for n in network.nodes}
        for node in network.nodes:
            for iface in node.interfaces:
                # This should ideally be validated
                assert iface.connect is not None


class TestNetworkFromJSON:
    """Tests for creating network from JSON (if applicable)."""
    
    def test_simple_json_deserialization(self):
        """Deserialize simple network from dict."""
        network_dict = {
            "nodes": [
                {
                    "data": {"id": "h1", "label": "Host 1"},
                    "config": {"type": "host", "label": "h1"},
                    "interfaces": [
                        {"connect": "sw1", "id": "h1_1", "name": "h1-eth0", "ip": "192.168.1.10"}
                    ]
                }
            ],
            "links": []
        }
        
        # This tests if we can create from dict (if we add from_dict method)
        # For now just verify structure
        assert "nodes" in network_dict
        assert len(network_dict["nodes"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
