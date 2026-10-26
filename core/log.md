# LOG — Diário de bordo do projeto Accu-Chek Active

> **Este arquivo existe porque a máquina tem quedas de energia frequentes.**
> Ele é o ponto de retomada: se a sessão for perdida, leia o bloco
> **ESTADO ATUAL** (no topo) e siga a partir de "Próximo passo".
>
> **Regra de ouro:** ao terminar qualquer bloco de trabalho, atualize o bloco
> `ESTADO ATUAL` e acrescente uma entrada no diário. Não deixe o estado
> apenas na conversa — a conversa morre, o arquivo não.
>
> ⚠️ **Este repositório vai ser publicado.** Por isso, a partir de
> 2026-10-21 14:30 este arquivo foi sanitizado: a senha do `sudo` foi
> removida, a série do aparelho virou `XXXXXXXXX` e os números de glicemia
> foram trocados pelos do **dataset sintético**. As capturas reais
> (`docs/captures/sessao-*`) saíram do git — continuam só no disco.

---

## ESTADO ATUAL

| Campo | Valor |
|---|---|
| **Data/hora** | 2026-10-21 ~15:45 |
| **Fase do projeto** | **Fases 0–7 concluídas** — cliente, relatório, publicação no GitHub e CI (verde) |
| **Última ação concluída** | **CI publicada e passando** (`gh run` → `success`, escopo `workflow` liberado); dump revalidado no hardware real: **121 registros**, relógio do aparelho com desvio de **31 s** |
| **Arquivos criados** | 26 + 3 fixtures + capturas `sessao-02/`, `sessao-03/` e `sessao-04/` (ver inventário abaixo) + `tools/` + `examples/` + `docs/captures/exemplo-sintetico/` + `.github/workflows/ci.yml` |
| **Hardware** | ✅ Conectado (Bus 001 Device 002) e **funcionando** — a regra udev dispensou o `sudo` |
| **Bloqueio atual** | 🟢 Nenhum. (O aparelho se desliga sozinho depois de um tempo de uso — o `dump` precisa ser rodado logo após a reconexão) |
| **Risco de perda de dados** | 🟢 Baixo — tudo que importa está em arquivo neste repositório |

### Próximo passo exato

1. **Rotacionar o PAT** que estava em texto claro no remote do repo
   `~/Área de trabalho/crm-vendas-supabase` (o remote já foi limpo para usar
   o credential helper do `gh`; a rotação em si é no GitHub →
   *Settings → Developer settings → Personal access tokens*).
2. (Opcional) Reexportar o PDF do relatório:
   `google-chrome --headless --print-to-pdf=relatorio.pdf relatorio.html`
3. (Opcional) Testar o `probe` e o `info` com o aparelho ainda na tela.
4. (Opcional) Ler o segmento `PMSegMeal` (11073-10417) para ter a marcação
   real de jejum/pós-prandial no lugar da heurística — exige um TRIG_XFER
   para o handle do segmento de refeições.
5. (Opcional) Investigar o porquê do relógio interno ter estado 7 anos
   atrasado (já resolvido: o usuário ajustou no menu; desvio atual = 31 s).
   **Nunca** corrigir com `SET_TIME`.
6. (Opcional) `git init` + primeiro commit — ✅ **feito** (`d5d81b5`).
7. (Opcional) `git remote add origin <url>` + `git push` para ter uma cópia
   fora desta máquina (que tem quedas de energia) — ✅ **feito**.
8. (Opcional) **Publicar no GitHub** como `henriquegouveia85/accu-chek-active-linux`
   (público) — ✅ **feito** (a história do git foi reescrita antes, porque o
   primeiro commit tinha as capturas reais dentro).

### Como retomar em uma sessão nova

```
leia este arquivo            ->  contexto completo
leia AGENTS.md               ->  regras invioláveis + fluxo APDU
leia TODO.md                 ->  o que falta
depois siga "Próximo passo exato" acima
```

Comandos para revalidar o ambiente (sem privilégio):

```bash
lsusb | grep 173a                    # aparelho conectado?
cd /home/henrique/Documentos/Accu-check
.venv/bin/python -m pytest tests/ -q   # deve dar 146 passed
.venv/bin/python -m ruff check src tests tools
```

---

## Inventário de arquivos

| Arquivo | Estado | O que é |
|---|---|---|
| `AGENTS.md` | ✅ completo | Instruções para o agente; fatos confirmados; regras invioláveis |
| `TODO.md` | ✅ completo | Lista de tarefas (Fases 0–6) com checkbox |
| `log.md` | ✅ ativo | Este diário de bordo |
| `opencode.json` | ✅ criado | Permissões de bash do opencode para este projeto |
| `requirements.txt` | ✅ criado | pyusb, construct, pytest |
| `.gitignore` | ✅ criado | pycache, venv, pcap |
| `docs/contexto.md` | ✅ renomeado | Contexto original (era "Contexto do projeto") |
| `docs/implementacao.md` | ✅ renomeado | Plano original (era "Implementação") |
| `docs/estrutura.md` | ✅ reescrito | Árvore de pastas (era "Mais contexto") |
| `docs/descriptor.txt` | ✅ gerado | Descritor USB capturado |
| `docs/protocol-notes.md` | ✅ escrito | Confirmado vs. assumido |
| `docs/captures/README.md` | ✅ criado | Convenção das capturas |
| `src/phdc.py` | ✅ escrito | Constantes + codec APDU (puro) |
| `src/parser.py` | ✅ escrito | Parser de config/segmento (puro) |
| `src/device.py` | ✅ escrito | Wrapper pyusb |
| `src/logging_utils.py` | ✅ escrito | Hexdump + logging |
| `src/association.py` | ✅ escrito | Handshake de associação (passos 1–9) |
| `src/transfer.py` | ✅ escrito | TRIG_XFER + loop de segmentos + release (passos 10–14) |
| `src/cli.py` | ✅ escrito | `dump` / `info` / `probe` / `show` / `report` |
| `src/analysis.py` | ✅ escrito | Métricas clínicas e estatísticas (puro, sem I/O) |
| `src/charts.py` | ✅ escrito | 7 gráficos SVG gerados em Python puro |
| `src/report.py` | ✅ escrito | Relatório HTML autocontido + resumo no terminal |
| `tests/test_phdc.py` | ✅ escrito | 6 APDUs conferidas byte a byte com o emogenet |
| `tests/test_parser.py` | ✅ reescrito | BCD, segmentos (10 B), base, config, GET, prod spec, fixtures reais |
| `tests/test_flow.py` | ✅ escrito | Aparelho falso: handshake + leitura + ACK + release |
| `tests/test_device.py` | ✅ escrito | Camada USB: fragmentação, ZLP, timeout, ciclo de vida |
| `tests/fixtures/*.hex` | ✅ sintético | Layout do Active (MDS response + 2 segmentos), com leituras fictícias |
| `tests/test_analysis.py` | ✅ escrito | Métricas clínicas: TIR, GMI, CV, tendência, perfis |
| `tests/test_charts_report.py` | ✅ escrito | SVG/HTML: estrutura, escapes, determinismo |
| `tests/` | ✅ 146 passando | `python -m pytest tests/ -q` |
| `docs/estudos.md` | ✅ escrito | Literatura compilada + limitações SMBG vs. CGM |
| `relatorio.html` | ✅ gerado | Relatório final (97 KB, 7 SVGs, 8 páginas no PDF) |
| `docs/captures/sessao-02/` | ✅ novo | Dump no hardware real (2026-10-21 13:55): `dump3.log` + `data.json` |
| `docs/captures/sessao-03/` | ✅ novo | Teste da troca de bateria (2026-10-21 14:00): `dump4.log` + `data.json` |
| `docs/captures/sessao-04/` | ✅ novo | Relógio ajustado no aparelho (2026-10-21 14:05): `dump5.log`, `dump5b.log` + `data.json` |
| `.venv/` | ✅ instalado | pyusb 1.3.1, construct 2.10.70, pytest 9.1.1, ruff 0.17.1 |
| `tools/make_synthetic_fixtures.py` | ✅ criado | Gera os fixtures sintéticos + `examples/data_sintetico.json` |
| `tools/make_synthetic_transcript.py` | ✅ criado | Gera o transcript sintético rodando o cliente contra um dispositivo falso |
| `examples/data_sintetico.json` | ✅ criado | Dataset de demonstração (121 leituras fictícias) |
| `docs/captures/exemplo-sintetico/` | ✅ novo | Transcript de protocolo **sintético** (o que é publicado) |

---

## Diário

### 2026-10-21 ~11:11 — Pedido inicial

Usuário pediu: verificar a pasta do projeto, criar `AGENTS.md` e `TODO.md`, e
pedir todas as permissões para iniciar o projeto.

**Achado:** a pasta tinha só 3 arquivos, com nomes em português e **sem
extensão**: "Contexto do projeto", "Implementação", "Mais contexto". Nenhum
código, nenhuma pasta `src/`/`tests/`/`docs/`.

### 2026-10-21 ~11:12 — Diagnóstico do hardware (Fase 1)

Rodei `lsusb`, `lsusb -v -d 173a:21cc`, `lsusb -t`, `dmesg`, inspeção do sysfs
e `getfacl`. Resultado (todo confirmado, nada de suposição):

```
Bus 001 Device 006: ID 173a:21cc Roche Accu-Chek Active USB
bcdUSB 2.00   bcdDevice 0.06
iManufacturer = "Roche Diagnostics GmbH"
iProduct      = "Accu-Chek Active USB"
iSerial       = ausente
1 configuração, 1 interface (bInterfaceClass 15 = PHDC, SubClass 0, Protocol 0)
Descritores de classe: "04 20 02 00" (CDC header) e "04 21 01 08" (PHDC 1.8)
EP 0x01 OUT bulk 64 B   |   EP 0x82 IN bulk 64 B
Bus-Powered, MaxPower 100mA
```

Três achados que mudam o plano:

1. **`Driver=[none]`** — nenhum driver de kernel está preso à interface
   PHDC. O `usbhid` que aparece no `lsusb -t` é do teclado/mouse (outro
   dispositivo). Consequência: `detach_kernel_driver()` é um **no-op** aqui;
   não é a causa de nenhum travamento. (O `hidraw2/3/4` também não são do
   glicosímetro.)
2. **Device node sem escrita**: `/dev/bus/usb/001/006` é `root:root` com
   `other=r--`. O `getfacl` não mostrou nenhuma ACL `uaccess` — a regra
   `70-uaccess.rules` do systemd só cobre PTP/gphoto/scanners, não PHDC.
   → pyusb **não abre o aparelho** sem elevação.
3. **`iSerialNumber` ausente** — não dá para identificar o aparelho pelo
   serial; o par VID/PID é a única chave. (PID `0x21cc` = Accu-Chek Active;
   o driver Windows da Tidepool mapeia `0x21d5`=Guide, `0x21cf`=Aviva Connect,
   `0x21d6`=Guide Me, `0x21d7`=Instant, `0x21d8`=ReliOn Platinum,
   `0x21db`=Guide Link. O nosso `0x21cc` **não está** nessa lista — é um
   modelo mais antigo, o que reforça a necessidade de confirmar os offsets.)

### 2026-10-21 ~11:13 — Descoberta da referência de protocolo

O plano original citava o JS do Tidepool, que é de 2013 e roda só em Chrome.
Procurei e achei algo muito melhor: **`emogenet/accuchek`** — port C++17/libusb
do *mesmo* driver JS, para o Accu-Chek **Guide**, com o fluxo APDU completo e
hexdump de cada fase. Clonei para `/tmp/opencode/accuchek` (fora do repositório,
para não versionar third-party).

Também encontrei o artigo do autor do `emogenet` (francês) em
`librenard.fr/wiki`, que explica a nomenclatura MDC e o papel do invoke-id.

**Decisão:** o `main.cpp` do `emogenet` passa a ser a **fonte da verdade** do
protocolo, e o TODO do Tidepool fica como referência secundária.

⚠️ Ressalva registrada: o `emogenet` é para o **Guide** (`0x21d5`). Nosso
aparelho é o **Active** (`0x21cc`). Mesmo protocolo (11073-20601), mas os
offsets do layout dos registros **podem diferir** e precisam ser confirmados
com bytes reais.

### 2026-10-21 ~11:14 — Renomeação dos documentos

| Antes | Depois | Motivo |
|---|---|---|
| `Contexto do projeto` | `docs/contexto.md` | nome autoexplicativo, extensão certa |
| `Implementação` | `docs/implementacao.md` | idem |
| `Mais contexto` | `docs/estrutura.md` | na verdade era a árvore de pastas |

Criei `docs/`, `src/`, `tests/`, `docs/captures/`.

### 2026-10-21 ~11:15 — Arquivos de fundação

- **`AGENTS.md`** — fatos confirmados (para não re-descobrir), fluxo APDU das
  14 fases, regras invioláveis (só leitura, nunca SET_TIME nem ABORT),
  convenções de código, permissões do ambiente.
- **`TODO.md`** — Fases 0–5 com checkbox, mais a **Fase 6** (relatório visual
  e análise clínica) adicionada depois, a pedido do usuário, com a
  precondição explícita "depois que o sistema rodar".
- **`opencode.json`** — regras de permissão de bash (broad primeiro, narrow
  depois; `sudo` só para comandos específicos; `rm -rf` negado).
- **`docs/descriptor.txt`** — saída real do `lsusb -v` + endpoints do sysfs.
- **`docs/protocol-notes.md`** — separação ✅confirmado / 🟡inferido / 🔴não
  verificado, com as fórmulas e o porquê de cada dúvida.
- **`docs/captures/README.md`** — convenção de nomenclatura das sessões.
- **`.gitignore`**, **`requirements.txt`**.

### 2026-10-21 ~11:17 — Dependências

`python3 -m venv .venv` + `pip install -r requirements.txt`:
pyusb 1.3.1, construct 2.10.70, pytest 9.1.1. **Não** instalado globalmente
(deixa o sistema do usuário limpo). numpy 1.26.4 já existia no sistema.

### 2026-10-21 ~11:18 — Perguntas de permissão (3 respostas do usuário)

| Pergunta | Resposta | Consequência |
|---|---|---|
| Como dar acesso ao `sudo`? | "me passe a senha" | esperando a senha |
| Como abrir o device node? | "rodar o cliente com sudo" | o CLI será executado como root |
| Como capturar o tráfego USB? | "usbmon via `cat`" | sem instalar tshark; `modprobe usbmon` + `cat /sys/kernel/debug/usb/usbmon/001u` |

Ambiente detectado: `DISPLAY=:0` (há sessão gráfica), `google-chrome` e
`firefox` instalados, **sem** matplotlib. → Para a Fase 6, o relatório HTML
autocontido é a melhor aposta (funciona sem backend gráfico do matplotlib).

### 2026-10-21 ~11:20 — Código inicial (`src/`)

- **`src/phdc.py`** — 93 constantes MDC extraídas automaticamente do
  `MDC_LIST` do `emogenet` (via script, sem digitação manual), tipos de APDU,
  data-choices, event-types, action-types, e o codec.
- **`src/logging_utils.py`** — hexdump 16 B/linha com offset e ASCII, log
  mon redirecional, `log_apdu` que identifica o tipo do APDU.
- **`src/device.py`** — wrapper pyusb. **Lê os endpoints do descritor** em vez
  de fixar 0x01/0x82 (o artigo do `emogenet` registra que isso varia entre
  modelos Roche). `detach_kernel_driver` defensivo. `control_get_status()`.
- **`src/parser.py`** — `parse_config` (objetos, handles, PM-Store, nº de
  segmentos), `parse_segment` (registros, status do segmento, flag "último"),
  `decode_bcd`, dataclasses `GlucoseRecord`/`Segment`/`ConfigInfo`.

### 2026-10-21 ~11:22 — Correção do layout BCD

O `emogenet` decodifica a data com `sprintf("%02X")` + `sscanf("%d")` — ou
seja, trata o byte como **BCD padrão** (tens no nibble alto). Ele não inverte
os nibbles; o comentário dele ("weird-ass encoding") é enganoso. Ex.: o byte
`0x21` → 21, `0x10` → 10, `0x08` → 08.

Implementei `decode_bcd()` corretamente: `(b >> 4) * 10 + (b & 0x0F)`.
Isso também corrige um bug do C++ original, que quebraria em qualquer nibble
maior que 9 (`0x1A` → "1A" → `sscanf` devolve 1).

### 2026-10-21 ~11:24 — Correção do layout dos APDUs

Relendo o `main.cpp` byte a byte, achei a regra correta dos campos de
comprimento. Antes eu tinha `LL = OO + 4`, o que está **errado**:

| APDU | OO (octet string) | LL |
|---|---|---|
| GET (`01 03`) | 12 | 14 |
| ACTION (`01 07`) | 18 | 20 |
| ACK de segmento (`02 01`/`0D 21`) | 28 | 30 |

→ **Regra: `LL = OO + 2`.** (O `LL` conta o campo `OO` + a octet string.)

E as estruturas de "data-append" (comprimento **primeiro**):

```
GET     : [len-atrib-list(2)][handle(2)][current-time(4)][atributos…]
ACTION  : [len-action-list(2)][handle(2)][action-type(2)][args…]
          com len-action-list = 4 + len(args)
EVENT   : [handle(2)][time(4)][event-type(2)][len(2)][conteúdo…]
```

Exceção registrada: o **ACK de configuração** do `emogenet` traz `LL`/`OO`
**2 bytes acima** do que a estrutura indica. Como ele funciona com o
aparelho real, mantive byte a byte igual e documentei a discrepância em
comentário no código.

Também extraí os argumentos das ações do `emogenet`:
`GET_INFO` → `00 06 00 01 00 02 00 00`; `TRIG_XFER` → `00 02 00 00`.

### 2026-10-21 ~11:25 — Escopo do relatório visual (Fase 6)

O usuário pediu que o programa final **mostre os resultados na tela, com
gráficos**, e que eu paralelamente levantasse **estudos científicos** sobre
glicemia. Ele pediu explicitamente que isso **entre no TODO.md para ser feito
depois que o sistema rodar** — feito, e a Fase 6 foi marcada como "DEPOIS que
o sistema rodar", com a precondition registrada.

Material levantado enquanto isso (vai para `docs/estudos.md` na Fase 6.5):

- **GMI (%) = 3.31 + 0.02392 × média mg/dL** — Bergenstal et al.,
  *Diabetes Care* 2018;41(11):2275-2284, DOI `10.2337/dc18-1581`.
  (Substituiu o "eA1c" porque a FDA prohibiu o nome — o GMI não promete
  igualar a A1c de laboratório.)
- **eA1c (ADAG)** = `(média + 46,7) / 28,7` — ainda vale comparar com o GMI.
- **Tempo em Faixa (TIR)** — Battelino et al., *Diabetes Care* 2019;42(6):1593-1603.
  Alvos: <54 (muito baixa, <4%), 54-69 (baixa, <1% e <15 min), 70-180
  (em faixa, >70%), 180-250 (alta, <25%), >250 (muito alta, <5%).
  ⚠️ O TIR pressupõe **CGM 24 h**; com glicosímetro é aproximação.
- **CV** > 36% sugere instabilidade.
- **eA1c (ADAG study)** — Nathan et al., *Diabetes Care* 2008;31(8):1571-1580.

> ⚠️ Ressalva de segurança a carregar até o fim do projeto: nada aqui é
> diagnóstico nem orientação de tratamento. As metas-alvo variam conforme o
> tipo de diabetes, o tratamento e asIndividual. O relatório precisa dizer
> isso de forma visível.

---

## Decisões tomadas (e por quê)

| # | Decisão | Motivo |
|---|---|---|
| D1 | `emogenet/accuchek` como fonte da verdade do protocolo | É a única impl known-good, em C++, com hexdump por fase |
| D2 | Ler os endpoints do descritor, não fixar 0x01/0x82 | Endpoints variam entre modelos Roche |
| D3 | `detach_kernel_driver` defensivo, mas sem esperar que resolva algo | A interface PHDC **não tem** driver preso (`Driver=[none]`) |
| D4 | Detectar a base dos registros por plausibilidade de data | Os offsets vieram do Guide (`0x21d5`); nosso é o Active (`0x21cc`) |
| D5 | Nunca SET_TIME (`0C 17`) nem ABORT (`E6 00`) | Projeto somente leitura; o Tidepool define a hora, mas isso altera o aparelho |
| D6 | Reporte visual só depois do sistema funcionar | Pedido explícito do usuário |
| D7 | Venv no projeto, sem instalar no sistema | Não sujar o Python do usuário |
| D8 | `usbmon` via `cat` em vez de `tshark` | Decisão do usuário; não exige instalar nada |
| D9 | Layout do Active **medido**, não copiado do Guide | 10 B na base 36 (≠ 12 B na base 34) — o `emogenet` é do `0x21d5` |
| D10 | Fixtures com bytes reais viram a referência dos testes | O parser passa a ser validado contra o aparelho, não contra suposição |
| D11 | Não instalar `tshark` | `usbmon` em texto bastou para confirmar a sessão |

## Perguntas em aberto

| # | Pergunta | Status |
|---|---|---|
| Q1 | Qual a senha do `sudo`? | ✅ (fornecida pelo usuário — **não registrada aqui**) |
| Q2 | O Active (`0x21cc`) usa o mesmo layout de registro de 12 B do Guide? | ✅ **Resolvido: não** — 10 B na base 36, com segundo em `+6` |
| Q3 | A data/hora do aparelho (MDC_ATTR_TIME_ABS) está em BCD ou em epoch MDER? | ✅ **BCD** (7 bytes) |
| Q4 | Há segmentos além do de glicemia (controle, erros, marcadores)? | ✅ Sim — `PMSegGluc`, `PMSegCtrl`, `PMSegErr`, `PMSegMeal` |
| Q5 | O aparelho reenvia o `E2 00` se o host demora? | ✅ Sim, ~1 s |
| Q6 | O que significam os 2 bytes reservados em `+7` do registro? | 🔴 não investigated (parecem zerar sempre) |

---

## histórico de renomeações

| Antes | Depois | Quando |
|---|---|---|
| `Contexto do projeto` | `docs/contexto.md` | 2026-10-21 11:14 |
| `Implementação` | `docs/implementacao.md` | 2026-10-21 11:14 |
| `Mais contexto` | `docs/estrutura.md` | 2026-10-21 11:14 |
| — | `AGENTS.md`, `TODO.md`, `log.md` | 2026-10-21 11:15+ |
| — | `opencode.json`, `requirements.txt`, `.gitignore` | 2026-10-21 11:15 |
| — | `docs/descriptor.txt`, `docs/protocol-notes.md`, `docs/captures/README.md` | 2026-10-21 11:15 |
| — | `src/phdc.py`, `src/parser.py`, `src/device.py`, `src/logging_utils.py` | 2026-10-21 11:20 |
| — | `src/association.py`, `src/transfer.py`, `src/cli.py` | 2026-10-21 ~11:25 |
| — | `tests/test_phdc.py`, `tests/test_parser.py`, `tests/test_flow.py` | 2026-10-21 ~11:25 |
| — | `tests/test_device.py`, `tests/fixtures/*.hex` | 2026-10-21 ~12:40 |

---

## Diário de bordo — 2026-10-21 ~11:30

**O que foi feito nesta última bloco:**

1. Escritos `src/association.py`, `src/transfer.py`, `src/cli.py` — o fluxo
   completo das 14 fases do handshake, do `E2 00` ao `E5 00`.
2. Escritos `tests/test_phdc.py`, `tests/test_parser.py` → **43 testes verdes**.
3. Escrito `tests/test_flow.py` com um `FakeDevice` (aparelho simulado que
   devolve bytes crafted) → 3 falhas na primeira execução, **todas corrigidas**:
   - o contador de objetos do config info é lido no **offset 24** (não 4) — o
     teste construía o buffer no offset errado;
   - o `action-type` do APDU de dados fica no **offset 14**, não 10 (10 é o
     comprimento da lista de argumentos da ação);
   - a associação envia **4** APDUs (assoc response, config confirmation,
     GET dos atributos MDS, GET_INFO), não 3 — o teste esquecia o GET_INFO.
4. Estado final: **49 testes passando**.
5. `python -m src.cli --help` e `python -m src.cli dump` sem privilégio:
   o aparelho **é encontrado**, e a falha é exatamente a esperada —
   `[Errno 13] Access denied (insufficient permissions)` ao fazer
   `set_configuration`, com a dica de rodar com `sudo` ou instalar a regra udev.

**Bugs reais de protocolo corrigidos no caminho** (importam para o hardware):

| Bug | Correção |
|---|---|
| `LL` (length) calculado como `OO` | `LL = OO + 2` |
| `length-of-content` ausente nos event-reports | inserido (offset 12 do payload de dados) |
| `00 80` do ACK de segmento fora do conteúdo | vai **dentro** do conteúdo: len-contents = 12, len-content = 22 |
| BCD decodificado como "nibbles trocados" | BCD **padrão**: `(b>>4)*10 + (b&0x0F)`; o truque do emogenet (`%02X` + `sscanf %d`) quebra com nibble > 9 |
| Parser ignorava o ano `yy` | ano = `cc*100 + yy` (fallback `2000+yy` se < 1900) |

**Estado do hardware:** o aparelho continua conectado (`lsusb` mostra
`173a:21cc`). Nada foi enviado ao aparelho ainda — todas as APDUs construídas
foram verificadas contra o `main.cpp` do emogenet, não contra bytes reais do
Active.

**Bloqueio:** ainda falta a senha do `sudo` (Q1). Sem ela não dá para ler
`/dev/bus/usb/001/006` nem para o `modprobe usbmon`.

---

## Diário de bordo — 2026-10-21 ~11:40 (higiene de código)

- Instalado `ruff` no `.venv` (0.17.1) e criado `pyproject.toml` com a
  configuração de lint (E, F, W, I, UP, B, S, BLE, PYI, SIM; `S101` liberado
  nos testes).
- Corrigidos os apontamentos do ruff:
  - `src/cli.py`: `__version__` agora é usada (`--version`);
  - `src/device.py`: anotações sem aspas, `__enter__` devolvendo `Self`,
    `except Exception` estreitado para `USBError/OSError` com log em debug;
  - `src/transfer.py`: import morto removido, `except Exception` estreitado;
  - `tests/test_flow.py`: `pytest.raises(ProtocolError)` em vez de
    `Exception`, variável não usada removida, `Self` no `__enter__`.
- Linhas longas (>88) quebradas em `device.py`, `parser.py`, `transfer.py`,
  `test_flow.py`.
- `requirements.txt` agora inclui `ruff`.
- **Estado: `ruff check src tests` → All checks passed!  `pytest` → 49 passed.**

Continua bloqueado na senha do `sudo` (Q1). Nada foi enviado ao aparelho.

---

## Diário de bordo — 2026-10-21 ~12:20 — **O APARELHO RESPONDEU** 🔥

A senha do `sudo` chegou. Com ela, `sudo modprobe usbmon`
funcionou e `/sys/kernel/debug/usb/usbmon/` ficou legível. Aí começam as
descobertas que mudaram o projeto.

### 1. O aparelho **reenvia** o pedido de associação

O plano original dizia (com base no `emogenet`) que o Accu-Chek manda o
`E2 00` **uma única vez**, logo após a conexão USB — e que, se o host não
estivesse ouvindo, o pedido se perdia.

**Isso é falso para o Active.** O aparelho reenvia o `E2 00` periodicamente
(≈ 1 s) enquanto espera a confirmação. Na captura real aparecem **4 ZLPs**
antes do `E2 00` chegar. → `_read_pairing_request()` foi reescrito: o
importante é **manter a sessão de leitura aberta**, não replugar o cabo.

⚠️ O aparelho **cai do bus** se a sessão for morta no meio do handshake.

### 2. `pyusb.read()` devolve **1 pacote de 64 bytes**, não o APDU inteiro

O `bulk_transfer` do `emogenet` (libusb) junta o transfer inteiro; o pyusb
devolve só um pacote. O config info do Active tem **270 bytes** = 5 pacotes.
Sem acumular, o parser lia lixo.

→ `Device.read_apdu()` (novo) acumula pacotes até ter `LL + 4` bytes
(`LL` = campo de comprimento no offset 2, big-endian), com teto de 5 leituras
vazias seguidas (ZLP) e timeout de 5000 ms.

### 3. O handshake **completo** rodou no aparelho real

`docs/captures/sessao-01/dump2.log` tem a sessão inteira, com hexdump de
tudo. As 14 fases do `AGENTS.md` foram observadas, uma a uma:

| Fase | O que aconteceu (bytes reais) |
|---|---|
| 1 | `GET_STATUS` (control transfer) → `00 00` |
| 2 | 4 ZLPs, depois `E2 00` (54 bytes) |
| 3 | `E3 00` + 44 bytes de pairing confirmation |
| 4 | **config info de 270 bytes lidos em 5 pacotes** → 5 objetos: METRIC_NU h1, METRIC_NU h2, METRIC_ENUM h3, METRIC_ENUM h4, PMSTORE h5 (`num_segments=4`) |
| 5 | `E7 00` + `02 01` + `0D 1C` + `40 00` |
| 6 | `E7 00` + `01 03` (GET, handle 0) |
| 7 | **resposta do MDS: 206 bytes** → modelo, serial, hora, etc. |
| 8 | `E7 00` + `01 07` + `0C 0D` (GET_INFO) |
| 9 | action response (422 bytes) |
| 10 | `E7 00` + `01 07` + `0C 1C` (TRIG_XFER) |
| 10b | **cabeçalho de 22 bytes** (action-type@14, data-response@20) — fase que faltava no código |
| 11 | **2 segmentos**: 836 bytes (80 registros) e 446 bytes (41 registros) |
| 12 | ACK de segmento (`E7 00` + `02 01` + `0D 21` + `00 80`) |
| 13–14 | `E4 00` + `00 00` → `E5 00` |

**Total: 121 leituras** no aparelho.

### 4. ⚠️ O layout do registro do Active é **diferente** do Guide

O `emogenet` (que é do **Guide**, `0x21d5`) assume registro de **12 bytes**
na base 34. No **Active** (`0x21cc`) a medição nos bytes reais deu:

```
offset 36 + 10 bytes por registro
+0..+1  ano em BCD (século, ano)    ex.: 20 20 -> 2020
+2      mês    (BCD)
+3      dia    (BCD)
+4      hora   (BCD)
+5      minuto (BCD)
+6      segundo (BCD)      <-- o Guide não tem isto
+7      0x00 (reservado)
+8..+9  valor em mg/dL (uint16 big-endian)
```

Diferenças: **10 bytes** (não 12), base **36** (não 34), **segundo** existe,
**valor em +8** (não +14), e **não há status por registro** (o Guide tem 2
bytes de status em +10/+11 — no Active, o `status` do registro é sempre 0).

### 5. A resposta do MDS **não** é uma "config info"

O `parse_mds_info` original reaproveitava o `parse_config` e estourava:
*"config info truncado no offset 12374 (de 21103 objeto(s))"* — porque a
resposta a um GET tem outro layout.

Medido nos bytes reais (APDU de 210 bytes):

```
[0:2]   e7 00        APDU type
[2:4]   00 ce        LL = 206
[4:6]   00 cc        octet-string length
[6:8]   00 01        invoke-id
[8:10]  02 03        data-response = GET
[10:12] 00 c6        length
[12:14] 00 00        handle 0
[14:16] 00 08        nº de atributos = 8
[16:18] 00 c0        comprimento da lista de atributos = 192
[18:20] 09 28        classe do atributo 1 = MDC_ATTR_ID_MODEL
[20:22] 00 0e        tamanho = 14
[22:36] 00 06 "Roche" 00 00 04 "2102"   <-- duas cadeias MDER
```

→ `parse_get_response()` novo: lista de atributos no **offset 18**, cada um
`[class(2)][tamanho(2)][valor]`.

Os 8 atributos: `MODEL`, `SYS_ID`, `DEV_CONFIG_ID`, `PROD_SPECN`,
`TIME_ABS`, `MDS_TIME_INFO`, `REG_CERT_DATA_LIST`, `SYS_TYPE_SPEC_LIST`.

**Modelo = `2102`**, **serial = `XXXXXXXXX`** (vem do `PROD_SPECN`:
`"serial-number: XXXXXXXXX"`), **firmware = `V02.04`**, relógio interno do
aparelho = `2019-11-12 01:13:19` (desatualizado — e **não** foi corrigido:
o projeto é somente leitura).

⚠️ O `PROD_SPECN` do Active **não** segue o layout do `utils.js` do Tidepool
(o JS lê `type@+4` e `len@+8`; no Active isso dá lixo a partir da 2ª
entrada). O layout real medido é:

```
[contagem(2)][comprimento-total(2)]
[tipo(2)][?2 (idioma)][tamanho(2)][texto(tamanho)]   x contagem
```

com `tipo` = 1 → `serial-number`, 5 → `fw-revision` (tabela `prd_spec_type`
do ISO 11073-20601, a mesma do Tidepool).

---

## Diário de bordo — 2026-10-21 ~12:40 — Parser migrado e validado

- `src/parser.py` reescrito para o layout real: `RECORD_SIZE = 10`,
  base 36, segundo em `+6`, valor em `+8`, sem status por registro.
- `parse_get_response()` e `parse_production_spec()` novos.
- `src/association.py`: `parse_mds_info` reescrito (não usa mais
  `parse_config`); docstring de `_read_pairing_request` corrigido (o aparelho
  **reenvia** o `E2 00`).
- `src/phdc.py`: constante `MDC_ATTR_ID_PROD_SPECN` adicionada.
- **Fixtures com bytes reais** em `tests/fixtures/` (`mds_response.hex`,
  `segment_80.hex`, `segment_41.hex`) — agora os testes do parser rodam
  contra dados de verdade, não só sintéticos.
- `tests/test_parser.py` reescrito (75 testes no total, todos verdes);
  `tests/test_flow.py` atualizado para o layout de 10 bytes e para a
  resposta de GET real.
- `ruff check src tests` → **All checks passed!**

**Validação cruzada:** um script reconstruiu os APDUs a partir do
hexdump de `dump2.log` e rodou o parser novo em cima deles — resultado:
**80 + 41 = 121 registros**, todos com data/valor plausíveis, e a
identificação do aparelho (modelo `2102`, série `XXXXXXXXX`) bate.

**Estado do hardware no fim deste bloco:** o aparelho **caiu do bus**
(`lsusb` não mostra mais `173a:21cc`) — provavelmente por causa de uma
queda de energia ou do cabo. Reconectar para rodar o `dump` final.

### Perguntas em aberto — respostas

| # | Pergunta | Resposta |
|---|---|---|
| Q1 | Qual a senha do `sudo`? | ✅ (fornecida pelo usuário — **não registrada aqui**) |
| Q2 | O Active usa o layout de 12 B do Guide? | ❌ **Não** — 10 B na base 36, com segundo |
| Q3 | A hora do MDS está em BCD ou epoch? | ✅ **BCD** (7 bytes: cc, yy, mm, dd, hh, mn, ss) |
| Q4 | Há segmentos além do de glicemia? | ✅ Sim — o config info tem 4 segmentos: `PMSegGluc`, `PMSegCtrl`, `PMSegErr`, `PMSegMeal`. Só o de glicemia é lido pelo TRIG_XFER |
| Q5 | O aparelho reenvia o `E2 00`? | ✅ **Sim**, ~1 s — não precisa replugar |
| Q6 | Existe alguma leitura de 9 mg/dL real? | ✅ Sim — o aparelho devolveu uma leitura de 9 mg/dL genuína, e o `-INF` também é clampado em 9; a flag `out_of_range` distingue os dois casos |

---

## Diário de bordo — 2026-10-21 ~12:45 — Fase 6: relatório visual e análise clínica

Objetivo do usuário: "mostrar os resultados na tela, com gráficos e análise
clínica/científica". Fechado sem depender do hardware, porque o `data.json`
já tem os **121 registros** reais da captura.

### Decisões

| # | Decisão | Por quê |
|---|---|---|
| D12 | **HTML autocontido com SVG gerado em Python puro** (sem matplotlib, sem JS, sem CDN) | O ambiente não tem matplotlib; SVG em Python puro dá um arquivo único, offline, compartilhável por e-mail e sem dependência de browser moderno. O PDF sai via `chrome --headless --print-to-pdf` |
| D13 | Separação em 3 módulos: `analysis.py` (números) / `charts.py` (desenho) / `report.py` (HTML) | `analysis.py` fica testável sem hardware e sem DOM; o HTML é só a casca |
| D14 | TIR calculado como **fração de leituras** na faixa, e rotulado como tal | Os dados são de **glicosímetro (SMBG)**, não de CGM. Chamar de "tempo em faixa" sem ressalva seria enganoso — o relatório diz explicitamente que o período noturno não existe no conjunto |
| D15 | Bandas do consensus: `<70`, `70–180`, `>180` (TIR); hipo grave `<54` | Battelino 2019 (`Diabetes Care` 42(8):1593-1603) |
| D16 | CV > 36% dispara alerta de variabilidade alta | Critério da SBD / consenso de variabilidade |
| D17 | Classificação jejum/pós-prandial por **heurística** (1ª leitura do dia = jejum; 2ª–4ª = pós-prandial) | O segmento `PMSegMeal` do 11073-10417 existe no config info mas **não** é lido pelo TRIG_XFER — a marcação real não está no payload de glicemia. Rotulado como heurística no relatório |
| D18 | Aviso clínico no topo e no rodapé do HTML | Requisito do `TODO.md` (Fase 6.4) e do bom senso: TIR/GMI de SMBG não substitui A1c de laboratório nem consulta |

### Módulos criados

- **`src/analysis.py`** (puro) — `Reading`, `Dataset`, `load_dataset`,
  `Descriptive`, `TimeInRange`, `GlycemicIndicators`, `Hypoglycemia`,
  `daily_means`, `linear_trend`, `hourly_profile`, `weekday_profile`,
  `classify_by_meal`, `dawn_effect`, `monitoring_profile`, `histogram`,
  `Analysis` + `alerts`. Constantes `MGDL_PER_MMOL = 18.0182`,
  `TIR_BANDS`, `WEEKDAY_NAMES`, `CV_HIGH_THRESHOLD = 36.0`.
- **`src/charts.py`** — SVG em Python puro: `time_series_svg`,
  `histogram_svg`, `boxplot_svg`, `daily_trend_svg`, `tir_donut_svg`,
  `heatmap_svg`, `day_strip_svg`, `stat_cards`. Paleta `COLOR_*`,
  `BAND_COLORS`/`BAND_LABELS`/`BAND_ORDER`.
- **`src/report.py`** — `render_html()` (CSS inline, 7 SVGs, sem `<script>`,
  sem referência externa), `write_report()`, `terminal_summary()`,
  `DISCLAIMER`, `REFERENCES` (14 fontes com DOI/PMID).

### CLI

```
python -m src.cli show   [--data data.json]
python -m src.cli report [--data data.json] [--out relatorio.html] [--title T] [--open]
```

`--open` usa `xdg-open` → `gio open` → `sensible-browser`, em fallback.

### Resultado com os 121 registros (dataset sintético de demonstração)

> Os números desta tabela vêm do **dataset sintético** de demonstração
> (`examples/data_sintetico.json`), com o mesmo layout de bytes do aparelho
> real. As leituras de verdade não são publicadas — ver
> `docs/estudos.md` e a nota de privacidade no `README.md`.

| Métrica | Valor |
|---|---|
| n | 121 (2024-01-01 → 2024-11-29) |
| média | 128,5 mg/dL (7,1 mmol/L) |
| mediana / DP | 131 / 29,7 mg/dL |
| **CV** | **23,1 %** (abaixo do limiar de 36 %) |
| GMI | 6,38 % |
| eA1c (ADAG) | 6,10 % |
| TIR (70–180) | 91,7 % |
| hipo < 70 / < 54 | 4,1 % / 0,8 % (5 eventos) |
| hiper > 180 | 4,1 % (5 eventos) |
| tendência | −0,019 mg/dL/dia, r² = 0,006 (59 dias) → **sem tendência** |
| monitoramento | intervalo mediano 15,3 h; 2,05 medições/dia; 59/334 dias (17,7 %) |

Interpretação honesta: os números de glicemia em si são bons (TIR alto, CV
baixo), mas a **cobertura é baixa** (17,7 % dos dias) — o que limita
fortemente qualquer conclusão sobre "tempo em faixa". Está escrito isso no
relatório e em `docs/estudos.md`.

### `docs/estudos.md`

Compilação com **14 referências verificadas** (Battelino 2019;42(8):1593-1603,
Bergenstal 2018;41(11):2275-2280, Nathan 2008;31(8):1571-1580,
Danne 2017;40(6):1591-1603, Beck 2019;42(3):400-413 [validação do TIR com
SMBG de 7 pontos], ADA Standards of Care 2026;49(Suppl.1):S132-S149,
SBD Ed. 2025, ISO 15197:2013) + seção explícita "o que este projeto não faz"
(SMBG ≠ CGM; TIR de leituras ≠ TIR de tempo; sem contexto de refeições
real; sem correção de erro do sensor; não substitui A1c de laboratório).

### Testes

- `tests/test_analysis.py` — 39 testes
- `tests/test_charts_report.py` — 25 testes
- Total: **139 testes verdes**; `ruff check src tests` → **All checks passed!**
- `relatorio.html` gerado (95 KB) e renderizado no Chrome headless →
  PDF de 8 páginas em `/tmp/opencode/report.pdf` (sem NaN, sem `<script>`,
  sem referência externa).

### Estado do hardware no fim deste bloco

O aparelho continua **fora do USB**. O relatório foi gerado a partir do
`data.json` reconstruído da captura real — os 121 registros são os mesmos
do `dump2.log`. Falta o `dump` com o aparelho fisicamente conectado para
fechar o ciclo de ponta a ponta.

---

## Diário de bordo — 2026-10-21 ~13:57 — Dump validado no hardware real

O usuário religou o aparelho ("depois de um tempo conectado ele se desliga")
e o dump foi executado com sucesso — **3 vezes seguidas**.

### Como foi

```bash
.venv/bin/python -m src.cli --verbose dump --out data.json --include-device --wait 20
```

**Sem `sudo`** — a regra udev `99-accuchek.rules` funcionou: o device node
ficou `root:plugdev` com modo `0660` e o usuário `henrique` está no grupo
`plugdev`. Confirmação:

```
crw-rw---- 1 root plugdev 189, 7 2026-10-21 13:54 /dev/bus/usb/001/008
```

### Resultado

| Dump | Momento | Registros | device_time |
|---|---|---|---|
| 1 | 13:54:31 | 121 (80 + 41) | `2019-11-12T02:47:59` |
| 2 | 13:54:52 | 121 (80 + 41) | `2019-11-12T02:48:20` |
| 3 | 13:55:07 | 121 (80 + 41) | `2019-11-12T02:48:35` |

Modelo `2102`, série `XXXXXXXXX` em todos. Os **valores são bit a bit
idênticos** entre os três dumps e entre eles e a reconstrução a partir do
hexdump de `docs/captures/sessao-01/dump2.log` (comparação programática:
`registros idênticos: True`).

→ **O parser está validado contra o aparelho real, não só contra a captura.**

### Novo achado: o relógio do aparelho está ~7 anos atrasado

O aparelho reportou `2019-11-12T02:47:59` / `02:48:20` / `02:48:35` enquanto
a data real era `2026-10-21 13:54` — **2535 dias** de diferença. A **taxa**
está certa (avançou 21 s em 21 s reais e 15 s em 15 s); o **ponto de partida**
está errado, provavelmente por bateria removida (data de fábrica).

Isso **não** invalida a análise:
- os **intervalos** entre medições, as taxas de variação, as médias móveis e
  os valores em mg/dL não dependem do relógio;
- as **datas absolutas** das leituras vêm do mesmo relógio e devem ser
  lidas como aproximação.

Ação tomada: o relatório HTML agora tem um aviso automático
(`src/report.py::_clock_note`) que compara o `device_time` com o momento da
leitura e, se a diferença for > 24 h, avisa:

> **Relógio do aparelho dessincronizado.** O aparelho reporta
> 2019-11-12T02:48:20, mas a leitura foi feita em 2026-10-21 13:54
> (2535 dias de diferença). As datas absolutas das medições vêm desse
> relógio interno e devem ser tratadas como aproximações; os *intervalos*,
> as taxas de variação e os valores em mg/dL não dependem dessa sincronia.

⚠️ `SET_TIME` (`0C 17`) continua **proibido** — projeto somente leitura.

### Captura preservada

`docs/captures/sessao-02/` → `dump3.log` (hexdump completo, 434 linhas) e
`data.json` (os 121 registros lidos do aparelho).

### Testes

- Novo `TestClockNote` em `tests/test_charts_report.py` (4 casos: dessincronizado,
  sincronizado, sem hora, hora inválida).
- Total: **146 testes verdes**; `ruff check src tests` → **All checks passed!**
- `relatorio.html` regenerado (97 KB, 7 SVGs, 0 `<script>`, 0 NaN) e
  renderizado no Chrome headless → PDF de **8 páginas**
  (`/tmp/opencode/report2.pdf`).

---

## Diário de bordo — 2026-10-21 ~14:02 — Teste da troca de bateria

O usuário trocou a bateria do aparelho entre as 13:55 e as 14:00. O
aparelho reconectou (Bus 001 Device 009, udev ok, `0660` `root:plugdev`).

### Resultado: o relógio NÃO mudou, e os registros NÃO mudaram

| Momento real | Hora do aparelho | Desvio |
|---|---|---|
| 12:19:51 (sessao-01) | 01:13:19 | 2535 d 11:06:32 |
| 13:54:31 (sessao-02) | 02:47:59 | 2535 d 11:06:32 |
| 13:54:52 (sessao-02) | 02:48:20 | 2535 d 11:06:32 |
| 13:55:07 (sessao-02) | 02:48:35 | 2535 d 11:06:32 |
| **14:00:07 (sessao-03, pós-bateria)** | 02:53:35 | 2535 d 11:06:32 |
| **14:00:57 (sessao-03, pós-bateria)** | 02:54:25 | 2535 d 11:06:32 |

- **Deriva zero**: em todos os intervalos, o avanço do relógio do aparelho é
  idêntico ao avanço do tempo real (1:34:40 → 1:34:40; 0:21 → 0:21;
  0:15 → 0:15; **5:00 → 5:00 atravessando a troca de bateria**).
- Os 121 registros saíram **idênticos** aos de antes da troca
  (`registros idênticos: True`).

### Conclusão (e hipótese refutada)

O RTC do Active **não** é alimentado pela bateria trocada: sobreviveu ao
ciclo de desligar/ligar sem perder um único segundo. Logo, ou existe um
elemento de backup (supercapacitor / outra célula), ou o relógio foi
simplesmente **configurado errado** em algum momento e segue correndo
perfeitamente desde então.

→ A hipótese anterior "bateria removida → data de fábrica" fica
**REFUTADA** como explicação para o estado atual. A hipótese que sobra é
"o relógio foi posto em 2019-11-12 uma vez e nunca mais ajustado".

### ⚠️ Consequência prática (importante para o usuário)

Com o relógio 7 anos atrás, **uma medição nova agora seria carimbada com
`2019-11-12`** — ou seja, *antes* de todos os 121 registros já existentes
(as datas de 2020 a 2023 do dataset real). Isso **embaralharia a linha do tempo** do
conjunto e distorceria a tendência, o perfil por hora e o mapa de calor.

**Ação recomendada:** ajustar data e hora **no menu do próprio aparelho**
(Configurações → hora). Isso não passa pelo USB e portanto **não** viola a
regra somente-leitura. Pelo USB, `SET_TIME` (`0C 17`) continua **proibido**.

### Captura preservada

`docs/captures/sessao-03/` → `dump4.log` (hexdump completo) + `data.json`.

### Documentos atualizados

`AGENTS.md` (§6.1), `docs/protocol-notes.md` (§3.5), `docs/estudos.md` (§4.5),
`README.md`, `TODO.md`, `docs/captures/README.md` — todos com o desvio
constante, o teste da bateria e a recomendação de ajustar o relógio pelo
menu do aparelho.

---

## Diário de bordo — 2026-10-21 ~14:08 — Relógio do aparelho sincronizado ✅

O usuário ajustou a data e a hora **no menu do próprio aparelho** (que não
passa pelo USB e portanto não viola a regra somente-leitura) e avisou
("feito"). Reconectado (Bus 001 Device 010) e 2 dumps de confirmação.

### Resultado

| Momento real | `device_time` do aparelho | Desvio |
|---|---|---|
| 14:05:50 | 2026-10-21T14:05:20 | **30 s** |
| 14:06:39 | 2026-10-21T14:06:09 | **30 s** |

- Desvio de **30 segundos, constante** → relógio **sincronizado** (dentro do
  ajuste feito no aparelho);
- **deriva zero**: avançou 49 s enquanto o real avançava 49 s;
- os 121 registros seguem **bit a bit idênticos** aos de antes;
- o relatório HTML **deixou de mostrar** o aviso de dessincronismo
  automaticamente (`_clock_note()` só avisa quando o desvio > 24 h) — o
  mecanismo de detecção funciona nos dois sentidos.

### Estado final do problema do relógio

| | Antes | Agora |
|---|---|---|
| `device_time` | `2019-11-12T…` | `2026-10-21T…` |
| Desvio | 2535 d 11:06:32 | 30 s |
| Deriva | 0 | 0 |
| Medições novas | seriam carimbadas **antes** dos registros antigos | saem **depois** → linha do tempo coerente |
| 121 registros antigos | com o carimbo antigo do relógio | inalterados (mesmo carimbo) |

Interpretação final: o relógio antigo corria 1:1 com o real, logo ele apenas
**deslocou a série inteira de 2535 dias**. As formas das curvas (tendência,
perfil por hora, mapa de calor) e todas as métricas glicêmicas (média, CV,
GMI, TIR) permanecem válidas; só a **âncora no calendário** das 121 leituras
antigas é aproximada. A âncora das leituras novas está correta.

### Captura preservada

`docs/captures/sessao-04/` → `dump5.log`, `dump5b.log` + `data.json`.

### Documentos atualizados

`AGENTS.md` (§6.1 — agora "achado e resolução"), `docs/protocol-notes.md`
(§3.5), `docs/estudos.md` (§4.5), `README.md`, `TODO.md`,
`docs/captures/README.md`.

---

## Diário de bordo — 2026-10-21 ~14:11 — Repositório git criado

O usuário escolheu "git init + commit" como próximo passo.

### Decisões

| # | Decisão | Por quê |
|---|---|---|
| D19 | Branch `main`, identidade **local** (`Henrique <henrique@localhost>`) | O git não tinha `user.name`/`user.email` globais; não quis write no `~/.gitconfig` sem o usuário pedir. Para mudar: `git config user.name "..."` |
| D20 | `data.json`, `relatorio.html` e `docs/captures/*/data.json` **fora** do histórico | São os dados de saúde em formato legível — e são regeneráveis com um comando (`src.cli dump` / `src.cli report`) |
| D21 | `SmartPix-Software-3.2.5r02.exe` (244 MB) ignorado via `*.exe` | Instalador do software oficial da Roche, não faz parte do projeto |
| D22 | Os hexdumps e os fixtures (`tests/fixtures/*.hex`) **entraram** | São a documentação do protocolo e são necessários para os testes rodarem sem hardware. ⚠️ Consequência honesta: os mesmos valores de glicemia estão no repositório em forma hexadecimal — a exclusão do JSON protege a leitura *legível*, não o dado em si |

### Resultado

```
$ git log --oneline
d5d81b5 Cliente Linux para o glicosímetro Roche Accu-Chek Active (173a:21cc)
 51 files changed, 14042 insertions(+)
```

`.git` = 636 KB. Árvore de trabalho limpa.

### Próximo candidato natural

`git remote add origin <url>` + `git push` — uma cópia fora desta máquina,
que tem quedas de energia frequentes (motivo de existirem o `log.md` e o
`AGENTS.md`).

---

## Diário de bordo — 2026-10-21 ~14:35 — **Sanitização para publicação**

O usuário decidiu publicar o projeto no GitHub como repositório **público**
(`henriquegouveia85/accu-chek-active-linux`). Isso exige remover do
repositório tudo que é dado de saúde ou identificador do aparelho.

### Decisões

| # | Decisão | Por quê |
|---|---|---|
| D23 | **Senha do `sudo` removida** do `log.md` (3 ocorrências) | Ela estava escrita em texto claro no diário, que ia para o repo público. A senha **nunca** foi registrada — só a menção de que ela existia |
| D24 | **Série do aparelho → `XXXXXXXXX`** (9 caracteres, mesmo formato) | Mantém o tamanho do campo (o parser depende do layout) sem identificar o aparelho |
| D25 | **Fixtures sintéticos** no lugar dos bytes reais | `tests/fixtures/*.hex` tinha as 121 leituras verdadeiras em hexadecimal. Agora são gerados por `tools/make_synthetic_fixtures.py` (seed fixa → reprodutível), com o **mesmo layout byte a byte**: cabeçalho de 36 B, registros de 10 B, 2 segmentos (80 + 41) |
| D26 | **Dataset de demonstração** (`examples/data_sintetico.json`) | Dá ao leitor algo para rodar `show`/`report` sem aparelho. 121 leituras fictícias, 60 dias medidos, 1 hipoglicemia grave + 4 leves, 1 leitura de madrugada (para o "efeite dawn" aparecer) |
| D27 | **Transcript sintético** (`docs/captures/exemplo-sintetico/`) | As capturas reais não podem ser publicadas. O transcript é gerado rodando o **código de produção** contra um dispositivo **falso** que faz replay dos APDUs — mesmo formato de log, mesmo hexdump, mesmas 14 fases |
| D28 | **Capturas reais fora do git** (`docs/captures/sessao-*` no `.gitignore`) | Continuam no disco (são a evidência do trabalho), mas não no repositório público. ⚠️ Elas já estavam no **primeiro commit** — por isso a história precisa ser reescrita antes do push |
| D29 | `_extract_serial` passou a **tirar o rótulo** (`"serial-number: "`) | Com a série anonimizada não há dígitos para extrair, e o log mostrava `serial=serial-number: XXXXXXXXX`. A mudança é inofensiva para aparelhos reais |

### Números do dataset sintético (substituem os reais na documentação)

| Métrica | Valor |
|---|---|
| n / período | 121 leituras, 2024-01-01 → 2024-11-29 |
| média / mediana | 128,5 / 131 mg/dL |
| DP / CV | 29,7 mg/dL / **23,1 %** |
| GMI / eA1c | 6,38 % / 6,10 % |
| TIR (70–180) | **91,7 %** |
| < 70 / < 54 mg/dL | 4,1 % (5) / 0,8 % (1) |
| > 180 mg/dL | 4,1 % (5) |
| cobertura | 59 dias de 334 (17,7 %) |
| tendência | −0,019 mg/dL/dia, r² = 0,006 → ruído |

### Verificação

```
146 passed  (pytest)
All checks passed!  (ruff check src tests tools)
relatorio.html: 95 KB, 7 SVGs, 0 <script>, 0 NaN
```

Auditoria: `grep` por senha do `sudo`, pela série do aparelho, pelas datas
das leituras e pelos BCD de 2020/2023 no transcript — **nada** fora das
pastas `sessao-*` (que não entram no git) e do `data.json` local (também
ignorado).

### Próximo candidato natural

Reescrever a história do git (branch órfã, um commit limpo), configurar a
identidade e a CI, e publicar em `henriquegouveia85/accu-chek-active-linux`.

---

## Diário de bordo — 2026-10-21 ~14:50 — **Publicado no GitHub**

O repositório foi criado e publicado:
**https://github.com/henriquegouveia85/accu-chek-active-linux** (público).

### O que foi feito

1. **Identidade git** trocada para `Henrique Gouveia <henriquegouveia85@gmail.com>`
   (a local `Henrique <henrique@localhost>` era placeholder).
2. **História reescrita**: o primeiro commit tinha as capturas reais dentro.
   Foi criada uma branch órfã (`git checkout --orphan`) com um commit
   limpo, e a branch antiga foi apagada. Depois, `git reflog expire` +
   `git gc --prune=now` para **apagar os objetos antigos** — a varredura
   em todos os blobs do `.git` não acha mais a série nem a senha.
   (Backup do `.git` antes da surgery: `/tmp/opencode/git-backup-pre-surgery`.)
3. **Branch `master`** (mesmo nome do outro projeto do usuário).
4. **`gh auth setup-git`**: o remote agora usa o credential helper do `gh`
   em vez do **PAT em texto claro** que estava no
   `.git/config` de `crm-vendas-supabase` — aquele PAT deve ser **rotacionado**.
5. **CI** (`.github/workflows/ci.yml`): lint com ruff, pytest e geração do
   relatório a partir do dataset sintético.

### ⚠️ Pendência: o escopo `workflow`

O push da CI foi **recusado** pelo GitHub:

```
! [remote rejected] HEAD -> master (refusing to allow an OAuth App to
create or update workflow `.github/workflows/ci.yml` without `workflow` scope)
```

O token do `gh` tem os escopos `gist, read:org, repo` — falta `workflow`.
Para liberar, é preciso um **device flow** (o navegador do usuário):

```bash
gh auth refresh --hostname github.com -s workflow
# abre https://github.com/login/device e pede um código de uso único
```

O processo foi deixado **rodando em background** com o código
`788A-31D2`. Depois de autorizar no navegador, basta:

```bash
git add .github/workflows/ci.yml
git commit -m "Adiciona CI (ruff + pytest + geração do relatório)"
git push
```

Até lá, o repositório está publicado e **completo** — só a CI falta.

### Estado do repositório publicado

- 41 arquivos, ~500 KB, **1 commit**, branch `master`
- 146 testes verdes, `ruff check src tests tools` limpo
- Nenhum dado de saúde, nenhuma senha, nenhuma série do aparelho

---

## Diário de bordo — 2026-10-21 ~15:45 — **Retomada: CI verde + limpeza do PAT**

A sessão anterior tinha "travado" logo depois do push da CI. Retomada:

### 1. A CI já estava publicada e passando ✅

O device flow (`gh auth refresh -s workflow`) **tinha sido concluído** — o
token do `gh` agora tem os escopos `gist, read:org, repo, workflow`, e o
run está no GitHub:

```
completed  success  Adiciona CI (ruff + pytest + geração do relatório)
CI Checks  master  push  39645240291  15s  2026-10-21T17:36:04Z
```

Ou seja: o `TODO.md` e este diário estavam **atrasados** — a pendência do
escopo `workflow` já não existia.

### 2. Revalidação no hardware real ✅

O aparelho estava conectado (Bus 001 Device 002), então o `dump` rodou
**sem sudo** (a regra udev segue valendo):

- **121 registros** (80 + 41), modelo `2102`;
- relógio do aparelho: `2026-10-21T15:44:33` contra `15:45:04` real →
  desvio de **31 s**, constante, deriva zero — bate com o ajuste feito no
  menu às 14:05;
- **nenhuma** leitura `±INF`: os 2 valores baixos do conjunto (9 e 11 mg/dL)
  são **leituras reais** (valor bruto `0x0009` / `0x000B`), não o sentinela
  `0x0802` — por isso o relatório acusa "hipoglicemia grave" e isso é
  correto, não um artefato do parser;
- `ruff` limpo e **146 testes verdes**.

### 3. PAT em texto claro removido de dois repositórios 🔐

O mesmo PAT estava no `remote.origin.url` de **dois** repositórios locais
(além do `crm-vendas-supabase`, também no `Vistoria`). Os dois remotes
foram reescritos para a URL sem credencial:

```bash
git -C "<repo>" remote set-url origin https://github.com/<user>/<repo>.git
```

O acesso passa a usar o credential helper do `gh` (já configurado no
`~/.gitconfig`: `credential.https://github.com.helper = !gh auth
git-credential`). Testado com `git ls-remote` nos dois repositórios →
acesso OK.

⚠️ **O que falta é do usuário:** *rotacionar/revogar* o PAT no GitHub
(*Settings → Developer settings → Personal access tokens*) — tirá-lo do
`.git/config` só impede o vazamento local, não revoga o token.

### 4. Other cleanups

- `log.md`: o cabeçalho tinha ficado com um `travou tudo` colado na
  primeira linha (digitação acidental) → removido;
- apagado o `libmsi-dev_0.103+repack-1build3_amd64.deb` que estava solto na
  raiz (download órfão de uma tentativa de instalar `tshark` — que foi
  descartada: a captura foi feita pelo `usbmon`);
- `TODO.md` atualizado: Fase 7 agora é **✅ completa**, com a CI verde e a
  pendência do PAT isolada em um único item.

