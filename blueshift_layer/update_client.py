#!/usr/bin/env python3
"""Update Client: checa e aplica atualizacoes a partir do Git (A4).

O BlueShift versiona a propria camada (connectors, skills, portal) por TAGS
git (v0.9.3, v0.9.4, ...). O servidor do cliente mantem um clone fixo do
repo (default /opt/blueshift/repo) e o update = git fetch + checkout da
tag aprovada + docker compose up -d --build (dados preservados — volumes
intactos).

Sem dependencias externas: usa subprocess + git CLI (instalado na imagem).

Fluxo:
  check()  -> versao instalada (git describe) vs disponivel (git ls-remote)
  apply()  -> roda update.sh <tag> em background (rebuild derruba o portal,
              entao responde na hora e o rebuild termina sozinho)
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

from . import __version__ as CURRENT_VERSION

REPO_DIR = os.getenv("BLUESHIFT_REPO_DIR", "/opt/blueshift/repo")
UPDATE_SCRIPT = os.getenv("BLUESHIFT_UPDATE_SCRIPT", "/opt/blueshift/repo/update.sh")
LOG_FILE = os.getenv("BLUESHIFT_UPDATE_LOG", "/opt/blueshift/update.log")


def _git(*args: str, cwd: str | None = None, timeout: int = 15) -> str:
    """Roda git e devolve stdout limpo. Levanta CalledProcessError em falha."""
    base = ["git"]
    if cwd:
        base += ["-C", cwd]
    return subprocess.check_output(base + list(args), text=True,
                                   stderr=subprocess.DEVNULL,
                                   timeout=timeout).strip()


def _repo_existe() -> bool:
    return os.path.isdir(os.path.join(REPO_DIR, ".git"))


def versao_instalada() -> str:
    """Tag git atual do repo (ex: v0.9.3) ou __version__ como fallback."""
    if _repo_existe():
        try:
            tag = _git("describe", "--tags", "--abbrev=0", cwd=REPO_DIR)
            if tag:
                return tag
        except Exception:  # noqa: BLE001 - fallback abaixo
            pass
    return CURRENT_VERSION


def _tags_remotas() -> list[str]:
    """Tags de versao (vX.Y.Z) disponiveis no remoto, mais recente primeiro.

    Se o remoto for inacessivel (repo privado sem credencial no container)
    e estivermos em dev, usa as tags LOCAIS como fallback — permite testar o
    fluxo completo sem depender de rede/credencial.
    """
    if not _repo_existe():
        return []
    try:
        out = _git("ls-remote", "--tags", "--refs", "origin", cwd=REPO_DIR)
        _origem = "remoto"
    except Exception:  # noqa: BLE001 - sem rede/remoto inacessivel
        if os.getenv("BLUESHIFT_DEV") != "1":
            return []
        try:
            out = _git("tag", cwd=REPO_DIR)
            _origem = "local (dev)"
        except Exception:  # noqa: BLE001
            return []
    tags = []
    for linha in out.splitlines():
        nome = linha.split("\t")[-1].rsplit("/", 1)[-1] if "\t" in linha else linha.strip()
        if nome.startswith("v"):
            tags.append(nome)
    # ordena por versao numerica (v0.9.10 > v0.9.9 > v0.9.3)
    def _chave(t: str):
        try:
            return tuple(int(p) for p in t.lstrip("v").split("."))
        except ValueError:
            return (0, 0, 0)
    return sorted(set(tags), key=_chave, reverse=True)


def _estado_container() -> str:
    """Status do container do portal: running/created/restarting/exited/?.

    'created' = container criado mas NUNCA iniciado — estado de update pela
    metade (o compose morreu entre criar e iniciar). A tela deve avisar.
    """
    try:
        return subprocess.check_output(
            ["docker", "inspect", "blueshift-platform",
             "--format", "{{.State.Status}}"],
            text=True, stderr=subprocess.DEVNULL, timeout=10).strip() or "?"
    except Exception:  # noqa: BLE001
        return "?"


def check() -> dict:
    """Retorna versao instalada vs disponivel no remoto git."""
    atual = versao_instalada()
    remoto = _tags_remotas()
    # 'aplicado': o checkout do repo pode ser mais novo que o codigo RODANDO
    # (imagem/container) — sinal de update baixado mas NAO aplicado (build ok
    # que nao trocou os containers, ou container 'Created' nunca iniciado).
    codigo = CURRENT_VERSION
    status = _estado_container()
    aplicado = (atual.lstrip("v") == codigo) and status != "created" \
        if atual.startswith("v") else True
    base = {
        "atual": atual,
        "codigo": codigo,
        "aplicado": aplicado,
        "container_status": status,
    }
    if not remoto:
        return {**base, "disponivel": False, "motivo": "remoto_indisponivel",
                "repo": REPO_DIR, "repo_ok": _repo_existe()}
    nova = remoto[0]
    return {
        **base,
        "disponivel": nova != atual,
        "disponivel_version": nova,
        "todas": remoto,
        "repo": REPO_DIR,
        "repo_ok": True,
    }


def apply(version: str | None = None) -> dict:
    """Aplica a atualizacao: update.sh <tag> em background (rebuild Docker).

    O rebuild recria o proprio container — por isso roda em background
    (nohup) e esta funcao responde na hora. Em dev (BLUESHIFT_DEV=1) faz
    dry-run (so mostra o comando), para nao derrubar o ambiente.
    """
    info = check()
    if not version:
        version = info.get("disponivel_version")
    if not version:
        return {"ok": False, "motivo": "nenhuma_versao_disponivel"}
    # Se o checkout ja esta na versao E o codigo rodando tambem, nada a fazer.
    # Se o checkout esta na versao mas o codigo NAO (update baixado nao
    # aplicado), permite RE-aplicar — troca os containers de verdade.
    if version == info.get("atual") and info.get("aplicado", True):
        return {"ok": False, "motivo": "ja_na_versao_atual", "versao": version}

    cmd = ["bash", UPDATE_SCRIPT, version]

    if os.getenv("BLUESHIFT_DEV") == "1":
        return {"ok": True, "dry_run": True, "versao": version,
                "mensagem": f"[dev] rodaria: {' '.join(cmd)} (rebuild simulado)"}

    if not os.path.isfile(UPDATE_SCRIPT):
        return {"ok": False, "motivo": "update_script_ausente",
                "erro": f"{UPDATE_SCRIPT} nao encontrado"}

    # Update via container IRMAO descartavel: rodar o update.sh DENTRO do
    # portal morre no meio — o rebuild recria o proprio portal e o processo
    # some (update pela metade: container 'Created' nunca iniciado). Um
    # container efemero (--rm, --entrypoint bash) executa o update.sh via
    # docker.sock: NAO e gerenciado pelo compose, sobrevive a recriacao do
    # portal e o update termina sozinho. COMPOSE_PROJECT_NAME via -e resolve
    # o self-replacement do update.sh em qualquer versao dele.
    _proj = ""
    try:
        _proj = subprocess.check_output(
            ["docker", "inspect", "blueshift-platform",
             "--format", '{{index .Config.Labels "com.docker.compose.project"}}'],
            text=True, stderr=subprocess.DEVNULL, timeout=10).strip()
    except Exception:  # noqa: BLE001 - fallback abaixo
        _proj = ""
    _proj = _proj or "blueshift_ia_platform"
    # Source do volume = caminho do repo NO HOST (o -v espera source no host;
    # REPO_DIR e o caminho DENTRO do container — usar como source montaria
    # pasta vazia e o update.sh sumiria: "No such file or directory").
    _host_repo = REPO_DIR
    try:
        out = subprocess.check_output(
            ["docker", "inspect", "blueshift-platform",
             "--format", '{{range .Mounts}}{{.Destination}}={{.Source}}\n{{end}}'],
            text=True, stderr=subprocess.DEVNULL, timeout=10)
        for linha in out.splitlines():
            dest, _, src = linha.partition("=")
            if dest == REPO_DIR and src:
                _host_repo = src
                break
    except Exception:  # noqa: BLE001 - fallback: usa REPO_DIR mesmo
        pass
    cmd = ["docker", "run", "--rm", "--entrypoint", "bash",
           "--network", f"{_proj}_default",
           "-v", "/var/run/docker.sock:/var/run/docker.sock",
           "-v", f"{_host_repo}:{REPO_DIR}",
           "-w", REPO_DIR,
           "-e", f"COMPOSE_PROJECT_NAME={_proj}",
           # git safe.directory via env (GIT_CONFIG_COUNT, git >= 2.31): o
           # container irmao roda como root sobre repo de dono 1000:1000 e o
           # git bloquearia por 'dubious ownership'. Via env garante que vale
           # MESMO quando o update.sh em execucao e o antigo (bash bufferiza).
           "-e", "GIT_CONFIG_COUNT=1",
           "-e", "GIT_CONFIG_KEY_0=safe.directory",
           "-e", f"GIT_CONFIG_VALUE_0={REPO_DIR}",
           "blueshift/platform:latest",
           f"{REPO_DIR}/update.sh", version]

    try:
        # background: o rebuild derruba o portal — o update termina sozinho
        # no container irmao (fora do ciclo de vida do portal)
        with open(LOG_FILE, "a", encoding="utf-8") as logf:
            logf.write(f"\n=== update {version} iniciado (container irmao) ===\n")
            proc = subprocess.Popen(
                cmd, stdout=logf, stderr=subprocess.STDOUT,
                start_new_session=True,  # sobrevive ao rebuild do portal
            )
        return {"ok": True, "versao": version, "pid": proc.pid,
                "mensagem": f"Atualizacao {version} iniciada em background "
                            f"(log: {LOG_FILE})"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "motivo": "falha_update", "erro": str(e)}


def ler_log(linhas: int = 60) -> str:
    """Ultimas linhas do log de update (para a tela Atualizacoes)."""
    try:
        with open(LOG_FILE, encoding="utf-8") as f:
            return "".join(f.readlines()[-linhas:])
    except OSError:
        return ""
