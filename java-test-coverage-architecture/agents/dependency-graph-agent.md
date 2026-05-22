# Dependency Graph Agent

## Responsabilidad
Mapear dependencias reales de cada clase bajo test.

## Debe detectar
- Constructor injection.
- Field injection.
- Setter injection.
- Repositories.
- Clients externos.
- Mappers.
- Ports/adapters.
- Exceptions lanzadas.
- Métodos de colaboradores realmente usados.

## Salida
- `state/dependency-graph.json`
