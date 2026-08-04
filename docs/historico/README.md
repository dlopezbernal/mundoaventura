# Documentos históricos

> ⚠️ **Documentos históricos.** Estos ficheros registran el diseño y el encargo de
> funcionalidades **ya implementadas**. Se conservan como memoria del proceso, pero
> **no describen el estado actual** del sistema y pueden contener detalles que
> quedaron superados. Para la arquitectura vigente, ver
> [`../ARQUITECTURA.md`](../ARQUITECTURA.md), [`../DECISIONES.md`](../DECISIONES.md) y
> el `CLAUDE.md` de la raíz.

| Documento | Qué es | Estado |
|---|---|---|
| [create-user-config.md](create-user-config.md) | Plan por hitos del **menú de configuración sin código** (que cualquier adulto pueda configurar la app sin tocar el código): alcance, decisiones técnicas y criterios de aceptación. | Implementado (menú ⚙️ Configuración / 🛡️ Admin). |
| [claude-code-config-implementacion.md](claude-code-config-implementacion.md) | Brief ejecutable que guió la implementación del menú por fases; contiene la corrección clave sobre el **umbral del RAG** (distancia coseno directa, sin porcentaje). | Implementado. |

El plan de trabajo por hitos (H1–H10) vive en [`../plan/`](../plan/); las decisiones
justificadas, en [`../decisiones/`](../decisiones/).
