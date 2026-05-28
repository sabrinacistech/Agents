# Java Unit Testing Skills

Skills de testing unitario puro para proyectos Java.
Sin tests de integración — todo resuelto con mocks y JUnit 5.

## Estructura

```
java-testing-skills/
├── README.md                                   ← este archivo
│
├── Fundamentos
│   ├── 01-testeable-design.md                  ← código que se puede testear
│   ├── 02-test-structure-aaa.md                ← patrón AAA / Given-When-Then
│   ├── 03-test-naming.md                       ← nombres que son especificaciones
│   └── 04-test-toolstack.md                    ← JUnit 5 + Mockito + AssertJ + PIT
│
├── Buenas prácticas
│   ├── 05-test-first-principles.md             ← Fast, Isolated, Repeatable, Self-validating
│   ├── 06-test-doubles.md                      ← Stub vs Mock vs Fake vs Spy
│   ├── 07-test-parameterized.md                ← @ParameterizedTest, edge cases, nulos
│   └── 08-test-coverage-quality.md             ← branch coverage + mutation testing
│
└── Antipatrones
    ├── 09-antipattern-mystery-guest-logic.md   ← datos ocultos + lógica en tests
    ├── 10-antipattern-coupled-brittle.md       ← tests acoplados + tests frágiles
    ├── 11-antipattern-eager-sleeping.md        ← eager test + Thread.sleep
    └── 12-antipattern-overmocking-assertfree.md ← over-mocking + tests sin asserts
```

## Stack de herramientas

| Herramienta | Versión | Propósito |
|-------------|---------|-----------|
| JUnit 5 (Jupiter) | 5.10.x | Framework de tests |
| Mockito | 5.11.x | Test doubles (mock, stub, spy) |
| AssertJ | 3.25.x | Assertions fluidas y legibles |
| JaCoCo | 0.8.x | Cobertura de ramas (branch coverage) |
| PIT | 1.15.x | Mutation testing |
| Awaitility | 4.2.x | Tests asíncronos sin Thread.sleep |

## Orden de adopción recomendado

1. Empezar por `01-testeable-design.md` — si el diseño no lo permite, nada más funciona.
2. Establecer `02-test-structure-aaa.md` y `03-test-naming.md` como estándar de equipo.
3. Configurar el stack con `04-test-toolstack.md`.
4. Revisar los antipatrones (`09` al `12`) en el código existente.
5. Agregar `08-test-coverage-quality.md` (JaCoCo + PIT) al pipeline de CI.

## Principio guía

> Testear comportamiento observable, no implementación interna.
> Un test que falla al refactorizar sin cambiar el contrato es un test mal escrito.
