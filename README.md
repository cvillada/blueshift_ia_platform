# BlueShift IA Platform (dev)

Camada empacotada sobre o Hermes-Agent (MIT) para entrega on-premise via Docker + license key.

## Setup
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
blueshift --help
```

## Comandos
- `blueshift init <cliente>` — cria profile do cliente
- `blueshift activate <chave>` — valida license key
- `blueshift status` — mostra estado do container
- `blueshift update` — checa atualizacoes aprovadas
