# Testing System Plan

## 1. Overview

This document outlines the testing strategy for the DuckLake project. We will use a combination of unit tests, integration tests, and a Marimo notebook for exploratory testing and data generation.

## 2. Testing Levels

### 2.1. Unit Tests

- **Purpose:** To test individual components in isolation.
- **Tools:** `pytest` for the Python backend.
- **Scope:** Test individual functions and classes in the backend, such as API endpoint logic and data transformation functions.

### 2.2. Integration Tests

- **Purpose:** To test the interaction between different components of the system.
- **Tools:** `pytest` with `httpx` for making requests to the backend API.
- **Scope:** Test the end-to-end flow of data operations, from the API endpoint to the database and object storage.

### 2.3. End-to-End (E2E) Tests

- **Purpose:** To test the entire system from the user's perspective.
- **Tools:** A browser automation framework like Cypress or Playwright.
- **Scope:** Test user workflows in the frontend, such as searching for data, uploading files, and viewing lineage information.

## 3. Marimo Notebook

- **Purpose:** To provide an interactive environment for:
    - **Test Data Generation:** Creating test data in various formats (CSV, Parquet, etc.).
    - **Exploratory Testing:** Manually testing the API and inspecting the state of the system.
    - **Data Analysis:** Analyzing the data stored in the DuckLake.
- **Setup:** The Marimo notebook will be pre-configured with the necessary libraries and connection details to interact with the DuckLake system.
