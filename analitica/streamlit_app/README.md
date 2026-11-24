# App Streamlit — Derecho WRF

Una pestaña por pregunta (P1–P7) y un **Explorador libre**. Filtros globales en la barra lateral:
ventana de tiempo (UTC), esquema, ciudades, umbral de viento severo y tamaño de rankings.
Cada pestaña muestra la consulta SQL que se ejecutó.

## Ejecutar

```bash
pip install -r requirements.txt
# con datos reales (credenciales AWS activas y tablas catalogadas):
AWS_REGION=us-east-1 ATHENA_WORKGROUP=p2-derecho streamlit run app.py
# solo para ver la interfaz (datos inventados):
DERECHO_DEMO=1 streamlit run app.py
```

## Archivos
- `app.py` — interfaz.
- `queries.py` — SQL (Athena) de cada pregunta, parametrizado por los filtros.
- `datos.py` — ejecuta en Athena o genera datos de demostración.

## Pendiente
- Validar las consultas contra las tablas reales (nombres de columnas tomados del código de B).
- Despliegue con API Gateway: hoy la app llama a Athena directo con boto3. Si se exige
  API Gateway → Lambda → Athena, se reemplaza `datos.ejecutar_athena` por una llamada HTTP
  sin tocar el resto.
