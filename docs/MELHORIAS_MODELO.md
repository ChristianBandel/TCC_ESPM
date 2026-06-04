# Como melhorar acuracia e R² (TCC)

## Por que o modelo atual falha?

1. **Poucos dados alinhados** (~330 semanas) para um problema ruidoso.
2. **Sinal fraco**: correlacao semanal global mortes x retorno futuro do Brent fica perto de **-0,04 a -0,11** — guerra em um pais nao move o Brent na mesma semana sempre.
3. **Alvo difícil**: "volatilidade alta/baixa" mistura choques de oferta, demanda, OPEP e guerra.
4. **R² negativo** = o regressor erra mais do que prever a media historica.

Isso **nao invalida o TCC** — voce documenta limitacoes e mostra o pipeline + cenarios Groq + tentativas de melhoria.

## O que ja foi melhorado no codigo

| Mudanca | Objetivo |
|---------|----------|
| Features por **regiao** (Oriente Medio, Europa, Africa petroleo) do GED | Captar onde a guerra importa para oleo |
| Alvo **`direcao_futura`** (sobe / cai / estavel) | Responder "petroleo cai ou sobe?" |
| `mortes_zscore`, `delta_mortes`, `log_mortes` | Picos de conflito vs normal |
| **HistGradientBoosting** + `class_weight=balanced` | Menos viés para uma classe |
| **Split temporal** (sem embaralhar) | Evitar vazamento de futuro |
| CV temporal no treino | Metrica mais honesta |

## O que VOCE ainda deve fazer (ordem de impacto)

### 1. Dados (maior ganho)

```powershell
python 1_Coleta_Dados/coletar_petroleo.py    # maximo historico API
python 1_Coleta_Dados/coletar_conflitos.py --csv 1_Coleta_Dados/GEDEvent_v25_1.csv
python 2_Preparacao_Dados/preparar_dataset.py
python 3_Modelagem/treinar_modelo.py
```

- Alinhar **mesma janela temporal** (petroleo e GED desde 2015).
- Nao usar semanas com `num_eventos = 0` se forem falha de merge — conferir CSV.

### 2. Pergunta de pesquisa mais realista

Em vez de "prever preco exato", usar no TCC:

- **Classificacao**: em semanas de **pico de mortes no Oriente Medio**, Brent **cai** ou **sobe** nas 4 semanas seguintes?
- **Event study**: comparar retorno medio apos choques (`choque_conflito=1`) vs semanas normais.

### 3. Modelagem avancada (se sobrar tempo)

- Janelas **mensais** (menos ruido que semanal).
- Incluir variaveis macro (dolar, estoques EIA) — FRED API.
- Modelo so para **Oriente Medio** (subconjunto GED).
- Ensemble ou XGBoost com busca de hiperparametros (`GridSearchCV` + `TimeSeriesSplit`).

### 4. Expectativa de metricas

| Metrica | Realista em TCC | Muito bom |
|---------|-----------------|-----------|
| Acuracia direcao | 40–55% | > 55% |
| R² retorno | 0 a 0,15 | > 0,2 |

Tres classes balanceadas: baseline aleatoria ~33%. **Bater 45%** ja e argumento com dados reais.

## Frase para o texto do TCC

> "O modelo aprende associacoes historicas fracas entre intensidade de conflito regional e movimento do Brent; a Groq gera cenarios futuros qualitativos, e o ML quantifica ordem de grandeza sob incerteza (R² e acuracia reportados com validacao temporal)."
