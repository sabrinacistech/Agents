# Compile Error Parser

## Objetivo
Convertir stderr de `javac`/Maven en `state/compile-error-index.json` accionable por el Repair Agent.

## Entrada
- stdout/stderr de `mvn -pl <m> -Dtest=<FQCN> test-compile` o `test`.
- Archivos de log: `target/surefire-reports/*.txt`.

## Procedimiento
1. Capturar líneas con patrón:
   `[ERROR] <ruta>:[<line>,<col>] <mensaje>`
2. Clasificar por código canónico (tabla más abajo) usando regex sobre el mensaje.
3. Extraer símbolo afectado (FQCN, método, parámetro).
4. Calcular `hash = sha256(errorCode + symbolFQN + fixIdCandidate)` para alimentar G7.

## Códigos canónicos

| Código | Patrón | Reparación sugerida |
|--------|--------|---------------------|
| `E_IMPORT_UNRESOLVED` | `cannot find symbol\s+class\s+(\w+)` con import previo | quitar import / reemplazar por FQCN de whitelist |
| `E_PACKAGE_UNRESOLVED` | `package (\S+) does not exist` | quitar import; marcar paquete prohibido |
| `E_METHOD_UNRESOLVED` | `cannot find symbol\s+method\s+(\w+)\(` | reemplazar por método del contrato; si no existe, eliminar |
| `E_CONSTRUCTOR_UNRESOLVED` | `constructor \S+ in class \S+ cannot be applied` | usar constructor del contrato; si solo private, usar factory/builder |
| `E_INTERFACE_INSTANTIATION` | `\S+ is abstract; cannot be instantiated` | aplicar `interface-instantiation-rules.md` |
| `E_TYPE_MISMATCH` | `incompatible types: (\S+) cannot be converted to (\S+)` | revisar firma; ajustar fixture |
| `E_GENERIC_INFERENCE` | `incompatible types: inference variable` | tipar explícitamente generics |
| `E_VARARGS` | `non-varargs call of varargs method` | castear primer argumento |
| `E_OVERRIDE` | `method does not override` | quitar `@Override` o ajustar firma |
| `E_ACCESS` | `\S+ has private access` | usar API pública/builder/factory |

## Salida: `state/compile-error-index.json`

```json
{
  "schemaVersion": 1,
  "runId": "cycle-3",
  "errors": [
    {
      "id": "err:0001",
      "code": "E_METHOD_UNRESOLVED",
      "file": "src/test/java/com/acme/FooServiceTest.java",
      "line": 42,
      "col": 18,
      "message": "cannot find symbol method setFoo(java.lang.String)",
      "symbolFQN": "com.acme.Order#setFoo(java.lang.String)",
      "raw": "[ERROR] .../FooServiceTest.java:[42,18] cannot find symbol ..."
    }
  ]
}
```
