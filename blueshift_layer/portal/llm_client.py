"""Client de LLM OpenAI-compatível da BlueShift (100% offline, sem libs externas).

Fala com qualquer endpoint OpenAI-compatible (LM Studio, vLLM, Ollama, etc.)
usando apenas urllib da biblioteca padrao — mantendo o padrao on-premise do
projeto (sem dependencias de rede pesadas no venv).

No Docker, o LM Studio roda no HOST (Mac do cliente), nao dentro do container.
Por isso, se a base_url aponta para 127.0.0.1/localhost, resolvemos para
host.docker.internal quando estivermos dentro de container.
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.error


def _resolver_host(base_url: str) -> str:
    """Se rodando em container e a URL for localhost, aponta pro host do Docker."""
    in_container = os.path.exists("/.dockerenv")
    if in_container and ("127.0.0.1" in base_url or "localhost" in base_url):
        return base_url.replace("127.0.0.1", "host.docker.internal") \
                       .replace("localhost", "host.docker.internal")
    return base_url


def chat(modelo: dict, mensagens: list[dict], max_tokens: int = 512,
         temperatura: float = 0.3) -> dict:
    """Envia chat completion. Retorna dict {ok, content, model, error}.

    `mensagens` no formato OpenAI: [{"role": "...", "content": "..."}, ...]
    """
    base = _resolver_host(modelo["base_url"]).rstrip("/")
    url = f"{base}/v1/chat/completions"
    payload = {
        "model": modelo["modelo"],
        "messages": mensagens,
        "max_tokens": max_tokens,
        "temperature": temperatura,
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    if modelo.get("api_key"):
        headers["Authorization"] = f"Bearer {modelo['api_key']}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            out = json.loads(resp.read().decode("utf-8"))
        content = out["choices"][0]["message"]["content"]
        return {"ok": True, "content": content, "model": modelo["modelo"], "error": None}
    except urllib.error.HTTPError as e:
        return {"ok": False, "content": "", "model": modelo["modelo"],
                "error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"ok": False, "content": "", "model": modelo["modelo"],
                "error": f"nao foi possivel conectar ao endpoint ({e.reason}). "
                         f"Confirme que o LM Studio / vLLM esta rodando em {base}."}
    except Exception as e:  # noqa: BLE001 - relatar erro ao usuario
        return {"ok": False, "content": "", "model": modelo["modelo"], "error": str(e)}


def health(modelo: dict) -> bool:
    """Checa se o endpoint responde (GET /v1/models)."""
    base = _resolver_host(modelo["base_url"]).rstrip("/")
    url = f"{base}/v1/models"
    headers = {}
    if modelo.get("api_key"):
        headers["Authorization"] = f"Bearer {modelo['api_key']}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001
        return False
