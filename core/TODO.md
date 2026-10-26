# TODO — Accu-Chek Active (Roche) no Linux

Legenda: `[ ]` pendente · `[~]` em andamento · `[x]` feito · `[!]` bloqueado

---

## Fase 0 — Fundação do repositório

- [x] Renomear documentos para nomes autoexplicativos
      (`docs/contexto.md`, `docs/implementacao.md`, `docs/estrutura.md`)
- [x] Criar `AGENTS.md` com fatos confirmados, fluxo APDU e regras invioláveis
- [x] Criar `TODO.md`
- [x] Criar `opencode.json` com permissões de bash para o fluxo do projeto
- [x] Criar `docs/descriptor.txt` a partir de `lsusb -v -d 173a:21cc`
- [x] Instalar dependências: `pip install -r requirements.txt` (.venv)
- [ ] Instalar `tshark`/`dumpcap` (opcional) — `sudo apt install tshark`
      → **descartado**: captura feita via `usbmon` (`cat`), sem instalar nada
- [x] Regra udev `99-accuchek.rules` + `sudo udevadm control --reload-rules`
      → **instalada e validada**: o device node fica `root:plugdev` (`0660`)
      e o dump roda **sem sudo**
- [x] `git init` + `.gitignore` (pycache, venv, capturas binárias grandes)
      → repositório criado, histórico **reescrito** na publicação (ver Fase 7):
      branch `master`, **1 commit**, 41 arquivos. Fora do git: `data.json`,
      `relatorio.html`, `docs/captures/sessao-*/` (dados de saúde legíveis,
      regeneráveis) e o instalador `SmartPix-*.exe` (244 MB)

## Fase 1 — Diagnóstico do dispositivo  ✅ (parcial)

- [x] `lsusb` → identificado `173a:21cc` no Bus 001, Device 006
- [x] `lsusb -v -d 173a:` → `docs/descriptor.txt`
      (classe 15/PHDC, PHDC bcdCDC 1.8, EP 0x01 OUT + 0x82 IN, bulk 64B)
- [x] `lsusb -t` → interface 0 **sem driver de kernel** (`Driver=[none]`)
- [x] `dmesg | tail` → enumeração limpa, sem erros
- [x] `getfacl /dev/bus/usb/001/006` → root:root, sem ACL de escrita
- [x] `sudo lsusb -v` completo (o sem-root omite strings e descriptors de config)
- [x] `sudo modprobe usbmon` + confirmado `/sys/kernel/debug/usb/usbmon/`
- [x] `cat /sys/kernel/debug/usb/usbmon/001u > docs/captures/sessao-01/usbmon4.txt`

## Fase 2 — Captura de tráfego USB  ✅ (sem pcap)

> ⚠️ As capturas de sessão (`docs/captures/sessao-*`) contêm leituras de
> glicemia e a série do aparelho: ficam **só no disco**, fora do git. O
> transcript publicado é o sintético, em
> `docs/captures/exemplo-sintetico/`.

- [x] Ligar `usbmon` (rodado com `sudo`)
- [ ] `sudo tshark -i usbmon1 -w docs/captures/session-01.pcap`
      → **descartado**: `tshark` não instalado; a captura foi pelo `usbmon`
        em texto (`docs/captures/sessao-01/usbmon4.txt`) + hexdump do cliente
- [x] `src/cli.py probe` (substituiu o `src/probe.py`):
      - [x] `find(find_all=True, idVendor=0x173a, idProduct=0x21cc)`
      - [x] `detach_kernel_driver` (no-op esperado) + `claim_interface(0)`
      - [x] hexdump de tudo com timestamp monotônico → `docs/captures/sessao-01/`
- [x] Correlacionar o `usbmon` com o hexdump (mesmos bytes, mesma ordem)
- [x] Validar contra o fluxo do `emogenet/accuchek` (fases 1→14)
      → **validado**: as 14 fases rodaram no aparelho real
- [x] Guardar a sessão como baseline para as fases seguintes
      (`docs/captures/sessao-01/dump2.log` = sessão completa com 121 registros)

## Fase 3 — Cliente Python

### 3.1 `src/device.py` — camada USB
- [x] `find_device(vid=0x173a, pid=0x21cc)` com mensagens de erro claras
- [x] `open_device()` → `set_configuration(1)`
- [x] `claim_interface(0)` + `detach_kernel_driver` defensivo
- [x] `bulk_out(data, timeout=5000)` / `bulk_in(size, timeout=5000)`
- [x] `close()` idempotente (context manager)
- [x] Detectar endpoint IN/OUT dinamicamente pelo descritor (não fixar 0x01/0x82)

### 3.2 `src/phdc.py` — constantes e codec
- [x] Portar `kAPDU_TYPE_*` (0xE200…0xE700)
- [x] Portar `kDATA_ADPU_*` (0x0101, 0x0103, 0x0107, 0x0201, 0x0203, 0x0207)
- [x] Portar `kEVENT_TYPE_*` (0x0D1C, 0x0D21)
- [x] Portar `kACTION_TYPE_*` (0x0C0D, 0x0C17[NÃO USAR], 0x0C1C, 0x0C1E)
- [x] Lista `MDC_*` (93 entradas extraídas do `MDC_LIST` do emogenet)
- [x] Helpers: `be16`/`be32`/`put16`/`put32`, `mdc_name(value)`
- [x] Builders: `association_response()`, `get_request()`, `action_request()`,
      `config_confirmation()`, `segment_ack()`, `release_request()`
- [x] Cada constante com comentário de fonte
- [x] **Verificado byte a byte** contra o `main.cpp` do emogenet (6 APDUs)

### 3.3 `src/association.py` — handshake
- [x] `associate(dev)` → envia `E3 00` (pairing confirmation) e valida resposta
- [x] Parse do "config info": achar objeto `MDC_MOC_VMO_PMSTORE` (handle)
- [x] Extrair `MDC_ATTR_NUM_SEG` (nº de segmentos)
- [x] Responder "config received confirmation" (`02 01` + `0D 1C` + `40 00`)
- [x] GET dos atributos MDS (modelo, serial, hora do aparelho) — `01 03` handle 0
- [x] Controle de `invoke_id` (próxima pergunta = atual + 1)
- [x] Em falha: logar hexdump completo e levantar `ProtocolError` com contexto

### 3.4 `src/transfer.py` — leitura dos segmentos
- [x] `get_info(dev, pm_store_handle)` → `01 07` + `0C 0D`
- [x] `trigger_transfer(dev, pm_store_handle)` → `01 07` + `0C 1C`
- [x] Loop de recepção: ler segmento → parsear → mandar ACK (`02 01` + `0D 21` + `00 80`)
- [x] Parar quando `status & 0x40` (último segmento)
- [x] Teto de segurança `MAX_SEGMENTS` (evita laço infinito)
- [x] **Tolerar pacotes de 64 bytes fragmentados** (montar stream antes de parsear)
      → `Device.read_apdu()` acumula até `LL + 4` bytes
- [x] Ler o cabeçalho de 22 bytes que responde ao TRIG_XFER
      (data-response: 0 = ok, 3 = segmento vazio, 512 = erro)
- [x] `release(dev)` → `E4 00` + `00 00`, esperar `E5 00`

### 3.5 `src/parser.py` — decodificação
- [x] `parse_config(buffer)` → objetos, handles, contagem de segmentos
- [x] `parse_segment(buffer)` → lista de registros
- [x] Data/hora BCD (não "nibbles trocados" — corrigido) → `datetime`
- [x] Valor uint16 BE mg/dL (+ conversão mmol/L = mg/dL / 18,0)
- [x] `status` → flags
- [x] Detecção automática da base dos registros (por plausibilidade de data)
- [x] Dataclass `GlucoseRecord` com `to_dict()`
- [x] **Layout real do Active** (medido nos bytes capturados): registro de
      **10 bytes** na base **36** — ano(2) mês dia hora min seg(BCD),
      reservado, valor em +8. (O Guide tem 12 bytes; ver `docs/protocol-notes.md`.)
- [x] `parse_get_response()` → lista de atributos da resposta a um GET (offset 18)
- [x] `parse_production_spec()` → serial number e fw-revision
- [x] `+INF` (0x07FE → 601) / `-INF` (0x0802 → 9) com flag `out_of_range`
- [ ] `construct` para o layout do registro de 12 bytes (opcional)

### 3.6 `src/cli.py` — entrada
- [x] `python -m src.cli dump --out data.json`
- [x] `--verbose` (hexdump em stderr)
- [x] `python -m src.cli info` (identificação do aparelho)
- [x] `python -m src.cli probe` (Fase 2, handshake mínimo com hexdump)
- [x] Saída em JSON: id, timestamp ISO, epoch, mg/dL, mmol/L, status

### 3.7 `tests/`
- [x] `test_phdc.py` — 6 APDUs conferidas byte a byte com o emogenet
- [x] `test_parser.py` — BCD, segmentos, detecção de base, config, GET, prod spec
- [x] `test_flow.py` — aparelho falso: handshake + leitura + ACK + release
- [x] `test_device.py` — camada USB: fragmentação, ZLP, timeout, ciclo de vida
- [x] Fixtures com **bytes reais** do Active (`tests/fixtures/*.hex`)
- [x] 146 testes passando (`python -m pytest tests/ -q`)

## Fase 4 — Documentação e empacotamento  ✅
- [x] `README.md` — como rodar, troubleshooting, regra udev
- [x] `docs/protocol-notes.md` — confirmado vs. assumido (manter atualizado)
- [x] `requirements.txt`
- [x] `pyproject.toml` (ruff + pytest)
- [x] `udev/99-accuchek.rules` — instalada em `/etc/udev/rules.d/` e
      **validada**: o device node ficou `root:plugdev` (`0660`) e o dump rodou
      **sem sudo**
- [x] **Validação no hardware**: 3 dumps consecutivos → 121 registros
      idênticos (80 + 41), modelo `2102`, série `XXXXXXXXX`

## Fase 5 — Ferramenta auxiliar `rea` (só se travar)
- [ ] Clonar https://github.com/morluto/rea (precisa de chave de API de LLM)
- [ ] Usar **apenas** se surgir um comando desconhecido sem documentação

## Fase 6 — Relatório visual e análise clínica  ✅

> Objetivo final pedido pelo usuário: um programa que lê os dados e **mostra na
> tela** os resultados, com gráficos e o que mais for possível em termos de
> glicemia e estudos científicos.
> **Precondição:** as Fases 1–4 funcionando (leitura real do aparelho).
> Pode ser desenvolvido com `tests/fixtures/` (JSON sintético) em paralelo,
> mas a validação final só com dados reais.

### 6.1 Coleta e organização dos dados  ✅
- [x] `src/analysis.py` — módulo de estatística, **puro** (sem I/O, sem UI)
- [x] Carregar registros de JSON (do `src/cli.py dump`) — `load_dataset()`
- [x] Normalizar: ordenação cronológica, deduplicação por timestamp
- [x] Enriquecer com contexto: jejum/pós-prandial por **heurística** (o
      segmento `PMSegMeal` do 11073-10417 ainda não é lido)

### 6.2 Métricas clínicas (com as fórmulas e as referências)  ✅
- [x] Descritivas: n, média, mediana, DP, CV, IQR, min, max, amplitude
- [x] **GMI** (%) = `3.31 + 0.02392 × média mg/dL`
      (Bergenstal et al., *Diabetes Care* 2018;41(11):2275-2280 — DOI 10.2337/dc18-1581)
- [x] **eA1c (ADAG)** = `(média + 46,7) / 28,7` — comparação com o GMI
- [x] **Tempo em faixa (TIR)** — alvos do consenso internacional
      (Battelino et al., *Diabetes Care* 2019;42(8):1593-1603):
      | Faixa | mg/dL | Alvo T1D/insulina | Alvo T2D não-insulina (ADA) |
      |---|---|---|---|
      | Muito baixa | < 54 | < 4% | — |
      | Baixa | 54–69 | < 1% + < 15 min | — |
      | Em faixa | 70–180 | > 70% | > 70% (80–130 em jejum) |
      | Alta | 180–250 | < 25% | < 25% (pós-prandial < 180) |
      | Muito alta | > 250 | < 5% | < 10% |
- [x] Índice de hipoglicemia: nº de eventos < 70, < 54, sequências consecutivas
- [x] Coeficiente de variação (CV %) — instabilidade se > 36%
- [x] Jejum vs. pós-prandial: médias por janela (heurística da 1ª leitura do dia)
- [x] Tendência: regressão linear sobre a média diária (slope mg/dL/dia + r²)
- [x] Efeito "dawn phenomenon" (média das leituras de madrugada, 1ª vs. 2ª metade)
- [x] Distribuição: histograma, boxplot por hora do dia, por dia da semana
- [x] Intervalo mediano entre medições (densidade de monitorização)
- [x] Alertas automáticos (`Analysis.alerts`)

### 6.3 Gráficos  ✅
- [x] `src/charts.py` — geração de gráficos
- [x] Backend escolhido: **HTML autocontido** com SVG gerado em Python puro
      (sem matplotlib, sem JS, sem CDN) — decided against PNG export:
      o HTML já abre offline e é compartilhável
- [x] Gráfico 1: série temporal (linha) com faixas alvo coloridas
- [x] Gráfico 2: histograma da distribuição de valores
- [x] Gráfico 3: boxplot por hora do dia
- [x] Gráfico 4: media diária + linha de tendência
- [x] Gráfico 5: donut/faixas de TIR
- [x] Gráfico 6: heatmap hora × dia da semana
- [x] Extra: *strip plot* da faixa horária (hora × valor)

### 6.4 Interface  ✅
- [x] `src/cli.py report` — gera `relatorio.html` e abre no navegador (`--open`)
- [x] `src/cli.py show` — resumo no terminal (sem navegador), para uso rápido
- [x] Painel HTML: cabeçalho com período e nº de leituras, cartões com as
      métricas, gráficos, tabela de eventos críticos (hipo/hiper) e
      **avisos clínicos** (não substitui orientação médica)
- [x] Marcar claramente que os dados são de **glicosímetro (SMBG)**, não CGM:
      TIR/GMI de SMBG são aproximações (ver `docs/estudos.md`)
- [x] `src/report.py::terminal_summary()` — resumo ASCII para o terminal

### 6.5 Estudos científicos (paralelo, não depende do hardware)  ✅
- [x] `docs/estudos.md` — compilação da literatura relevante (verificada
      nas fontes, com PMID/DOI)
- [x] Consenso de TIR (Battelino 2019) e revisões recentes
- [x] Limitação do TIR com dados de glicosímetro (o TIR pressupõe CGM 24 h)
      — e a validação do TIR com SMBG de 7 pontos (Beck 2019, DCCT)
- [x] GMI vs. A1c de laboratório: quando concordam e quando não
- [x] Metas glicêmicas: ADA *Standards of Care* 2026 e SBD (Ed. 2025/2026)
- [x] Variabilidade glicêmica e risco de hipoglicemia (CV ≤ 36%, níveis 1/2/3)
- [x] Ordem do dia, exercício e horário das refeições: como interpretar
- [x] Precisão analítica do aparelho: ISO 15197:2013 (±15% / ±15 mg/dL)

---

## Fase 7 — Publicação no GitHub  ✅

- [x] Sanitizar todo o conteúdo: senha removida, série → `XXXXXXXXX`,
      fixtures/dataset/transcript **sintéticos**
- [x] Reescrever o histórico (branch órfã + `git gc --prune=now`) para que
      as capturas reais **não existam** em nenhum objeto do `.git`
      → varredura em todos os blobs: zero ocorrências da série/senha
- [x] Identidade git → `Henrique Gouveia <henriquegouveia85@gmail.com>`
- [x] `gh auth setup-git` (credential helper do `gh`, sem PAT em texto claro)
- [x] `docs/captures/README.md` — o que é publicado vs. o que fica no disco
- [x] `README.md` — seção **Privacidade**
- [x] Publicar: **https://github.com/henriquegouveia85/accu-chek-active-linux**
      (público, branch `master`, 1 commit, 41 arquivos, ~500 KB)
- [x] `.github/workflows/ci.yml` (ruff + pytest + geração do relatório)
      → escopo `workflow` liberado (`gh auth refresh -s workflow`) e
      **push aceito**: run `39645240291` → **success**
- [x] Remote do repo `crm-vendas-supabase` limpo: o PAT em texto claro saiu
      do `.git/config` e o acesso passou a usar o credential helper do `gh`
- [ ] **Rotacionar o PAT** que estava em texto claro no remote do
      `~/Área de trabalho/crm-vendas-supabase` — ação do usuário no GitHub
      (*Settings → Developer settings → Personal access tokens*)

---

## Notas de progresso

- **2026-10-21** — Diagnóstico inicial concluído. Aparelho enumerado como
  PHDC 1.8, endpoints bulk 0x01/0x82, **sem driver de kernel na interface**
  (implica `detach_kernel_driver` é inofensivo). Device node sem ACL de escrita
  → precisa regra udev.
- **2026-10-21** — Descoberta importante: `emogenet/accuchek` é um port
  C++/libusb do driver Tidepool e documenta o fluxo APDU completo. Serve de
  referência primária, Reducing risco de implementação às cegas.
- **2026-10-21** — **Handshake completo rodou no aparelho real** (14 fases):
  GET_STATUS → E2 00 → E3 00 → config info (270 B) → config confirmation →
  GET dos atributos do MDS (206 B) → GET_INFO → TRIG_XFER → **2 segmentos
  (80 + 41 = 121 registros)** → ACKs → release.
  Captura completa em `docs/captures/sessao-01/dump2.log`.
- **2026-10-21** — **Layout do registro do Active confirmado pelos bytes
  reais**: 10 bytes na base 36 (o Guide tem 12 na base 34). O segundo ocupa
  `+6` e o valor `+8`. O parser foi migrado e validado contra a captura.
- **2026-10-21** — Identificação do aparelho lida do MDS: modelo `2102`,
  serial `XXXXXXXXX`, firmware `V02.04`, relógio interno `2019-11-12 01:13:19`
  (desatualizado — e **não** alterado: o projeto é somente leitura).
- **2026-10-21** — **Dump validado no hardware real**: 3 execuções seguidas
  devolveram exatamente os mesmos **121 registros** (80 + 41), modelo `2102`,
  série `XXXXXXXXX`. A regra udev funcionou — o `dump` rodou **sem sudo**
  (`/dev/bus/usb/001/008` = `root:plugdev`, `0660`).
  Captura preservada em `docs/captures/sessao-02/`.
- **2026-10-21** — **Descoberta: o relógio do aparelho está ~7 anos atrasado.**
  Ele reportou `2019-11-12` enquanto a data real era `2026-10-21` —
  **2535 dias, 11:06:32** de diferença, medidos em **6 pontos** (4 dumps em
  2 sessões, 12:19 → 14:00). O desvio é **constante ao segundo**: **deriva
  zero**, o relógio corre 1:1 com o real; só o **ponto de partida** está
  errado.
- **2026-10-21** — **Teste da troca de bateria**: o usuário trocou a bateria
  entre 13:55 e 14:00. O relógio **não mudou** (continuou correndo com
  deriva zero através do ciclo de desligar/ligar) e os 121 registros
  continuaram idênticos → o RTC **não** é alimentado pela bateria trocada.
  A hipótese "bateria removida → data de fábrica" fica **refutada**.
  ⚠️ Consequência: medição nova agora seria carimbada como `2019-11-12`
  (*antes* de todos os registros existentes) → a data/hora precisa ser
  ajustada **no menu do aparelho**, nunca via USB (`SET_TIME` é proibido).
  O relatório avisa isso (`_clock_note()`).
- **2026-10-21** — **✅ Relógio do aparelho sincronizado**: o usuário ajustou
  a data/hora **no menu do próprio aparelho** (14:05). O `device_time` passou
  a `2026-10-21T14:05:20` (real 14:05:50) e `14:06:09` (real 14:06:39) →
  desvio de **30 s, constante, deriva zero**. Os 121 registros antigos seguem
  idênticos, e como o relógio antigo corria 1:1, ele apenas deslocou a
  série toda de 2535 dias — as curvas e as métricas glicêmicas seguem
  válidas, só a âncora no calendário das leituras antigas é aproximada.
  O relatório deixou de mostrar o aviso de dessincronismo sozinho.
  Captura em `docs/captures/sessao-04/`.
- **2026-10-21** — **Fase 6 concluída**: `src/analysis.py` (métricas clínicas
  puras), `src/charts.py` (7 gráficos SVG gerados em Python puro, sem
  matplotlib/JS/CDN), `src/report.py` (HTML autocontido de ~95 KB + resumo no
  terminal) e os comandos `src.cli report` / `src.cli show`.
  Compilação bibliográfica em `docs/estudos.md` (Battelino 2019, Bergenstal
  2018, Beck 2019, ADA 2026, SBD, ISO 15197), com a ressalva explícita de que
  TIR/GMI de glicosímetro (SMBG) são aproximações.
  **146 testes verdes.**
- **2026-10-21** — **Repositório publicado**:
  https://github.com/henriquegouveia85/accu-chek-active-linux (público).
  Histórico reescrito (branch órfã → 1 commit limpo) e `git gc` para apagar
  os objetos antigos — as capturas reais **não existem mais** em nenhum
  objeto do `.git`. Conteúdo publicado: 41 arquivos, ~500 KB, sem dado de
  saúde, sem senha, sem série do aparelho. **Falta só a CI**, bloqueada pelo
  escopo `workflow` do token do `gh`.
- **2026-10-21 ~15:45** — **CI publicada e verde**: o escopo `workflow` foi
  liberado (`gh auth refresh -s workflow`) e o push da
  `.github/workflows/ci.yml` foi aceito — run `39645240291` → `success`
  (ruff + 146 testes + geração do relatório a partir do dataset sintético).
  Revalidação local no hardware real com o aparelho conectado: **121
  registros**, modelo `2102`, relógio do aparelho com desvio de **31 s**
  (constante, deriva zero) e **nenhuma** leitura `±INF` (os 2 valores
  baixos — 9 e 11 mg/dL — são leituras reais, com valor bruto `0x0009` /
  `0x000B`, não o sentinela `0x0802`).
  Também foi limpo o remote do repo `crm-vendas-supabase`: o **PAT em
  texto claro** saiu do `.git/config` e o acesso agora usa o credential
  helper do `gh`. Resta só **rotacionar** o PAT no GitHub (ação do
  usuário).
