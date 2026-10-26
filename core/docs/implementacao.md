
Implemente, na ordem:

1. `device.py`: localizar dispositivo por VID/PID, abrir handle,
   detach kernel driver, set_configuration, claim_interface.
2. `phdc.py`: portar constantes do `accuChekUSB.js` do Tidepool
   (APDU types, event types, comandos MDC_*). Comente cada constante
   com a fonte.
3. `association.py`: enviar ASSOCIATION_REQUEST, ler resposta,
   validar. Se falhar, logar hexdump e iterar.
4. `transfer.py`: implementar o fluxo de leitura de registros conforme
   o Tidepool faz (GET_ID_LIST → TRIG_XFER para cada ID → receber
   pacotes até fim da transferência).
5. `parser.py`: decodificar timestamp, valor de glicemia (mg/dL),
   flags (antes/depois da refeição, controle, etc.). Referenciar
   structs do padrão 11073-10417.
6. `cli.py`: comando simples que dumps tudo em JSON.

## FASE 4 — Uso do projeto `rea` (auxiliar, se necessário)

O `rea` NÃO fareja USB. Ele é útil apenas se eu encontrar um binário
do software Roche (driver `.dll`, instalador, ou app) que eu queira
dissecar para entender comandos que não estejam documentados no
Tidepool. Nesse caso:

1. Clone https://github.com/morluto/rea
2. Configure conforme o README (precisa de chave de API de algum LLM).
3. Aponte para o binário em questão e me ajude a extrair strings,
   identificar funções de IO (DeviceIoControl, WriteFile em HID, etc.)
   e correlacionar com os bytes vistos na captura usbmon.

Não invista nessa fase a menos que as fases 1-3 travem em algum
comando desconhecido.

# DIRETRIZES TÉCNICAS

- Prefira Python + pyusb para iteração rápida. Se performance virar
  problema (não deve ser o caso), portamos para C com libusb-1.0.
- Use `usb.core.find(idVendor=0x173a, idProduct=0x21cc)` como ponto
  de partida (ajuste o PID conforme `lsusb`).
- Sempre faça `detach_kernel_driver(interface)` e `claim_interface`
  antes de qualquer transferência.
- Timeouts generosos no início (ex: 5000ms) para não falhar em
  handshake lento.
- Log de TODOS os bytes trocados em hexdump (com timestamp monotônico
  e direção IN/OUT) — isso é o que nos permite comparar com capturas.
- Preserve o `.pcap` de cada sessão de teste para análise posterior.
- Nunca envie nada além de: ASSOCIATION_REQUEST, GET_ID_LIST,
  TRIG_XFER e CONF (release). Qualquer outro comando, pare e pergunte.

# ENTREGÁVEIS ESPERADOS

1. `docs/descriptor.txt` com o descritor USB completo.
2. `docs/protocol-notes.md` com o que confirmamos vs. o que assumimos
   do Tidepool.
3. `docs/captures/*.pcap` + `.hex` de cada tentativa.
4. Projeto Python funcional que dumps as leituras em JSON.
5. README.md explicando como rodar (incluindo regras udev para rodar
   sem sudo, se possível).

# SEGURANÇA

Este é um dispositivo médico. Somente operações de leitura. Não
tentar escrever, calibrar, atualizar firmware ou resetar. Se um
comando parecer ter efeito colateral, ABORTE e me consulte.

# PRIMEIRA AÇÃO

Comece pela FASE 1, execute os comandos, cole a saída aqui e proponha
o primeiro script mínimo da FASE 2. Depois iteramos.