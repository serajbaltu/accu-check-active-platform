# Capturas de sessão

Uma subpasta por sessão: `sessao-01/`, `sessao-02/`, ...

Conteúdo de cada sessão:

| Arquivo | Origem |
|---|---|
| `*.pcap` | `sudo tshark -i usbmon1 -w sessao-01.pcap` |
| `usbmon.txt` | `sudo cat /sys/kernel/debug/usb/usbmon/001u > usbmon.txt` (fallback sem tshark) |
| `*.hex` | hexdump do nosso cliente (log com timestamp monotônico e direção) |
| `*.log` | log completo do cliente |

Regras:
1. **Nunca sobrescrever** uma sessão anterior.
2. Antes de cada teste, reconectar o cabo USB do aparelho (reinicia o ciclo de
   associação e limpa a fila IN).
3. O aparelho precisa estar na tela "transferindo dados".
4. Anotar na tabela de sessions (em `../protocol-notes.md`) o que foi tentado.

## ⚠️ O que é publicado e o que não é

As capturas de sessão contêm **leituras de glicemia** (dado de saúde) e o
**número de série** do aparelho. Por isso:

- as pastas `sessao-*` **não** entram no repositório público — continuam no
  disco, mas estão no `.gitignore`;
- o que **é** publicado está em `exemplo-sintetico/`, gerado por
  `tools/make_synthetic_transcript.py`.

O transcript sintético tem exatamente o mesmo formato de log das capturas
reais (mesmos `INFO`/`DEBUG`, mesmo hexdump de 16 bytes/linha, mesmos
offsets) — só que os bytes são os do dataset sintético. Ele é produzido
rodando o cliente contra um **dispositivo falso** que faz replay dos APDUs,
o que exercita o mesmo código de produção.

```bash
.venv/bin/python tools/make_synthetic_transcript.py
```

## Sessões (histórico das sessões reais, mantidas só localmente)

| Sessão | Data/hora | O que foi feito | Resultado |
|---|---|---|---|
| `sessao-01` | 2026-10-21 ~10:40 | Descoberta do layout do registro (10 B, base 36) a partir do hexdump | 121 registros (80 + 41) |
| `sessao-02` | 2026-10-21 13:54–13:55 | **Validação do cliente completo no hardware real**, 3 dumps consecutivos | 121 registros idênticos nos 3 dumps; `device_time` = `2019-11-12T02:48:35` |
| `sessao-03` | 2026-10-21 14:00–14:01 | **Teste da troca de bateria** (o usuário trocou entre 13:55 e 14:00), 2 dumps | 121 registros idênticos; relógio **inalterado** (deriva zero) — `device_time` = `2019-11-12T02:54:25` |
| `sessao-04` | 2026-10-21 14:05–14:06 | **Relógio ajustado no menu do aparelho** pelo usuário, 2 dumps | 121 registros idênticos; `device_time` = `2026-10-21T14:05:20` → `14:06:09` (desvio de 30 s, deriva zero) |
