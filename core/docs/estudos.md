# Estudos científicos — métricas glicêmicas e como interpretá-las

> **Aviso.** Este documento é material técnico de apoio ao projeto
> `accuchek`. Ele **não** é orientação médica, não é diagnóstico e não
> substitui a consulta com um profissional de saúde. Os números gerados pelo
> relatório (`python -m src.cli report`) são **descritivos** — mostram o que
> o aparelho registrou, nada mais.

Documento compilado em **2026-10-21**. Todas as referências abaixo foram
verificadas na fonte (PMID/DOI indicados).

---

## 1. Por que este documento existe

O aparelho lê **glicosemias capilares** (SMBG — *self-monitoring blood
glucose*), uma leitura por vez, feita pelo usuário. Isso é radicalmente
diferente de um **sensor contínuo (CGM)**, que mede a glicose intersticial a
cada 1–5 minutos, 24 h por dia.

A maioria das métricas "modernas" da diabetes — Tempo em Faixa (TIR), GMI,
coeficiente de variação — foi **definida e validada em CGM**. Aplicá-las a um
glicosímetro é legítimo e útil, mas exige explicitar as limitações.

Este documento responde a três perguntas:

1. **O que cada número do relatório significa** e de onde vem a fórmula.
2. **Qual é a meta** de cada métrica (e para qual população).
3. **O que muda** quando os dados vêm de um glicosímetro e não de um CGM.

---

## 2. As métricas e suas fórmulas

### 2.1 Tempo em Faixa (TIR / TBR / TAR)

O **Tempo em Faixa** é a porcentagem do tempo com glicose entre
**70 e 180 mg/dL** (3,9–10,0 mmol/L). O complemento é dividido em:

| Faixa | Limite | Nome |
|---|---|---|
| Nível 2 baixa | < 54 mg/dL (3,0 mmol/L) | *Very Low* / hypoglycemia grave |
| Nível 1 baixa | 54–69 mg/dL | *Low* |
| **Alvo** | **70–180 mg/dL** | ***Time in Range*** |
| Nível 1 alta | 181–250 mg/dL | *High* |
| Nível 2 alta | > 250 mg/dL (13,9 mmol/L) | *Very High* |

> Battelino T, Danne T, Bergenstal RM, et al. "Clinical Targets for
> Continuous Glucose Monitoring Data Interpretation: Recommendations From the
> International Consensus on Time in Range." *Diabetes Care*.
> 2019;42(8):1593–1603. DOI: [10.2337/dci19-0028](https://doi.org/10.2337/dci19-0028)

O consenso também fixa a **frequência de dados** mínima para que o número
signifique alguma coisa:

> "…> 70% use of CGM over the most recent 14 days correlates strongly with
> 3 months of mean glucose, time in ranges, and hyperglycemia metrics."

Isto é, o sensor precisa estar ativo **≥ 70% das horas de 14 dias**. Um
glicosímetro usado 2 vezes por semana **não** satisfaz esse critério — e o
TIR que sai dos seus dados, portanto, é uma fração de leituras, não de
tempo.

### 2.2 GMI — *Glucose Management Indicator*

```
GMI (%) = 3.31 + 0.02392 × glicemia média (mg/dL)
GMI (mmol/mol) = 12.71 + 4.70587 × glicemia média (mmol/L)
```

Deriva de uma regressão entre glicemia média de CGM (Dexcom G4) e HbA1c de
laboratório em 528 participantes de 4 ensaios randomizados.

> Bergenstal RM, Beck RW, Close KL, et al. "Glucose Management Indicator
> (GMI): A New Term for Estimating A1C From Continuous Glucose Monitoring."
> *Diabetes Care*. 2018;41(11):2275–2280.
> DOI: [10.2337/dc18-1581](https://doi.org/10.2337/dc18-1581)

Tabela de referência do próprio artigo:

| Glicemia média (mg/dL) | 100 | 125 | 150 | 175 | 200 | 225 | 250 | 300 |
|---|---|---|---|---|---|---|---|---|
| **GMI (%)** | 5,7 | 6,3 | 6,9 | 7,5 | 8,1 | 8,7 | 9,3 | 10,5 |

Cada +25 mg/dL de média ⇒ **+0,6% de GMI**.

O GMI **não** promete igualar a HbA1c de laboratório. A FDA proibiu o uso do
termo "eA1c" justamente porque ele sugere uma correspondência que não existe.
Quando o GMI e a HbA1c divergem, o motivo pode ser do sensor, do regime de
tratamento, ou de condições que alteram a HbA1c (anemia, hemoglobinopatias,
ferropenia, gestação).

### 2.3 eA1c (estudo ADAG)

```
eA1c (%) = (glicemia média mg/dL + 46,7) / 28,7
```

(Equivalente a `eAG (mg/dL) = 28,7 × HbA1c − 46,7`.)

> Nathan DM, Ellis P, Bergenstal RM, et al. "Translating the A1C assay into
> estimated average glucose values." *Diabetes Care*. 2008;31(8):1571–1580.
> DOI: [10.2337/dc08-1262](https://doi.org/10.2337/dc08-1262)

A SBD usa a mesma constante: "HbA1c próximos a 7% correspondem a glicemias
médias diárias de aproximadamente 154 mg/dL, variando de 122 a 184 mg/dL".

O relatório calcula **os dois** (GMI e eA1c-ADAG) para deixar visível a
diferença entre eles — que aqui é de ~0,35% de HbA1c, a diferença entre as
duas retas de regressão.

### 2.4 Coeficiente de variação (CV) — variabilidade

```
CV (%) = desvio-padrão / média × 100
```

Meta: **CV ≤ 36%** para adultos com diabetes em tratamento com insulina ou
sulfonilureia. Acima disso, considera-se variabilidade alta (instabilidade
glicêmica).

> Danne T, Savage MW, Bergenstal RM, et al. "International Consensus on Use
> of Continuous Glucose Monitoring." *Diabetes Care*. 2017;40(6):1591–1603.
> DOI: [10.2337/dci17-0037](https://doi.org/10.2337/dci17-0037)

> ⚠️ **O CV é uma das poucas métricas que a SBD aceita calcular a partir de
> glicemia capilar** — ver [§4.3](#43-o-cv-e-uma-exceção-interessante).

### 2.5 Relação TIR ↔ HbA1c

Dois estudos que ancoram a relação:

| TIR 70–180 | HbA1c estimado (Beck, n=545, T1D) | (Vigersky & McMahon, n=1137) |
|---|---|---|
| 20% | 9,4% | 10,6% |
| 50% | 7,9% | 8,3% |
| **70%** | **7,0%** | **6,7%** |
| 90% | 6,0% | 5,1% |

Regra prática: **cada +10% de TIR ≈ −0,5% de HbA1c** (ou −0,8%, no conjunto
amplo de ECRs). E: "Each incremental 5% increase in TIR is associated with
clinically significant benefits."

### 2.6 Validade clínica do TIR (e por que ele existe)

> Beck RW, Bergenstal RM, Riddlesworth TD, et al. "Validation of Time in
> Range as an Outcome Measure for Diabetes Clinical Trials." *Diabetes Care*.
> 2019;42(3):400–413. DOI: [10.2337/dc18-1444](https://doi.org/10.2337/dc18-1444)

Usando os perfis de **7 pontos do DCCT** (1.440 participantes com DM1):
para cada **10 pontos percentuais a menos de TIR**, o risco de progressão de
retinopatia subiu **64%** (IC 95%: 51–78) e o de microalbuminúria **40%**
(IC 95%: 25–56). Esse é o estudo que validou o TIR como desfecho — e,
relevante para este projeto, ele usou **glicosímetro**, não CGM.

---

## 3. As metas

### 3.1 Consenso internacional (Battelino 2019)

**Adultos com DM1 ou DM2** (e idosos/alto risco):

| Métrica | Meta | Equivalente (24 h) |
|---|---|---|
| TIR (70–180) | **> 70%** | > 16 h 48 min |
| TBR < 70 | **< 4%** | < 1 h |
| TBR < 54 | **< 1%** | < 15 min |
| TAR > 180 | **< 25%** | < 6 h |
| TAR > 250 | **< 5%** | < 1 h 12 min |

**Idosos ou de alto risco** (risco de hipoglicemia grave): TIR **> 50%**,
TBR < 70 **< 1%**, TAR > 250 **< 10%**.

**Gestação**: TIR 63–140 mg/dL > 70% (T1D) — e as metas de SMBG
pré- e pós-prandial **continuam valendo**.

**Prioridade clínica**: reduzir primeiro a TBR, depois o TIR.

### 3.2 ADA — *Standards of Care* 2026

> American Diabetes Association Professional Practice Committee. "6. Glycemic
> Goals, Hypoglycemia, and Hyperglycemic Crises: Standards of Care in
> Diabetes—2026." *Diabetes Care*. 2026;49(Suppl. 1):S132–S149.
> DOI: [10.2337/dc26-S006](https://doi.org/10.2337/dc26-S006)

- Meta de **HbA1c < 7%** para a maioria dos adultos não gestantes (recomendação
  6.3a, nível A).
- **TIR > 70%** "em pessoas que usam CGM" (6.3b, nível B).
- Tempo < 70 mg/dL **< 4%** (< 1% para idosos) e < 54 mg/dL **< 1%** (6.3c, B).
- Glicemia capilar pré-prandial **80–130 mg/dL**; pico pós-prandial **< 180 mg/dL**.
- **CV ≤ 36%**.
- Classificação de hipoglicemia: **nível 1** (< 70 mg/dL), **nível 2**
  (< 54 mg/dL), **nível 3** (evento grave, precisa de ajuda de terceiros).

> Observação honesta: o texto da ADA diz explicitamente *"in people using
> CGM"*. As metas de TIR **não** foram escritas para glicosímetro.

### 3.3 SBD — Diretriz da Sociedade Brasileira de Diabetes

> Bertoluci MC, Forti AC, Almeida-Pititto B, et al. "Diretriz da Sociedade
> Brasileira de Diabetes — Edição 2025." DOI: [10.29327/5660187](https://doi.org/10.29327/5660187)
> (capítulo "Metas de controle glicêmico", edições 2025/2026, em
> `diretriz.diabetes.org.br`)

| | Adultos | Idoso saudável | Idoso comprometido | Criança/adolescente |
|---|---|---|---|---|
| HbA1c | < 7,0% | < 7,5% | < 8,0% (ed. 2026) | < 7,0% |
| Jejum / pré-prandial | 80–130 | 80–130 | 90–150 | 70–130 |
| 2 h pós-prandial | < 180 | < 180 | < 180 | < 180 |
| Ao deitar | 90–150 | 90–150 | 100–180 | 110–200 |
| TIR 70–180 | > 70% | > 70% | > 50% | > 70% |
| T hipog < 70 | < 4% | < 4% | < 1% | < 4% |
| T hipog < 54 | < 1% | < 1% | 0 | < 1% |

Duas observações da SBD que interessam diretamente a este projeto:

1. **Recomendação R9**: "…a variabilidade glicêmica, medida através do
   cálculo do coeficiente de variação deva ser < 36%, obtido através de
   dispositivos de monitorização contínua de glicose **ou valores de glicemia
   capilar**."
2. "A glicemia média diária estimada também pode ser obtida através da média
   dos dados dos glicosímetros com softwares próprios, sendo estas **mais
   fidedignas, tanto quanto mais frequentes forem as aferições diárias**."

Ou seja: a diretriz brasileira reconhece explicitamente o **CV** e a **média
glicêmica** calculados a partir de glicosímetro, e valoriza a frequência
de aferição.

---

## 4. As limitações de usar um glicosímetro como se fosse CGM

Esta é a seção mais importante deste documento.

### 4.1 O TIR de SMBG é uma fração de *leituras*, não de *tempo*

O TIR pressupõe que se está medindo **todo o tempo**. Com um glicosímetro,
a porcentagem é "quantas das minhas medições caíram dentro da faixa" — e o
conjunto de medições é **auto-selecionado**: mede-se quando há suspeita de
que algo está acontecendo (antes da refeição, ao sentir sintomas), e
raramente de madrugada.

### 4.2 O período noturno simplesmente não existe nos dados

O estudo de validação do TIR (Beck 2019) usa perfis de 7 pontos do DCCT e
**reconhece isso explicitamente**:

> "There are certain limitations inherent in using seven-point testing data
> compared with CGM data. With seven-point testing, there is limited ability
> to assess glycemic variability and interday variation within and between
> individuals. In addition, the seven-point data are **solely from daytime**,
> and thus the calculation of TIR and the other metrics does not include the
> overnight period. **This could produce an underestimate of TIR**; however,
> it is unlikely to have an effect on the association of TIR with
> complications."

Consequência prática: hipoglicemia noturna — justamente a mais perigosa — é
**invisível** num conjunto de dados de glicosímetro. Um TIR de 94% com 1,7%
abaixo de 70 mg/dL **não significa** ausência de hipoglicemia noturna.

### 4.3 O CV é uma exceção interessante

O CV é uma medida de **dispersão**, e não de cobertura temporal: ele é
calculado sobre a distribuição dos valores, não sobre o tempo. Por isso a SBD
o aceita de glicemia capilar. Ainda assim, se a variabilidade real ocorre
entre as medições (e não dentro delas), o CV de SMBG **subestima** a
variabilidade inter-diarária.

### 4.4 A precisão do próprio aparelho

**ISO 15197:2013** (sistemas de automonitorização de glicemia para
autoteste) exige que:

- **≥ 95%** dos resultados fiquem dentro de **± 15 mg/dL** do valor de
  referência para glicemias **< 100 mg/dL**;
- **≥ 95%** dos resultados fiquem dentro de **± 15%** para glicemias
  **≥ 100 mg/dL**;
- **≥ 99%** dos resultados caiam nas zonas A e B da *Consensus Error Grid*
  (Parkes) — ou seja, no máximo 1% dos resultados podem levar a uma decisão
  clínica incorreta.

> ISO 15197:2013 — *In vitro diagnostic test systems — Requirements for
> blood-glucose monitoring systems for self-testing in managing diabetes
> mellitus*. Ver também a análise comparativa de Freckmann et al.,
> *J Diabetes Sci Technol* 2015 (PMC4525642).

Consequência: uma leitura "100 mg/dL" pode ser, no glicosímetro, de 87 a
113 mg/dL. O erro analítico (≈ ±15%) é **da mesma ordem** que a diferença
entre 70 e 90 mg/dL — ou seja, **leituras próximas do limite da faixa-alvo
têm incerteza relevante**. Isso não é motivo para ignorar o dado, mas
significa que uma leitura isolada de 68 ou de 185 mg/dL **não** deve ser
interpretada como evento.

O **Accu-Chek Active** é um aparelho antigo (bcdDevice 0.06, Around 2008) e
reporta resultados **equivalentes a plasma**.

### 4.5 O relógio do aparelho esteve ~7 anos atrasado (resolvido)

O `TIME_ABS` do Active devolve `2019-11-12` enquanto a data real é
`2026-10-21`. Medido em 6 pontos, o desvio é **constante ao segundo**
(2535 d 11:06:32) e a **deriva é zero** — o relógio corre 1:1 com o tempo
real; só o *ponto de partida* está errado.

Uma troca de bateria feita no meio do teste **não alterou** o relógio nem os
registros, o que mostra que o RTC não depende da bateria trocada (há um
elemento de backup, ou o relógio foi configurado errado e segue correndo).

O que isso afeta:

- **Datas absolutas** — as leituras aparecem com o carimbo do relógio do
  aparelho, que estava anos atrasado. É a mesma base temporal usada
  para os cálculos de todos os gráficos, então os resultados são
  **internamente consistentes**, mas o deslocamento em relação ao calendário
  real não pode ser descartado.
- **O que NÃO é afetado** — intervalos entre medições, taxa de variação,
  médias móveis, CV, TIR (fração de leituras), tendência (depende só da
  ordenação temporal) e todos os valores em mg/dL. Nenhum desses depende de
  a hora estar certa.

Em outras palavras: **as conclusões clínicas deste relatório não mudam**,
mas a pergunta "quando eu medi isso?" tem resposta aproximada.

O projeto **não** corrige o relógio por USB. Fazer isso exigiria o comando
`SET_TIME` (`0C 17`), que é proibido: o cliente é somente leitura.

⚠️ **Atenção prática:** com o relógio 7 anos atrás, uma medição feita agora
seria carimbada como `2019-11-12` — **antes** de todos os registros já
existentes — e a linha do tempo do conjunto embaralharia.

**✅ Resolvido em 2026-10-21 14:05:** a data e a hora foram ajustadas **no
menu do próprio aparelho** (que não passa pelo USB e portanto não viola a
regra somente-leitura do projeto). O desvio passou de 2535 dias para
**30 segundos, constantes** — ou seja, o relógio está sincronizado. As
medições novas saem com a data correta (2026-10-21), **depois** das
antigas, e a linha do tempo do conjunto fica coerente.

As leituras já gravadas mantêm o carimbo antigo, mas como o relógio antigo
corria 1:1 com o real, o que ele fez foi **deslocar a série toda de 2535
dias** — as formas das curvas (tendência, perfil por hora, mapa de calor) e
todas as métricas glicêmicas permanecem válidas. Apenas a ancoragem no
calendário é aproximada para as leituras antigas.

### 4.6 Resumo das limitações

| Métrica | Confiabilidade com SMBG | Por quê |
|---|---|---|
| Glicemia média | **boa** | não depende de cobertura temporal |
| Mediana, Q1/Q3, IQR, min, max | **boa** | idem |
| GMI / eA1c | **boa** | idem (mas o GMI foi validado em CGM) |
| CV | **razoável** | dispersão, não cobertura (aceito pela SBD) |
| TIR/TBR/TAR | **aproximação** | depende de cobertura; período noturno ausente |
| Tendência (regressão) | **razoável** | precisa de pontos em dias distintos |
| Perfil por hora | **viés de seleção** | quem mede à noite? quem sente sintomas? |
| Eventos de hipoglicemia | **piso, não estimativa** | só conta o que foi medido |
| Datas absolutas | **aproximadas** | o relógio do aparelho está 2535 dias atrasado (§4.5) |

---

## 5. Interpretar os achados: o que cada gráfico do relatório mostra

### 5.1 Séries temporais e faixa-alvo
Azul/verde = dentro de 70–180. Vermelho = abaixo de 70. Laranja = acima de
180. A faixa colorida ao fundo é **referência visual**, não uma meta
individual — a meta depende do seu perfil (ver §3).

### 5.2 Média diária e tendência
Regressão linear sobre as médias diárias. O que importa não é o sinal, é o
**r²**: com r² baixo, a "tendência" é ruído. Neste projeto, o relatório
mostra o `r²` e marca explicitamente quando a correlação é fraca.

### 5.3 Perfil por hora do dia
Mostra a mediana e o IQR por hora. **Cuidado com o viés**: se o usuário
mede às 3h da manhã, provavelmente é porque algo aconteceu ali — o perfil
vai super-representar a madrugada.

### 5.4 Mapa de calor hora × dia da semana
Mesma ressalva, ampliada: células com poucas leituras são ruído estatístico
(aqui a cor é a média, sem intervalo de confiança). Trate células com pouquíssimas
leituras como ausentes, não como "baixo".

### 5.5 Efeito *dawn* (fenômeno do amanhecer)
Aumento fisiológico da glicemia de madrugada por hormônios
contrarreguladores (cortisol, GH, glucagon, catecolaminas). É uma das
explicações clássicas para leituras altas ao acordar. **Também** pode ser
glicemia alta na véspera ("efeito Somogyi") — a distinção só é possível com
mais dados noturnos, que um glicosímetro não oferece.

### 5.6 Jejum × pós-prandial
A heurística implementada (`src/analysis.py::classify_by_meal`) classifica a
**primeira leitura do dia antes das 10h** como jejum e as leituras de
1,5–3 h depois como pós-prandiais. É uma aproximação: o aparelho tem um
segmento de refeições (`PMSegMeal`) que **ainda não é lido** — ver
`docs/protocol-notes.md`.

### 5.7 Sequências de hipoglicemia
A contagem de "sequências consecutivas" usa a lista ordenada, sem olhar o
intervalo entre medições: duas medições baixas com 30 min de intervalo
contam como um episódio. É a convenção do próprio CGM (episódios de ≥ 15 min).

---

## 6. Aplicação ao dataset de demonstração

> ⚠️ **O conjunto de dados publicado é sintético.** As leituras reais do
> aparelho são dado de saúde e **não** são publicadas — ver a seção
> [Privacidade](../README.md#privacidade). O dataset de demonstração
> (`examples/data_sintetico.json`) reproduz o **layout** do aparelho real
> — 121 leituras, 80 + 41 em dois segmentos, modelo 2102 — com **valores
> fictícios**. A tabela abaixo é o exemplo de como aplicar a metodologia
> §1–§5 a um conjunto com esta estrutura, não o resultado clínico de
> ninguém.

Os 121 registros de demonstração (2024-01-01 → 2024-11-29, modelo 2102,
série XXXXXXXXX) produzem:

| Métrica | Valor | Meta | Leitura |
|---|---|---|---|
| n | 121 | — | cobertura de 59 dias em 334 (17,7%) |
| Média | 128,5 mg/dL (7,1 mmol/L) | — | GMI 6,4% / eA1c 6,1% |
| Mediana | 131 mg/dL | — | distribuição quase simétrica |
| DP / CV | 29,7 / **23,1%** | ≤ 36% | ✅ variabilidade aceitável |
| TIR 70–180 | **91,7%** | > 70% | ⚠️ otimista: sem dados noturnos |
| TBR < 70 | 4,1% (5 leituras) | < 4% | ⚠️ acima da meta |
| TBR < 54 | 0,8% (1 leitura) | < 1% | ✅ |
| TAR > 180 | 4,1% (5 leituras) | < 25% | ✅ |
| Tendência | −0,019 mg/dL/dia (r² = 0,006) | — | **ruído** — sem tendência real |

No conjunto real, o aparelho devolveu leituras fora de escala (`±INF` → 9 e
601 mg/dL) e uma delas coincidiu com uma **leitura genuína** de 9 mg/dL — a
flag `out_of_range` no JSON é o que separa os dois casos. A de 601 mg/dL é
`+INF` do aparelho (valor sentinela, não uma glicemia real de 601). O
parser e o dataset sintético reproduzem esse tratamento.

**Interpretação honesta:** com 17,7% de cobertura e sem dados noturnos, o
"TIR de 92%" diz mais sobre *quando* a pessoa mede do que sobre o controle
glicêmico real. Os números **mais confiáveis** aqui são a **média de
128 mg/dL** e o **CV de 23%** — que, pelo menos, é consistente com um
controle razoável nos momentos observados. A **ausência de variabilidade
elevada** e o GMI em torno de 6,4% são os achados mais sólidos.

---

## 7. O que este projeto **não** faz (e por quê)

- **Não** calcula risco de hipoglicemia noturna (sem dados).
- **Não** substitui a HbA1c de laboratório.
- **Não** valida o aparelho contra um método de referência (ISO 15197 exige
  ensaio com ≥ 100 amostras de ≥ 100 pacientes).
- **Não** emite diagnóstico, nem sugestão de dose, nem alerta deoterapia.
- **Não** envia nada ao aparelho: o protocolo implementado é **estritamente
  de leitura** (ver `AGENTS.md`, regra 1).
- **Não** define meta individual: as metas do §3 são populacionais.

---

## 8. Referências

1. **Battelino T**, Danne T, Bergenstal RM, et al. Clinical Targets for
   Continuous Glucose Monitoring Data Interpretation: Recommendations From
   the International Consensus on Time in Range. *Diabetes Care*.
   2019;42(8):1593–1603. DOI: 10.2337/dci19-0028. PMID: 31177185.
2. **Bergenstal RM**, Beck RW, Close KL, et al. Glucose Management Indicator
   (GMI): A New Term for Estimating A1C From Continuous Glucose Monitoring.
   *Diabetes Care*. 2018;41(11):2275–2280. DOI: 10.2337/dc18-1581.
   PMID: 30224348.
3. **Nathan DM**, Ellis P, Bergenstal RM, et al. Translating the A1C assay
   into estimated average glucose values. *Diabetes Care*.
   2008;31(8):1571–1580. DOI: 10.2337/dc08-1262.
4. **Danne T**, Savage MW, Bergenstal RM, et al. International Consensus on
   Use of Continuous Glucose Monitoring. *Diabetes Care*. 2017;40(6):1591–1603.
   DOI: 10.2337/dci17-0037.
5. **Beck RW**, Bergenstal RM, Riddlesworth TD, et al. Validation of Time in
   Range as an Outcome Measure for Diabetes Clinical Trials. *Diabetes Care*.
   2019;42(3):400–413. DOI: 10.2337/dc18-1444. PMID: 30352896.
6. **Hirsch IB**, Sherr JL, Hood KK. Connecting the Dots: Validation of Time
   in Range Metrics With Microvascular Outcomes. *Diabetes Care*.
   2019;42(3):368–370. DOI: 10.2337/dci18-0040.
7. **American Diabetes Association** Professional Practice Committee. 6.
   Glycemic Goals, Hypoglycemia, and Hyperglycemic Crises: Standards of Care
   in Diabetes—2026. *Diabetes Care*. 2026;49(Suppl. 1):S132–S149.
   DOI: 10.2337/dc26-S006.
8. **Bertoluci MC**, Forti AC, Almeida-Pititto B, et al. *Diretriz da Sociedade
   Brasileira de Diabetes — Edição 2025*. DOI: 10.29327/5660187.
   Capítulo "Metas de controle glicêmico", `diretriz.diabetes.org.br`.
9. **Freckmann G**, Schmid C, Baumstark A, Rutschmann M, Haug C. Analytical
   Performance Requirements for Systems for Self-Monitoring of Blood Glucose
   With Focus on System Accuracy. *J Diabetes Sci Technol*. 2015;9(2):309–314.
   PMC4525642.
10. **ISO 15197:2013**. In vitro diagnostic test systems — Requirements for
    blood-glucose monitoring systems for self-testing in managing diabetes
    mellitus. International Organization for Standardization.
11. **ISO/IEEE 11073-20601**. Health informatics — Device communication —
    Part 20601: Generic device communication (nível de aplicação PHDC).
12. **ISO/IEEE 11073-10417**. Health informatics — Device health management —
    Part 10417: Device specialization for glucose monitoring (perfil do
    glicosímetro).
13. **Mazze M**, et al. *Ambulatory Glucose Profile* (AGP) — o modelo de
    relatório visual de 30 dias, padronizado e endossado pelo consenso
    internacional (Battelino 2019, ref. 24/67).
14. **Tidepool** `uploader` — `lib/drivers/roche/accuChekUSB.js` e
    `lib/drivers/roche/utils.js`. Driver de referência (origem do port
    `emogenet/accuchek`). <https://github.com/tidepool-org/uploader>

---

## 9. Como manter este documento

Ao atualizar o código de análise (`src/analysis.py`), revisar:

- a fórmula e a fonte de cada métrica;
- se a nova métrica precisa de ressalva metodológica (seção 4);
- a tabela da seção 6, se os dados reais mudarem;
- o rodapé do relatório (`src/report.py::DISCLAIMER` e `REFERENCES`).
