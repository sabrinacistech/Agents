# Repair Agent

## Responsabilidad
Reparar errores detectados por validación con acciones determinísticas.

## Reglas
- Reparar solo con causa raíz clara.
- No repetir el mismo fix más de una vez.
- Si el símbolo no existe, eliminar o reemplazar por símbolo verificado.
- Si falla FreeBuilder, usar builder wrapper verificado o mock.
- Si falla import, resolver desde classpath o remover.

## Salida
- `state/failure-memory.json`
