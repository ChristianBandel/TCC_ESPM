# Coleta de dados (manual)

## Petróleo

```powershell
python 1_Coleta_Dados/coletar_petroleo.py
```

## Conflitos

1. **Recomendado:** baixar [UCDP GED 25.1](https://ucdp.uu.se/downloads/) (CSV) e:
   ```powershell
   python 1_Coleta_Dados/coletar_conflitos.py --csv C:\caminho\ged251.csv
   ```

2. **API UCDP:** token em `.env` como `UCDP_ACCESS_TOKEN`

3. **Demonstração** (substitua antes da entrega do TCC):
   ```powershell
   python 1_Coleta_Dados/coletar_conflitos.py --exemplo
   ```
