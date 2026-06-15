# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Data repository for **Vivero Don Juan**, a plant nursery. Contains the product catalog and plant master data in CSV format. All data is in Spanish.

## Data Model

Two CSV files with a one-to-many relationship:

**`descripcion.csv`** — Plant master records (one row per plant species/cultivar)
- Key fields: `plant_id`, `nombre_cientifico`, `nombre_comun`, `categoria`, `exposicion_solar`, `riego`, `crecimiento`, `facilidad_cultivo`, `uso_recomendado`, `resistencia_frio`, `descripcion`, `embedding`, `created_at`
- The `embedding` column holds vector embeddings for semantic/AI search

**`catalogo.csv`** — Product variants (one-to-many from `descripcion`)
- Key fields: `variante_id`, `plant_id` (FK → `descripcion.plant_id`), `nombre_comun`, `nombre_cientifico`, `tamano_envase_lts` (container size in liters), `precio`, `stock`, `elegibilidad`
- Each plant can have multiple variants differing in container size and price

Prices are in Argentine pesos (ARS). Eligibility (`elegibilidad`) is rated 1–4.
