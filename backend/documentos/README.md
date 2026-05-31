# 📚 Documentos del RAG (base de conocimiento)

Aquí pones los documentos con los que cada personaje responde en el chat.

## Reglas

1. **Una carpeta por personaje.** El nombre de la carpeta debe ser el `personaje_id`
   (el mismo que en `backend/personajes.py`). Carpetas actuales:
   - `triceratops/`
   - `t-rex/`
   - `leonardo_da_vinci/`
   - `sherlock_holmes/`

2. **Idioma: INGLÉS.** Los documentos deben estar en inglés (los embeddings funcionan
   mucho mejor). La pregunta del niño se traduce ES→EN automáticamente al preguntar.

3. **Formatos admitidos:** `.pdf`, `.txt`, `.md`.

4. Un documento que sirva a dos personajes (p. ej. una enciclopedia de dinosaurios para
   `triceratops` y `t-rex`) se **copia** en ambas carpetas.

## Cómo indexar (primera vez y cada vez que cambies documentos)

Desde la raíz del proyecto, con el entorno virtual activado:

```powershell
python -m backend.ingest
```

Esto trocea los documentos (chunking con solape) e indexa los fragmentos en ChromaDB.
Reconstruye la colección desde cero cada vez (reindexado limpio).

> Los archivos `*_ejemplo.md` que vienen de muestra son solo para que puedas probar el
> pipeline de inmediato. Bórralos y pon tus documentos reales cuando quieras.
