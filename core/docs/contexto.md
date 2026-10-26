# CONTEXTO DO PROJETO

Estou fazendo engenharia reversa do meu glicosímetro Accu-Chek Active (Roche)
para criar suporte a Linux. O aparelho JÁ ESTÁ CONECTADO na porta USB do meu
computador agora. Não tenho acesso a nenhuma máquina Windows.

O projeto `rea` (https://github.com/morluto/rea) pode ser usado como
ferramenta auxiliar de análise, mas o grosso do trabalho será feito com
captura USB nativa no Linux + libusb/pyusb.

# O QUE JÁ SE SABE SOBRE O DISPOSITIVO

- Fabricante: Roche
- Modelo: Accu-Chek Active
- Classe USB: PHDC (Personal Healthcare Device Class, 0x0F)
- Protocolo de aplicação: ISO/IEEE 11073-10417 (glicosímetro)
- VID esperado: 0x173A (Roche)
- PID esperado: 0x21CC (Accu-Chek Active) — CONFIRMAR com lsusb
- Referência de implementação aberta: código JS do projeto Tidepool
  (`accuChekUSB.js` e `utils.js` no repositório tidepool-org) — já contém
  as constantes do protocolo (APDU_TYPE, EVENT_TYPE, ASSOCIATION_REQUEST
  = 0xE200, MDC_ACT_SEG_GET_ID_LIST, MDC_ACT_SEG_TRIG_XFER, etc.)
- Projeto correlato: `cw-cdz/accuchek` (C++ + libusb) para Accu-Chek Guide

# OBJETIVO FINAL

Ler registros de glicemia do aparelho via USB no Linux, entregando os dados
em formato estruturado (JSON ou CSV). Apenas LEITURA — não modificar
firmware, calibração, nem enviar comandos que não sejam de leitura.

# TAREFAS QUE VOCÊ DEVE EXECUTAR (em ordem)

## FASE 1 — Diagnóstico do dispositivo conectado

1. Rode `lsusb` e identifique o dispositivo Roche (VID 173a).
2. Rode `lsusb -v -d 173a:` (ou o PID correto) e salve a saída completa em
   `docs/descriptor.txt`. Analise:
   - bDeviceClass / bDeviceSubClass / bDeviceProtocol (esperado: 0x0F PHDC)
   - Interfaces, endpoints (bulk IN/OUT, interrupt, etc.)
   - Strings do dispositivo (iManufacturer, iProduct, iSerialNumber)
3. Rode `lsusb -t` para ver o topology.
4. Verifique `dmesg | tail -50` para mensagens do kernel ao plugar.
5. Cheque se o driver `usbhid` ou outro está "prendendo" a interface —
   se sim, precisaremos de `usb_detach_kernel_driver` no pyusb.

## FASE 2 — Captura de tráfego USB no Linux (usbmon)

Como não tenho Windows, a captura será feita com `usbmon` nativo do Linux
e analisada no Wireshark (ou tshark em CLI).

1. Me guie a carregar o módulo: `sudo modprobe usbmon`
2. Descubra o barramento correto em `/sys/kernel/debug/usb/usbmon/`
   (o mesmo que aparece em `lsusb -t` como "Bus XX").
3. Inicie captura: `sudo tshark -i usbmonX -w captures/session.pcap`
   (ou `dumpcap`, ou `cat /sys/kernel/debug/usb/usbmon/Xu > capture.txt`
   como fallback puro).
4. Enquanto isso, execute um script Python mínimo com pyusb que:
   - Encontre o dispositivo
   - Faça detach do kernel driver se necessário
   - Reivindique a interface PHDC
   - Envie o ASSOCIATION_REQUEST (0xE2 0x00 + payload conforme protocolo
     Tidepool)
   - Registre TODOS os bytes enviados e recebidos (hexdump com timestamp)
5. Pare a captura e me ajude a correlacionar o `.pcap` com o hexdump do
   script. O objetivo é validar que o script está gerando o mesmo tráfego
   que o software oficial geraria (o que sabemos pelos padrões Tidepool).

## FASE 3 — Implementação do cliente Python

Crie um projeto organizado:
