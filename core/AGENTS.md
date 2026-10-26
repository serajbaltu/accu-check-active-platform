# AGENTS.md — Accu-Chek Active (Roche) no Linux

Instruções operacionais para agentes de IA trabalhando neste repositório.
Leia este arquivo **antes** de tocar em qualquer código.

---

## 1. O que é este projeto

Engenharia reversa do protocolo USB do glicosímetro **Roche Accu-Chek Active**
(VID `0x173a`, PID `0x21cc`) para ler registros de glicemia no Linux.

Objetivo final: um cliente Python que despeja as leituras em JSON/CSV.

## 2. Documentos do repositório

| Arquivo | Conteúdo |
|---|---|
| `docs/contexto.md` | Contexto original: o que já se sabe do dispositivo, objetivo, Fases 1–2 |
| `docs/implementacao.md` | Plano original: Fases 3–4, diretrizes técnicas, entregáveis, segurança |
| `docs/estrutura.md` | Estrutura de pastas planejada |
| `docs/descriptor.txt` | Descritor USB capturado (`lsusb -v`) |
| `docs/protocol-notes.md` | O que foi **confirmado** vs. o que foi **assumido** do Tidepool |
| `docs/estudos.md` | Literatura clínica (TIR, GMI, CV, metas) + limitações SMBG vs. CGM |
| `docs/captures/` | `.pcap` + `.hex` de cada sessão de teste (**só no disco** — contêm dado de saúde e a série; ver regra 5) |
| `TODO.md` | Lista de tarefas com checkbox — consulte e atualize |
| `src/` | Código Python |
| `tests/` | Testes |

## 3. Fatos já CONFIRMADOS no hardware (não re-descubrir)

Capturados nesta máquina em 2026-10-21, com o aparelho conectado:

```
Bus 001 Device 006: ID 173a:21cc Roche Accu-Chek Active USB
        (o número do device muda a cada reconexão — usar `lsusb | grep 173a`)
bcdUSB 2.00, bcdDevice 0.06
iManufacturer 1 = "Roche Diagnostics GmbH"
iProduct      2 = "Accu-Chek Active USB"
iSerial       0 = (ausente)
bNumConfigurations = 1, bNumInterfaces = 1
Interface 0: bInterfaceClass 15 (PHDC), SubClass 0, Protocol 0
  Descritores de classe: "04 20 02 00" (CDC header, bcdCDC 2.00)
                          "04 21 01 08" (PHDC device descriptor, bcdCDC 1.8)
Endpoints (bulk, 64 bytes cada):
  EP 0x01 OUT (bulk, 64 bytes)  <- envio
  EP 0x82 IN  (bulk, 64 bytes)  <- recepção
Bus-Powered, MaxPower 100mA
```

Ponto crítico: `lsusb -t` mostra `If 0, Class=Personal Healthcare, Driver=[none]`.
**Nenhum driver do kernel está preso à interface** (o `usbhid` do teclado/mouse é outro
dispositivo). Portanto `detach_kernel_driver()` é um no-op aqui — chame mesmo assim,
por segurança, mas não é a causa de nenhum travamento.

O device node `/dev/bus/usb/001/006` é `root:root` com `other=r--` → **sem escrita
para o usuário comum**. Resolvido pela regra udev em `99-accuchek.rules`
(entregável do README).

## 4. Referência de protocolo (a fonte da verdade)

O protocolo é ISO/IEEE **11073-20601** (transport/PHDC) sobre **11073-10417**
(perfil de glicosímetro), codificação **MDER**.

Duas fontes, ambas já clonadas/disponíveis:

1. **`emogenet/accuchek`** (C++17 + libusb-1.0) — port do JS do Tidepool para o
   Accu-Chek **Guide** (PID `0x21d5`). É a melhor referência: tem o fluxo completo
   em `main.cpp` com hexdump de cada fase.
   - Clone de referência em `/tmp/opencode/accuchek` (não versionar aqui).
   - Upstream: https://github.com/emogenet/accuchek
2. **Tidepool `uploader`** — JS original (`lib/drivers/roche/accuChekUSB.js`).
   Repo: https://github.com/tidepool-org/uploader/tree/master/lib/drivers/roche
   - O JS **define a data/hora do aparelho** (SET_TIME). Não copiar isso:
     este projeto é **somente leitura**.
3. Artigo do `emogenet` em https://librenard.fr/wiki/books/apprendre-a-parler-a-un-glucometre/page/la-langue-du-lecteur-isoieee-11073
   (explica o fluxo APDU e a nomenclatura MDC).

### Fluxo APDU (confirmado pelo `main.cpp` do emogenet)

| # | Direção | Mensagem | Bytes-chave |
|---|---|---|---|
| 1 | IN | GET_STATUS (control transfer) | — |
| 2 | IN | pairing request (associação) | `E2 00` |
| 3 | OUT | pairing confirmation | `E3 00` + payload de 44 bytes |
| 4 | IN | config info (extended config) | `E7 00` … `0D 1C` |
| 5 | OUT | config received confirmation | `E7 00` + `02 01` + `0D 1C` + `40 00` |
| 6 | OUT | MDS attribute request (GET handle 0) | `E7 00` + `01 03` |
| 7 | IN | MDS response (modelo, serial, hora) | `E7 00` + `02 03` |
| 8 | OUT | action request GET_INFO | `E7 00` + `01 07` + `0C 0D` |
| 9 | IN | action response | `E7 00` + `02 07` |
| 10 | OUT | action request TRIG_XFER | `E7 00` + `01 07` + `0C 1C` |
| 11 | IN | segment stream (loop) | `E7 00` + `02 01` + `0D 21` |
| 12 | OUT | segment ACK | `E7 00` + `02 01` + `0D 21` + `00 80` |
| 13 | OUT | release request | `E4 00` + `00 00` |
| 14 | IN | release response | `E5 00` |

**Invoke-id**: campo de 2 bytes no offset 6 de todo APDU de dados `E7 00`. A próxima
pergunta deve usar `invokeId_atual + 1`. Errar aqui faz o aparelho **abandonar
silenciosamente** — é o erro nº 1 em reimplementações.

**Fase 10b (medida, não documentada pelo emogenet)**: a resposta ao TRIG_XFER
é um APDU de **22 bytes** — `action-type` no offset 14 e `data-response` no
offset 20. Valores: `0` = sucesso, `1` = "no such segment", `2` = "try again
later", `3` = **segmento vazio** (não há o que ler), `512` = falha ao recuperar
o segmento.

**Layout do registro (MEDIDO no Active, não copiado do Guide)**: offset 30 =
nº de entradas (uint16 BE); offset 32 = status do segmento (bit `0x40` =
último). Cada entrada tem **10 bytes**, começando no **offset 36**:

```
+0..+1  ano em BCD (século, ano)   ex.: 20 20 -> 2020
+2      mês    (BCD)
+3      dia    (BCD)
+4      hora   (BCD)
+5      minuto (BCD)
+6      segundo (BCD)
+7      0x00 (reservado)
+8..+9  valor uint16 BE mg/dL
```

O Guide (`0x21d5`, usado pelo `emogenet`) tem **12 bytes** na base **34**, **sem**
o segundo, valor em `+14` e status em `+16`. **Não copiar os offsets do C++ para
o Active** — as datas ficam deslocadas em 2 bytes.

**Resposta do MDS (data-choice `02 03`)**: a lista de atributos começa no
**offset 18** (não é um "config info"): `[14:16]` = nº de atributos,
`[16:18]` = comprimento da lista, e cada atributo é `[class(2)][size(2)][valor]`.
O `MODEL` traz duas cadeias MDER (`"Roche"`, `"2102"`); o `PROD_SPECN` traz a
lista `[contagem(2)][comprimento-total(2)]` + entradas
`[tipo(2)][idioma(2)][tamanho(2)][texto]` (tipo 1 = serial-number, 5 = fw-revision).

**Transporte (medido)**: o `pyusb.read()` devolve **1 pacote de 64 bytes** — o
APDU precisa ser reassemblado (o config info tem 270 bytes = 5 pacotes). O
Active **reenvia** o `E2 00` periodicamente (~1 s) enquanto espera a
confirmação: 4 ZLPs vieram antes dele na captura real. Não é preciso replugar
o cabo; basta manter a sessão de leitura aberta. O aparelho **cai do bus** se a
sessão for morta no meio do handshake.

**Valores fora de escala** (Tidepool): `0x07FE` = +INF → 601 mg/dL;
`0x0802` = −INF → 9 mg/dL. Atenção: existe também uma leitura **real** de
9 mg/dL no aparelho — a flag `out_of_range` é que distingue os dois casos.

## 5. Regras invioláveis

1. **Somente leitura.** Nunca enviar SET_TIME (`0C 17`), nem qualquer comando de
   escrita, calibração, reset ou atualização de firmware. Se um byte Ambíguo
   sugerir escrita → **ABORTAR e consultar o usuário**.
2. **Comandos permitidos**: `E2 00` (associação), `E3 00` (confirmação),
   `E4 00`/`E5 00` (release), `E7 00` com `01 03` (GET),
   `E7 00` com `01 07` + `0C 0D`/`0C 1C` (GET_INFO / TRIG_XFER),
   `E7 00` com `02 01` (ACKs de confirmação).
3. **Nunca** enviar `E6 00` (abort) nem `0C 17` (SET_TIME).
4. **Logar tudo**: todo byte enviado/recebido em hexdump com timestamp monotônico
   e direção. É o que permite comparar com o `.pcap` do usbmon.
5. **Preservar** cada `.pcap`/`.hex` de sessão em `docs/captures/sessao-*/`
   — mas essas pastas **não entram no git** (dado de saúde + série do
   aparelho). O que é publicado é o transcript sintético, gerado por
   `tools/make_synthetic_transcript.py`.
6. **Timeout generoso**: 5000 ms (handshake do aparelho é lento).
7. **Python + pyusb** é o alvo. Libusb-1.0 já está instalado
   (`/usr/lib/x86_64-linux-gnu/libusb-1.0.so.0`).
8. Ao concluir uma tarefa: **atualizar `TODO.md`** e rodar lint/typecheck/testes.

## 6. Convenções de código

- Python 3.12. Layout `src/` conforme `docs/estrutura.md`.
- Type hints em todas as funções públicas. Docstring em português.
- `device.py` isola pyusb: `find_device()`, `open_device()`, `claim()`,
  `bulk_out()`, `bulk_in()`, `close()`. O resto do código **nunca** importa `usb`
  diretamente — facilita testar com mock.
- `phdc.py` só contém constantes e funções puras de encode/decode (testáveis
  sem hardware). Cada constante com comentário indicando a fonte
  (Tidepool / emogenet / ISO 11073-20601).
- `parser.py` só recebe bytes e devolve dataclasses. Nada de I/O.
- `analysis.py` só recebe registros e devolve métricas. Nada de I/O, nada de
  HTML, nada de rede.
- `charts.py` só devolve **strings SVG**. Nada de I/O, nada de matplotlib.
- `report.py` monta o HTML (CSS inline, sem `<script>`, sem referência
  externa) e o resumo de terminal.
- Logs em `logging`, formato `[%(asctime)s.%(msecs)03d] %(levelname)s %(name)s: %(message)s`.
- Hexdump: 16 bytes/linha, offset, ASCII à direita.

## 6.1 Relógio do aparelho (achado e resolução de 2026-10-21)

O relógio interno do Active estava **~7 anos atrasado**: reportava sempre
`2019-11-12` enquanto a data real era `2026-10-21`. Medido em **6 pontos**
(4 dumps em 2 sessões, 12:19 → 14:00), o desvio era **constante ao
segundo**: **2535 dias, 11:06:32** — **deriva zero**, o relógio corria 1:1
com o real.

**Troca de bateria testada** (13:55→14:00): o relógio **não mudou** e os 121
registros seguem idênticos → o RTC **não** é alimentado pela bateria trocada
(há backup, ou o relógio foi configurado errado e seguia correndo). A
hipótese "bateria removida → data de fábrica" fica **refutada**.

**✅ RESOLVIDO pelo usuário** (14:05): data e hora ajustadas **no menu do
próprio aparelho** (não via USB). O `device_time` passou a `2026-10-21T14:05:20`
(real `14:05:50`) e depois `2026-10-21T14:06:09` (real `14:06:39`) →
desvio de apenas **30 s, constante, deriva zero**. Os 121 registros
antigos seguem idênticos.

Estado atual:
- ✅ medições **novas** já saem com a data correta (2026-10-21), **depois**
  dos 121 registros antigos (2020-2023) → linha do tempo coerente;
- ⚠️ os **121 registros antigos** continuam com o carimbo do relógio
  antigo (2020-2023). Como o relógio antigo corria 1:1 e só o *ponto de
  partida* estava errado (deslocamento constante de 2535 dias), os
  **intervalos, as taxas, as médias móveis e os valores em mg/dL** não são
  afetados; só as **datas absolutas** devem ser lidas como aproximadas;
- o relatório HTML detecta o dessincronismo sozinho
  (`src/report.py::_clock_note`, avisa só se o desvio > 24 h) — hoje ele
  **não** mostra o aviso.

⚠️ Não corrigir via USB: `SET_TIME` (`0C 17`) é **proibido** (regra 1 da
seção 5).

## 7. Permissões e ambiente

- Usuário `henrique` está nos grupos `sudo`, `plugdev`, `adm`, `docker`.
- A regra udev `99-accuchek.rules` **está instalada e validada**: o device node
  do Active fica `root:plugdev` com modo `0660` → o pyusb abre **sem sudo**
  (usuário no grupo `plugdev`).
- `sudo` **exige senha** → o agente não consegue elevar privilégio sozinho.
  Quando o usuário autorizar, grave a senha em arquivo com `chmod 600` e
  use `setsid nohup bash -c "exec sudo -S <cmd> < /tmp/opencode/.sudopass" ... &`
  (o timeout da ferramenta mata o grupo de processos se não for detached).
  ⚠️ **Nunca** escrever a senha em arquivo versionado, log ou commit.
- `debugfs` está montado em `/sys/kernel/debug` (rw), mas o diretório
  `usb/usbmon` só é legível por root.
- `tshark`/`dumpcap` **não instalados** — captura de fallback via
  `cat /sys/kernel/debug/usb/usbmon/Xu` (também exige root) ou via
  `dmesg`-based logging de driver.
- Regras udev permitidas em `opencode.json` (sudo `tee` em
  `/etc/udev/rules.d/99-accuchek.rules`).

## 8. Ambiente de teste

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # pyusb, construct, pytest, ruff

# verificação (sem hardware — deve passar sempre)
.venv/bin/python -m ruff check src tests
.venv/bin/python -m pytest tests/ -q          # 146 testes

# com o aparelho (precisa de permissão de escrita em /dev/bus/usb)
sudo .venv/bin/python -m src.cli --verbose probe
sudo .venv/bin/python -m src.cli dump --out data.json --include-device

# relatório e análise (não precisam de hardware; usam o data.json)
.venv/bin/python -m src.cli show   --data data.json
.venv/bin/python -m src.cli report --data data.json --out relatorio.html --open
```

O aparelho precisa estar **conectado** e na tela de transferência de dados.
Se a tela mostrar "transferindo dados", o aparelho já está no estado de
associação. O Active **reenvia** o `E2 00` a cada ~1 s, então não é preciso
reconectar o cabo — mas ele **cai do bus** se a sessão for encerrada no meio
do handshake, e nesse caso é preciso reconectar.

Regras de lint ficam em `pyproject.toml` (ruff). Rodar `ruff check --fix`
antes de commitar.
