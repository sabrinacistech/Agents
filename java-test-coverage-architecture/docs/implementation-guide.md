# Implementation Guide

## Paso 1
Ejecutar discovery y completar `state/build-tool-contract.json`.

## Paso 2
Clasificar clases y completar `state/classification-index.json`.

## Paso 3
Para cada clase objetivo, generar contrato en `state/symbol-contracts.json`.

## Paso 4
Crear grafo de dependencias y fixtures.

## Paso 5
Leer JaCoCo XML y crear `state/coverage-targets.json`.

## Paso 6
Generar batch pequeño de tests.

## Paso 7
Validar con narrow test runner.

## Paso 8
Si falla, parsear error y reparar de forma determinística.

## Paso 9
Generar reporte final con evidencia.
