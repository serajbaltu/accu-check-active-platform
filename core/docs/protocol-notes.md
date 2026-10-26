# Protocol Notes — Accu-Chek Active

Separação explícita entre o que **foi confirmado no hardware** e o que foi
**assumido** a partir do driver do Tidepool / do port `emogenet/accuchek`.

Legenda: ✅ confirmado · 🟡 inferido (forte) · 🔴 não verificado

---

## 1. Camada USB — ✅ confirmado

| Item | Valor | Como |
|---|---|---|
| VID / PID | `0x173a` / `0x21cc` | `lsusb` |
| bcdUSB | 2.00 | descriptor |
| bcdDevice | 0.06 | descriptor |
| Classe de interface | 15 (PHDC) | descriptor |
| SubClass / Protocol | 0 / 0 | descriptor |
| Descritor PHDC | `04 21 01 08` → bcdCDC 1.8 | descriptor |
| Descritor CDC header | `04 20 02 00` → bcdCDC 2.00 | descriptor |
| Endpoint OUT | `0x01`, bulk, 64 B | descriptor + sysfs `ep_01` |
| Endpoint IN | `0x82`, bulk, 64 B | descriptor + sysfs `ep_82` |
| Driver de kernel | **nenhum** (`Driver=[none]`) | `lsusb -t` |
| Nº de configurações | 1 | descriptor |
| Endereço USB | full-speed (12 Mbit/s) | `lsusb -t` |
| iSerialNumber | **ausente** | descriptor (`iSerial 0`) |

**Implicação:** `detach_kernel_driver()` é inofensivo (não há driver preso), e
`claim_interface(0)` deve funcionar sem `libusb_set_option(LIBUSB_OPTION_NO_DEVICE_DISCOVERY)`.

**Atenção:** o `emogenet/accuchek` foi escrito para o **Accu-Chek Guide**
(`0x21d5`), **não** para o Active (`0x21cc`). O *protocolo* é o mesmo (ambos
PHDC/11073-20601), mas o **layout dos registros é diferente** — o Active usa
10 bytes na base 36, o Guide usa 12 bytes na base 34 (ver § 3.1).

## 2. Camada de transporte (APDU) — ✅ confirmado

Formato geral (ISO/IEEE 11073-20601, codificação MDER):

```
E7 00 | LL LL | OO OO | II II | DD DD | ...
       length  oct-str invoke-id data-choice
```

| APDU | Código | Nota |
|---|---|---|
| Association Request | `E2 00` | **enviado pelo aparelho**, não por nós |
| Association Response | `E3 00` | enviado por nós (pairing confirmation) |
| Release Request | `E4 00` | enviado por nós |
| Release Response | `E5 00` | enviado pelo aparelho |
| Association Abort | `E6 00` | **nunca enviar** |
| Presentation APDU | `E7 00` | dados (GET/ACTION/eventos) |

Data-choices:

| Código | Significado |
|---|---|
| `01 03` | GET (leitura de atributos) |
| `02 03` | resposta do GET |
| `01 07` | ACTION (confirmada) |
| `02 07` | resposta da ACTION |
| `01 01` | notificação do aparelho |
| `02 01` | ACK da notificação |

Event-types: `0D 1C` (MDC_NOTI_CONFIG), `0D 21` (MDC_NOTI_SEGMENT_DATA).
Action-types: `0C 0D` (GET_INFO), `0C 1C` (TRIG_XFER), `0C 1E` (GET_ID_LIST),
`0C 17` (SET_TIME — **proibido neste projeto**).

### Invoke-id
No offset 6 de todo APDU `E7 00`. A resposta traz o invoke-id da pergunta;
a próxima pergunta usa `invoke_id + 1`. Erro aqui → o aparelho **abandona em
silêncio** (sem erro, sem resposta).

### Estado do aparelho
O aparelho **inicia** a associação: ao conectar, ele manda `E2 00` — e
**reenvia** esse pedido periodicamente (~1 s) enquanto espera a confirmação
do host. Na captura real vieram 4 ZLPs antes do `E2 00`. Basta manter a
sessão de leitura aberta.

## 3. Camada de dados (11073-10417) — ✅ confirmado no Active

Estrutura de objetos (medida no config info real do Active, 270 bytes):

| Objeto | Handle | Conteúdo |
|---|---|---|
| `MDC_MOC_VMO_METRIC_NU` | 1 | glicemia (métrica numérica) |
| `MDC_MOC_VMO_METRIC_NU` | 2 | glicemia (métrica numérica) |
| `MDC_MOC_VMO_METRIC_ENUM` | 3 | marcador de estado |
| `MDC_MOC_VMO_METRIC_ENUM` | 4 | marcador de estado |
| `MDC_MOC_VMO_PMSTORE` | 5 | o PM-Store (4 segmentos: `PMSegGluc`, `PMSegCtrl`, `PMSegErr`, `PMSegMeal`) |

### 3.1 Layout do registro — ✅ **10 bytes** na base **36** (Active)

Medido nos bytes reais (`docs/captures/sessao-01/dump2.log`):

```
offset 30: uint16 BE  número de entradas do segmento
offset 32: byte        status do segmento (bit 0x40 = último)
offset 36: primeiro registro

cada entrada (10 B):
  +0  2 B  ano em BCD (século, ano)   ex.: 20 20 -> 2020
  +2  1 B  mês    (BCD)
  +3  1 B  dia    (BCD)
  +4  1 B  hora   (BCD)
  +5  1 B  minuto (BCD)
  +6  1 B  segundo (BCD)
  +7  1 B  reservado (sempre 0x00)
  +8  2 B  valor da glicemia, uint16 BE, mg/dL
```

⚠️ **O Accu-Chek Guide (`0x21d5`), usado pelo `emogenet`, tem layout
DIFERENTE**: 12 bytes na base 34, **sem** o segundo, valor em `+14` e status
em `+16`. Copiar os offsets do C++ para o Active produz leituras plausíveis
mas **erradas** (datas deslocadas em 2 bytes).

O `BCD` é **padrão** (`(b >> 4) * 10 + (b & 0x0F)`), não "nibbles trocados" —
o `emogenet` faz `sprintf("%02X")` + `sscanf("%d")`, que é equivalente, mas
quebra com nibble > 9.

O **status por registro não existe** no Active (sempre 0). O status de
`+7` (reservado) é sempre zero nas 121 leituras capturadas.

### 3.2 Resposta a um GET (`02 03`) — ✅ layout medido

A resposta do MDS **não** tem o layout de "config info". Medido (210 bytes):

```
[0:2]   e7 00     APDU type
[2:4]   00 ce     LL = 206
[4:6]   00 cc     octet-string length
[6:8]   00 01     invoke-id
[8:10]  02 03     data-response = GET
[10:12] 00 c6     length
[12:14] 00 00     handle 0
[14:16] 00 08     nº de atributos = 8
[16:18] 00 c0     comprimento da lista de atributos = 192
[18:..]           atributos: [class(2)][tamanho(2)][valor]
```

Os 8 atributos do Active: `MODEL`, `SYS_ID`, `DEV_CONFIG_ID`, `PROD_SPECN`,
`TIME_ABS`, `MDS_TIME_INFO`, `REG_CERT_DATA_LIST`, `SYS_TYPE_SPEC_LIST`.

- `MODEL` = duas cadeias MDER: `00 06 "Roche"` + `00 04 "2102"` → **modelo 2102**.
- `TIME_ABS` = **BCD**, 7 bytes (cc, yy, mm, dd, hh, mn, ss) →
  `2019-11-12 01:13:19` (relógio interno desatualizado — **não** alterado).
- `PROD_SPECN` = lista: `[contagem(2)][comprimento-total(2)]` e, por entrada,
  `[tipo(2)][idioma(2)][tamanho(2)][texto]`. Tipo 1 = `serial-number`
  (`"serial-number: XXXXXXXXX"`), tipo 5 = `fw-revision` (`"fw-rev:   V02.04"`).
  ⚠️ Este layout **difere** do `utils.js` do Tidepool (que lê `tipo@+4`,
  `tamanho@+8`) — no Active, a partir da 2ª entrada o JS lê lixo.

### 3.3 Cabeçalho do TRIG_XFER — ✅ 22 bytes

Resposta de 22 bytes ao `0C 1C`: `action-type` no offset 14,
`data-response` no offset 20. Valores: 0 = sucesso, 1 = "no such segment",
2 = "try again later", 3 = **segmento vazio**, 512 = falha ao recuperar.

### 3.4 Transporte — ✅ confirmado

- O `pyusb.read()` devolve **1 pacote de 64 bytes**; o APDU precisa ser
  **reassemblado** (o config info tem 270 bytes = 5 pacotes). O
  `bulk_transfer` do `emogenet` (libusb) já entregava o transfer inteiro.
- O Active **reenvia** o `E2 00` periodicamente (~1 s) enquanto espera a
  confirmação do host — não é preciso replugar o cabo, basta manter a sessão
  de leitura aberta. (O `emogenet` assume envio único.)
- O aparelho **cai do bus** se a sessão for encerrada no meio do handshake.
- O aparelho **se desliga sozinho** depois de um tempo conectado (observado
  pelo usuário): o `dump` precisa ser rodado logo após a reconexão.
- Com a regra udev instalada, o dump roda **sem `sudo`**
  (`/dev/bus/usb/001/00X` = `root:plugdev`, `0660`).

### 3.5 Relógio interno do aparelho — ✅ confirmado (errado) → ✅ resolvido

O `TIME_ABS` do MDS devolveu sempre `2019-11-12`, com a data real em
`2026-10-21`. Medido em **6 pontos** (4 dumps em 2 sessões, 12:19 → 14:00):

| Momento real | Hora do aparelho | Desvio |
|---|---|---|
| 12:19:51 | 01:13:19 | 2535 d 11:06:32 |
| 13:54:31 | 02:47:59 | 2535 d 11:06:32 |
| 13:54:52 | 02:48:20 | 2535 d 11:06:32 |
| 13:55:07 | 02:48:35 | 2535 d 11:06:32 |
| 14:00:07 | 02:53:35 | 2535 d 11:06:32 |
| 14:00:57 | 02:54:25 | 2535 d 11:06:32 |

Desvio **constante ao segundo** → **deriva zero**: o relógio corre 1:1 com o
tempo real. O que está errado é só o **ponto de partida**.

**Teste da bateria:** o usuário trocou a bateria do aparelho entre as 13:55 e
as 14:00. O relógio **não mudou** (continuou de 02:48:35 para 02:53:35, com
a deriva zero) e os 121 registros continuaram idênticos. Logo o RTC **não é
alimentado pela bateria trocada** — há um elemento de backup (ou o relógio
simplesmente foi configurado errado em algum momento e segue correndo).
A hipótese "bateria removida → data de fábrica" fica **refutada** para este
caso.

⚠️ **Consequência prática:** qualquer medição nova seria carimbada com
`2019-11-12`, ou seja, **antes** de todos os registros já existentes — isso
embaralharia a linha do tempo do conjunto.

**✅ Resolvido em 2026-10-21 14:05:** o usuário ajustou data e hora **no menu
do próprio aparelho** (que não passa pelo USB e portanto não viola a regra
somente-leitura). Verificado em dois dumps:

| Momento real | `device_time` | Desvio |
|---|---|---|
| 14:05:50 | 2026-10-21T14:05:20 | 30 s |
| 14:06:39 | 2026-10-21T14:06:09 | 30 s |

Desvio de **30 s, constante, deriva zero** → o relógio está sincronizado
(dentro do ajuste feito no aparelho). `SET_TIME` (`0C 17`) pelo USB continua
**proibido**.

Impacto analítico remanescente: os **registros antigos** continuam com o
carimbo do relógio antigo. Como ele corria 1:1 e
só o *ponto de partida* estava errado, os **intervalos**, as taxas, as médias
móveis e os valores em mg/dL **não** são afetados; só as **datas absolutas**
devem ser lidas como aproximadas. As medições **novas** já saem com a data
correta e **depois** das antigas → linha do tempo coerente.

## 4. Decisões de projeto

- **Não enviar SET_TIME** (`0C 17`): o Tidepool JS define a hora do aparelho.
  Este projeto é somente leitura e não deve tocar no relógio interno.
- **Não enviar ABORT** (`E6 00`).
- **Timeout 5000 ms**: o handshake do aparelho é lento.
- **Hexdump de tudo**: único mecanismo de debug confiável.

## 5. Referências

- `emogenet/accuchek` — https://github.com/emogenet/accuchek (clone em `/tmp/opencode/accuchek`)
- Tidepool `uploader` — `lib/drivers/roche/accuChekUSB.js` (define hora; não copiar)
- ISO/IEEE 11073-20601 (PHDC / MDER) e 11073-10417 (perfil glicosímetro)
- Artigo do emogenet — https://librenard.fr/wiki/books/apprendre-a-parler-a-un-glucometre/page/la-langue-du-lecteur-isoieee-11073
- Capturas reais deste projeto — `docs/captures/sessao-01/` (descoberta do
  layout), `sessao-02/` (validação do cliente completo) e `sessao-03/`
  (teste da troca de bateria → relógio).
  ⚠️ Elas contêm leituras de glicemia e a série do aparelho, então **não
  são publicadas**: continuam no disco, fora do git. O que é público é o
  transcript sintético `docs/captures/exemplo-sintetico/`, com o mesmo
  formato de log e o mesmo layout de bytes.
