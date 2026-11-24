---
name: cd47-rxm-minmax-diario
description: Correr el proceso diario RXM (Min/Max) del CD 47: elegir SKUs con Min/Max dentro de la capacidad, bajar el CSV y cargarlo a Copérnico, y controlarlo contra el reporte de tareas.
---

# Proceso diario RXM (Min/Max) - CD 47

Contexto: CD 47 (Rappi Turbo AR, 3PL ID Logistics, WMS Copérnico). Responde en español rioplatense, corto y directamente usable.

## Qué es
Un simulador de tareas de reabasto (tab "Carga RXM" del tablero "Transferencias CD47 AR", repo OsoSuarez/cd47-volumen, publicado en https://ososuarez.github.io/cd47-volumen/). Cada día decide qué SKUs llevan Min/Max dentro de la capacidad, y exporta el CSV para Copérnico. Además muestra cuántas líneas (tareas) creamos y da visibilidad a 7 días, por día y por zona.

## Flujo de datos
- Sheet INVENTARIOS ID (tabs CORDENADAS, REFERENCIA, V L): lo lee el workflow de GitHub en cada corrida (recalc.py rellena tpl3.html).
- base.json: plan de Fountain9 que baja el bot. trv.json: TR (Excels publicados). La lógica corre en el navegador.
- Bot local: fountain9/run_planes.py (modos completo / F9_SOLO_BAJAR / F9_SOLO_LOCAL), filtrar_csv.py, csv_to_base_json.py. servidor_bot.py escucha en 127.0.0.1:9748. Si ya hay planes bajados en la carpeta de descargas, procesar_planes_locales.bat los sube sin entrar a Fountain9.

## Pasos diarios
1. Actualizar inventario en el Sheet y volver a publicar el TR antes de bajar el CSV (el stock tiene que estar fresco).
2. Si falta el plan del día: Ejecutar bot, modo completo (~20 min). Si ya están los dos archivos del plan en descargas: procesar_planes_locales.bat. Verificar que el muelle muestre números razonables (secos ~60k filas / ~4,3k SKUs; RyC ~18k filas / ~740 SKUs).
3. En "Carga RXM": revisar que "obligatorios sin cubrir" sea 0.
4. Bajar el CSV (producto,minStock,maxStock,diasCedi,diasProveedor,grupo). Tiene TODOS los SKUs de V L: los elegidos con Min/Max y el resto en 0/0.
5. Descargarlo después de medianoche, o usar la lógica de día+1 desde las 22:00 (propuesta, todavía no confirmada).
6. Cargarlo a Copérnico.

## Lógica (planRXM)
- Capacidad 696 tareas/día (546 secos / 150 frío) más tolerancia; el día 0 se escala para el turno 22:00-06:00.
- Por día y pool: primero los obligatorios (picking < demanda del día y stock en almacenaje > 0) hasta la capacidad; después los adelantos hasta el tope.
- Min/Max son múltiplos del MCM entre el lote del TR y el empaque de V L (cajas enteras). El Min es el piso para que dispare la tarea.
- SKUs sin Min/Max cargado: se sugiere un Max = demanda de 3 días.

## Detalle técnico para quien lo hereda
- Front: tpl3.html (tablero). recalc.py lee el Sheet con el secret GS_KEY en el workflow de GitHub y rellena tpl3.html; no hay clave en el repo.
- Bot (PC local): run_planes.py (modos completo / F9_SOLO_BAJAR / F9_SOLO_LOCAL), filtrar_csv.py (descarta qty=0, toma los 2 planes más nuevos por timestamp; el archivo más grande es secos y el más chico RyC), csv_to_base_json.py (arma base.json, hace push y dispara el workflow).
- servidor_bot.py: HTTP en 127.0.0.1:9748 (/run?modo=completo|bajar y /publicar-tr). programar_servidor_bot.bat deja un .vbs en la carpeta Startup de Windows para que arranque solo, sin admin.
- Gráfico semanal: en modo RXM usa la salida de planRXM (el modelo viejo daba ~417 tareas contra ~900 reales).
- Al commitear archivos a la PC por el puente, verificar el tamaño: a veces escribe una versión vieja sin avisar.

## Validación (18/11 vs reporte de Copérnico)
- Tareas: 897 simulador vs 904 Copérnico (-0,8%); 17/11: 723 vs 706 (+2,4%).
- Las 904 tareas reales cumplen la regla de selección; 879/904 SKUs (97%) coinciden, sin falsos positivos.
- Demanda: TR real 94.062 vs 104.166 en Copérnico (-10%): explica los SKUs faltantes (TR cargado 18:05, reporte 19:56).
- NO validado: unidades por tarea al llegar al Max. El 18/11 el WMS corrió la regla vieja RXX (Programado = Demanda + Min - Picking) y redondea a cajas, dejando 39 SKUs con diferencia.

## Riesgos a tener presentes
- Stock desactualizado y TR cargado antes de la hora del reporte.
- Carga masiva de Min/Max de Copérnico sin soporte nocturno: el 17/11 19:30 se cayó y se arregló el 18/11 11:30 (16 h).
- Días 2 a 7 son indicativos: el plan queda 22-24% debajo de la demanda real del TR.

## Go/NoGo vs el agente Min/Max de Global (según sus especificaciones, no corrido por nosotros)
Postura: todavía no. Su escritura a Copérnico es un placeholder, Min = cantidad pedida y Max = cantidad + lote sin pack, un solo pool de 585 sin seco/frío ni turno, usa solo el plan de hoy, no pone en 0/0 los SKUs fuera del plan, no está comparado contra la realidad y no hay soporte nocturno. Propuesta: mantener las reglas del CD 47 y correrlas dentro de la estructura automática de Global. Documento: "Replenishment Min/Max - Go/NoGo Decision" en la carpeta TURBO SUPPLY CHAIN ARGENTINA de Drive.
