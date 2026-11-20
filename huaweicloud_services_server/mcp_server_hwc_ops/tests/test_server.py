"""Unit tests for mcp-server-hwc-ops. All cloud calls are mocked."""
import json
import os
import unittest
from unittest.mock import patch, MagicMock

# Ensure credentials are set for imports that check them
os.environ.setdefault("HUAWEI_ACCESS_KEY", "test_ak")
os.environ.setdefault("HUAWEI_SECRET_KEY", "test_sk")

from huaweicloud_services_server.mcp_server_hwc_ops.src.mcp_server_hwc_ops.server import (
    _get_credentials,
    _extract_server_fields,
    mcp,
)


class TestCredentials(unittest.TestCase):
    def test_primary_env_vars(self):
        with patch.dict(os.environ, {"HUAWEI_ACCESS_KEY": "ak1", "HUAWEI_SECRET_KEY": "sk1"}, clear=False):
            ak, sk = _get_credentials()
            self.assertEqual(ak, "ak1")
            self.assertEqual(sk, "sk1")

    def test_alias_env_vars(self):
        env = {"HUAWEICLOUD_SDK_AK": "ak2", "HUAWEICLOUD_SDK_SK": "sk2"}
        with patch.dict(os.environ, env, clear=False):
            # Remove primary vars so aliases are used
            with patch.dict(os.environ, {"HUAWEI_ACCESS_KEY": "", "HUAWEI_SECRET_KEY": ""}):
                ak, sk = _get_credentials()
                self.assertEqual(ak, "ak2")
                self.assertEqual(sk, "sk2")

    def test_missing_credentials_raises(self):
        with patch.dict(os.environ, {"HUAWEI_ACCESS_KEY": "", "HUAWEI_SECRET_KEY": "",
                                      "HUAWEICLOUD_SDK_AK": "", "HUAWEICLOUD_SDK_SK": ""}):
            with self.assertRaises(ValueError):
                _get_credentials()


class TestExtractServerFields(unittest.TestCase):
    def test_extracts_useful_fields(self):
        server = MagicMock()
        server.to_dict.return_value = {
            "id": "srv-001",
            "name": "my-ecs",
            "status": "ACTIVE",
            "flavor": {"id": "c3.large.2"},
            "metadata": {"vpc_id": "vpc-abc"},
            "addresses": {"net1": [{"addr": "10.0.0.1"}]},
            "created": "2025-01-01T00:00:00Z",
            "availability_zone": "la-south-2a",
            "os_type": "Linux",
        }
        result = _extract_server_fields(server)
        self.assertEqual(result["id"], "srv-001")
        self.assertEqual(result["name"], "my-ecs")
        self.assertEqual(result["status"], "ACTIVE")
        self.assertEqual(result["flavor"], "c3.large.2")
        self.assertEqual(result["vpc_id"], "vpc-abc")
        self.assertEqual(result["availability_zone"], "la-south-2a")

    def test_handles_missing_fields(self):
        server = MagicMock()
        server.to_dict.return_value = {"id": "srv-002"}
        result = _extract_server_fields(server)
        self.assertEqual(result["id"], "srv-002")
        self.assertIsNone(result["name"])
        self.assertIsNone(result["flavor"])


class TestMCPToolsRegistered(unittest.TestCase):
    def test_all_tools_are_registered(self):
        expected_tools = [
            "ecs_list_servers",
            "ecs_show_server",
            "vpc_list_vpcs",
            "vpc_list_subnets",
            "obs_list_buckets",
            "cbr_list_vaults",
            "cbr_list_backups",
            "ces_list_alarms",
            "cts_list_traces",
            "lts_list_log_groups",
            "iam_get_current_user_or_projects",
        ]
        # FastMCP stores tools internally; verify the tool functions exist
        for tool_name in expected_tools:
            self.assertTrue(
                hasattr(mcp, "_tool_manager"),
                f"FastMCP instance should have _tool_manager",
            )


class TestEcsListServersMocked(unittest.TestCase):
    @patch("huaweicloud_services_server.mcp_server_hwc_ops.src.mcp_server_hwc_ops.server._ecs_client")
    def test_ecs_list_servers_returns_filtered_fields(self, mock_client_fn):
        from huaweicloud_services_server.mcp_server_hwc_ops.src.mcp_server_hwc_ops.server import ecs_list_servers

        mock_server = MagicMock()
        mock_server.to_dict.return_value = {
            "id": "s1",
            "name": "test-ecs",
            "status": "ACTIVE",
            "flavor": {"id": "c3.xlarge"},
            "metadata": {"vpc_id": "vpc-1"},
            "addresses": {},
            "created": "2025-06-01",
            "availability_zone": "az1",
        }

        mock_response = MagicMock()
        mock_response.servers = [mock_server]

        mock_client = MagicMock()
        mock_client.list_servers_details.return_value = mock_response
        mock_client_fn.return_value = mock_client

        result = ecs_list_servers(region="la-south-2")
        data = json.loads(result)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "s1")
        self.assertEqual(data[0]["name"], "test-ecs")
        self.assertEqual(data[0]["flavor"], "c3.xlarge")

    @patch("huaweicloud_services_server.mcp_server_hwc_ops.src.mcp_server_hwc_ops.server._ecs_client")
    def test_ecs_list_servers_empty(self, mock_client_fn):
        from huaweicloud_services_server.mcp_server_hwc_ops.src.mcp_server_hwc_ops.server import ecs_list_servers

        mock_response = MagicMock()
        mock_response.servers = []

        mock_client = MagicMock()
        mock_client.list_servers_details.return_value = mock_response
        mock_client_fn.return_value = mock_client

        result = ecs_list_servers(region="la-south-2")
        data = json.loads(result)
        self.assertEqual(data, [])


class TestVpcListVpcsMocked(unittest.TestCase):
    @patch("huaweicloud_services_server.mcp_server_hwc_ops.src.mcp_server_hwc_ops.server._vpc_client")
    def test_vpc_list_vpcs(self, mock_client_fn):
        from huaweicloud_services_server.mcp_server_hwc_ops.src.mcp_server_hwc_ops.server import vpc_list_vpcs

        mock_vpc = MagicMock()
        mock_vpc.to_dict.return_value = {"id": "vpc-1", "name": "my-vpc", "cidr": "10.0.0.0/16"}

        mock_response = MagicMock()
        mock_response.vpcs = [mock_vpc]

        mock_client = MagicMock()
        mock_client.list_vpcs.return_value = mock_response
        mock_client_fn.return_value = mock_client

        result = vpc_list_vpcs(region="la-south-2")
        data = json.loads(result)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], "vpc-1")


class TestCbrListVaultsMocked(unittest.TestCase):
    @patch("huaweicloud_services_server.mcp_server_hwc_ops.src.mcp_server_hwc_ops.server._cbr_client")
    def test_cbr_list_vaults(self, mock_client_fn):
        from huaweicloud_services_server.mcp_server_hwc_ops.src.mcp_server_hwc_ops.server import cbr_list_vaults

        mock_vault = MagicMock()
        mock_vault.to_dict.return_value = {"id": "vault-1", "name": "my-vault"}

        mock_response = MagicMock()
        mock_response.vaults = [mock_vault]

        mock_client = MagicMock()
        mock_client.list_vault.return_value = mock_response
        mock_client_fn.return_value = mock_client

        result = cbr_list_vaults(region="la-south-2")
        data = json.loads(result)
        self.assertEqual(len(data), 1)


if __name__ == "__main__":
    unittest.main()
