# Estrutura do projeto

```
accuchek-linux/
├── AGENTS.md                 # instruções para o agente (ler primeiro)
├── TODO.md                   # lista de tarefas com checkbox
├── opencode.json             # permissões do opencode para este projeto
├── requirements.txt          # pyusb, construct, pytest
├── README.md                 # (a criar) como rodar + regra udev
├── docs/
│   ├── contexto.md           # contexto original do projeto (Fases 1–2)
│   ├── implementacao.md      # plano original (Fases 3–4) + diretrizes
│   ├── estrutura.md          # este arquivo
│   ├── descriptor.txt        # descritor USB capturado (lsusb -v)
│   ├── protocol-notes.md     # confirmado vs. assumido
│   └── captures/             # .pcap + .hex de cada sessão
├── src/
│   ├── __init__.py
│   ├── device.py             # wrapper pyusb (único que importa `usb`)
│   ├── phdc.py               # constantes + encode/decode (puro, testável)
│   ├── association.py        # handshake de associação
│   ├── transfer.py           # GET_INFO + TRIG_XFER + loop de segmentos
│   ├── parser.py             # bytes → dataclasses (sem I/O)
│   └── cli.py                # entrypoint: python -m src.cli dump --out data.json
└── tests/
    ├── test_parser.py
    ├── test_phdc.py
    └── test_device.py        # com mock, sem hardware
```

## Responsabilidades

| Módulo | Pode | NÃO pode |
|---|---|---|
| `device.py` | importar `usb`/pyusb, fazer I/O | conter lógica de protocolo |
| `phdc.py` | constantes e funções puras | fazer I/O |
| `association.py` / `transfer.py` | orquestrar APDUs | decodificar registros |
| `parser.py` | decodificar bytes | fazer I/O, falar com o dispositivo |
| `cli.py` | argument parsing, I/O de arquivo | conter lógica de protocolo |
