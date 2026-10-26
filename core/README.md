# Accu-Chek Active (Roche) no Linux

Cliente em Python que lê as leituras de glicemia do glicosímetro
**Roche Accu-Chek Active USB** (`173a:21cc`) no Linux, via USB, usando o
protocolo **ISO/IEEE 11073-20601** (PHDC / MDER) sobre o perfil
**11073-10417** de glicosímetro.

GitHub: <https://github.com/henriquegouveia85/accu-chek-active-linux>

> **ATENÇÃO: projeto somente leitura.** O cliente nunca define a hora do
> aparelho, nunca calibra, nunca reseta, nunca atualiza firmware. As únicas
> APDUs enviadas são as de associação (`E2`/`E3`/`E4`), a de leitura de
> atributos (`01 03`), as ações de leitura (`0C 0D` / `0C 1C`) e os ACKs
> (`02 01`). O `SET_TIME` (`0C 17`) e o `ABORT` (`E6 00`) **nunca** são
> enviados.

---

## Como funciona

```
python -m src.cli dump --out data.json --include-device
```

> ✅ Validado no hardware real: 3 dumps consecutivos devolveram exatamente os
> mesmos **121 registros** (80 + 41), modelo `2102`, série `XXXXXXXXX`.
>
> ℹ️ **Os números que aparecem neste repositório são sintéticos.** As
> leituras reais são dado de saúde e não são publicadas — ver
> [Privacidade](#privacidade).

O cliente faz o handshake completo do protocolo (14 fases) e despeja as
leituras em JSON:

```json
{
  "device": {
    "vendor_id": 5946,
    "product_id": 8652,
    "model": "2102",
    "serial": "XXXXXXXXX",
    "device_time": "2024-12-01T09:15:00"
  },
  "read_at": "2024-12-01T09:15:42",
  "count": 121,
  "records": [
    {
      "index": 0,
      "timestamp": "2024-01-01T07:46:49",
      "epoch": 1704090409,
      "mg/dL": 114,
      "mmol/L": 6.328,
      "status": 0
    }
  ]
}
```

### Comandos

| Comando | O que faz |
|---|---|
| `python -m src.cli dump [--out ARQ] [--include-device]` | Lê as leituras e salva em JSON |
| `python -m src.cli info` | Mostra modelo, série, hora do aparelho e segmentos |
| `python -m src.cli probe` | Só o handshake, com hexdump completo (diagnóstico) |
| `python -m src.cli show [--data ARQ]` | Resumo estatístico no terminal (sem navegador) |
| `python -m src.cli report [--data ARQ] [--out ARQ] [--open]` | Gera o relatório HTML autocontido |
| `python -m src.cli ... --wait SEGUNDOS` | Fica esperando o aparelho (útil para replugar o cabo) |
| `python -m src.cli --verbose dump` | Loga **todo** byte enviado/recebido, em hexdump |

---

## Relatório visual e análise clínica

O objetivo final do projeto: ler os dados e **mostrar na tela**, com gráficos
e métricas glicêmicas.

```bash
python -m src.cli report --data data.json --out relatorio.html --open
```

Gera **um único arquivo HTML autocontido** (~95 KB): sem JavaScript, sem CSS
externo, sem imagens externas, sem CDN. Abre offline em qualquer navegador e
pode ser enviado por e-mail.

O que tem dentro:

- **6 cartões** de métricas (n, média, GMI, TIR, CV, amplitude);
- **alertas** automáticos (hipoglicemia grave, variabilidade alta, TIR fora
  da meta);
- **Tempo em Faixa** — rosca com as 5 faixas + tabela;
- **série temporal** com as faixas-alvo coloridas ao fundo;
- **média diária + reta de tendência** (com r²);
- **boxplot por hora do dia**, **faixa horária** e **mapa de calor
  hora × dia da semana**;
- **tabelas** por hora, por dia da semana, eventos de hipoglicemia e todas
  as leituras;
- aviso clínico no topo e no rodapé.

Para uso rápido, sem abrir navegador:

```bash
python -m src.cli show --data data.json
```

### O que os números significam (e o que eles **não** significam)

As métricas vêm da literatura de CGM (Battelino 2019, Bergenstal 2018), mas
os dados vêm de um **glicosímetro (SMBG)**, não de um sensor contínuo. Isso
significa, entre outras coisas, que:

- o **TIR** é a fração das *leituras* na faixa, não do *tempo* — e o período
  noturno simplesmente não existe no conjunto de dados;
- a **hipoglicemia** é um *piso*, não uma estimativa: só conta o que foi
  medido;
- o **CV** e a **média glicêmica** são as métricas mais confiáveis aqui — a
  SBD inclusive aceita o CV calculado a partir de glicemia capilar.

A discussão completa, com as fontes e as ressalvas metodológicas, está em
[`docs/estudos.md`](docs/estudos.md).

---

## Requisitos

- Linux com `libusb-1.0` (já vem na maioria das distros)
- Python 3.10+
- pyusb

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

---

## Permissões de acesso ao aparelho

O `/dev/bus/usb/XXX/YYY` é criado pelo udev como `root:root`, **sem** ACL de
escrita para o usuário comum — então o pyusb não abre o aparelho sem
elevação. Duas saídas:

### 1. Rodar com `sudo` (mais simples)

```bash
sudo .venv/bin/python -m src.cli dump --out data.json
```

### 2. Instalar a regra udev (recomendado)

O arquivo `udev/99-accuchek.rules` dá ao grupo `plugdev` leitura e escrita no
device node:

```bash
sudo cp udev/99-accuchek.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
# replugar o aparelho para a regra valer
```

Depois disso, `python -m src.cli dump` funciona sem `sudo` — **validado**:
o device node ficou `root:plugdev` (`0660`) e o dump rodou sem elevação.

---

## O aparelho precisa estar pronto

O Accu-Chek Active só entra em modo de transferência quando o cabo USB está
conectado **e** o aparelho está na tela de transferência de dados. O cliente
espera o pedido de associação (`E2 00`) — que o aparelho **reenvia a cada
~1 s** enquanto espera a confirmação, então normalmente basta conectá-lo e
rodar o comando.

Se a sessão morrer no meio do handshake, o aparelho **cai do bus**: aí é
preciso reconectar o cabo (e, se continuar assim, desligar e ligar o
aparelho).

> ⚠️ O aparelho também **se desliga sozinho** depois de um tempo conectado.
> Rode o `dump` logo após reconectar o cabo.

---

## Protocolo (resumo)

| # | Direção | Mensagem |
|---|---|---|
| 1 | IN | `GET_STATUS` (control transfer) |
| 2 | IN | pairing request `E2 00` (enviado pelo aparelho) |
| 3 | OUT | pairing confirmation `E3 00` + 44 B |
| 4 | IN | config info (270 B) |
| 5 | OUT | config received confirmation |
| 6 | OUT | GET dos atributos do MDS |
| 7 | IN | resposta do MDS (modelo, série, hora) |
| 8 | OUT | action request `GET_INFO` |
| 9 | IN | action response |
| 10 | OUT | action request `TRIG_XFER` |
| 10b | IN | cabeçalho de 22 B (data-response) |
| 11 | IN | segmento de dados (loop) |
| 12 | OUT | ACK do segmento |
| 13 | OUT | release request `E4 00` |
| 14 | IN | release response `E5 00` |

O **invoke-id** (offset 6 de todo APDU `E7 00`) tem que andar de 1 em 1:
errar aqui faz o aparelho abandonar em silêncio.

O layout do registro foi **medido no Active** (10 bytes, base 36) e **não**
copiado do Accu-Chek Guide (12 bytes, base 34) — ver
[`docs/protocol-notes.md`](docs/protocol-notes.md).

### O relógio do aparelho (já foi corrigido)

O Active reportava `2019-11-12` enquanto a data real era `2026-10-21` —
**2535 dias** de diferença. Medido em 6 pontos, o desvio era constante ao
segundo: o relógio corria 1:1 com o real (deriva zero), só o *ponto de
partida* estava errado. Trocar a bateria não mudava nada (o RTC tem backup).

**Já foi resolvido**: ajustando a data e a hora **no menu do próprio
aparelho** (que não passa pelo USB), o desvio caiu para **30 segundos**,
constantes. O projeto **não** corrige o relógio por USB — `SET_TIME`
(`0C 17`) é proibido por ser somente leitura.

Restou um detalhe: as leituras que já estavam no aparelho continuam com o
carimbo antigo. Como o relógio antigo corria 1:1, ele apenas deslocou a
série toda de 2535 dias — os **intervalos**, as taxas e os valores em mg/dL
são válidos; só a âncora no calendário é aproximada. O relatório HTML detecta
o dessincronismo sozinho e avisa quando o desvio passa de 24 h.

---

## Estrutura do repositório

```
src/phdc.py          constantes MDC/APDU + codec (puro, sem I/O)
src/device.py        camada USB (único módulo que importa `usb`)
src/parser.py        bytes -> dataclasses (puro, sem I/O)
src/association.py   handshake (passos 1 a 9)
src/transfer.py      leitura dos segmentos (passos 10 a 14)
src/analysis.py      estatísticas e métricas clínicas (puro, sem I/O)
src/charts.py        gráficos SVG gerados em Python puro
src/report.py        relatório HTML autocontido + resumo no terminal
src/cli.py           entrada de linha de comando
tests/               146 testes (fixtures com o layout real do aparelho)
tools/               geradores dos fixtures e do transcript sintéticos
examples/            dataset de demonstração (sintético)
docs/                contexto, plano, notas de protocolo, estudos, capturas
udev/                regra de permissão de acesso
```

---

## Desenvolvimento

```bash
.venv/bin/python -m pytest tests/ -q      # 146 testes
.venv/bin/python -m ruff check src tests  # lint
```

Os testes rodam **sem hardware**: há um `FakeDevice` que simula o aparelho e
fixtures com o **layout exato** dos segmentos capturados do Active
(`tests/fixtures/*.hex`).

Os fixtures e o dataset de demonstração são **sintéticos** (gerados por
`tools/make_synthetic_fixtures.py`), mas reproduzem byte a byte a estrutura
do aparelho real — inclusive o cabeçalho de 36 bytes e o registro de 10
bytes. Para regenerá-los:

```bash
.venv/bin/python tools/make_synthetic_fixtures.py
```

O transcript de protocolo em `docs/captures/exemplo-sintetico/` é gerado
do mesmo jeito, rodando o cliente contra um dispositivo **falso** que faz
replay dos bytes:

```bash
.venv/bin/python tools/make_synthetic_transcript.py
```

---

## Privacidade

Este repositório é **público** e não contém nenhum dado do dono do aparelho:

| O que | Onde está | Situação |
|---|---|---|
| Leituras de glicemia (dado de saúde) | — | **Não publicadas** |
| Número de série do aparelho | `XXXXXXXXX` | Anonimizado |
| Capturas de sessão (`docs/captures/sessao-*`) | — | **Não publicadas** (ficam só no disco) |
| Senha de `sudo` | — | Nunca registrada |
| Fixtures de teste | `tests/fixtures/*.hex` | Sintéticos, mesmo layout |
| Dataset de demonstração | `examples/data_sintetico.json` | Sintético |
| Transcript de protocolo | `docs/captures/exemplo-sintetico/` | Sintético |

O transcript publicado foi produzido rodando o cliente contra um
dispositivo **falso** que faz replay dos bytes — o log tem exatamente o
formato das capturas reais, mas com leituras fictícias. Quem quiser
reproduzir o transcript:

```bash
.venv/bin/python tools/make_synthetic_transcript.py
```

---

## Aviso

Este software **não** é um dispositivo médico e as leituras aqui **não** são
diagnóstico nem orientação de tratamento. Qualquer decisão sobre a sua
glicemia deve ser tomada com o seu médico.

## Licença

Uso educacional. O protocolo reimplementado aqui segue as especificações
públicas ISO/IEEE 11073-20601 e 11073-10417.
