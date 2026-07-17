#!/usr/bin/env python3
"""CLI do BlueShift. Comandos: init, activate, status, update, portal."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from blueshift_layer import license_client, installer, update_client


def main():
    p = argparse.ArgumentParser(prog="blueshift", description="BlueShift IA Platform")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("init", help="Cria profile de cliente").add_argument("cliente")
    sub.add_parser("activate", help="Valida license key").add_argument("chave")
    sub.add_parser("status", help="Mostra estado do container")
    sub.add_parser("update", help="Checa atualizacoes aprovadas")

    portal_p = sub.add_parser("portal", help="Sobe o Portal do Cliente (Camada 4)")
    portal_p.add_argument("--host", default="0.0.0.0")
    portal_p.add_argument("--port", type=int, default=8080)
    portal_p.add_argument("--debug", action="store_true")

    sub.add_parser("mcp", help="Sobe o servidor MCP stdio (conectores CRM/RH/ERP)")

    args = p.parse_args()
    if args.cmd == "init":
        installer.create_profile(args.cliente)
    elif args.cmd == "activate":
        ok = license_client.validate(args.chave)
        print("LICENSE", "OK" if ok else "INVALIDA")
    elif args.cmd == "status":
        print("BlueShift status: container ativo (modo dev)")
    elif args.cmd == "update":
        update_client.check()
    elif args.cmd == "portal":
        from blueshift_layer.portal import create_app

        app = create_app()
        print(f"[portal] BlueShift Client Portal em http://{args.host}:{args.port}/portal")
        app.run(host=args.host, port=args.port, debug=args.debug)
    elif args.cmd == "mcp":
        from blueshift_layer.connector_pack.mcp_server import run as run_mcp

        run_mcp()
    else:
        p.print_help()


if __name__ == "__main__":
    main()
