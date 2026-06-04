# Indicadores macro

## Coleta

```powershell
python 1_Coleta_Dados/coletar_indicadores.py
```

**yfinance (sem chave):** VIX, DXY, WTI, S&P500, ouro.

**FRED (opcional):** defina `FRED_API_KEY` no `.env` para dólar, inflação breakeven, WTI/Brent FRED.

Saída: `dados/raw/indicadores_macro_semanal.csv`

## Integração

`preparar_dataset.py` faz merge por `semana_inicio` e cria:

- retornos e z-score 12 semanas por indicador
- `spread_brent_wti`
- `interacao_oriente_medio_x_vix`
