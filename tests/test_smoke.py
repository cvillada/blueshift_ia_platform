#!/usr/bin/env python3
"""Teste de fumaca: valida estrutura e imports basicos."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from blueshift_layer import license_client, installer, update_client
from blueshift_layer.connector_pack import mcp_erp, mcp_crm, mcp_rh


def test_license_dev_key():
    assert license_client.validate("BS-DEV-qualquer") is True


def test_connectors_exist():
    assert hasattr(mcp_erp.ErpConnector, "tools")
    assert hasattr(mcp_crm.CrmConnector, "tools")
    assert hasattr(mcp_rh.RhConnector, "tools")


def test_installer_callable():
    assert callable(installer.create_profile)


if __name__ == "__main__":
    test_license_dev_key()
    test_connectors_exist()
    test_installer_callable()
    print("SMOKE TESTS PASSOU")
