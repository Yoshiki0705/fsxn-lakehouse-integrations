-- =============================================================================
-- 02 - External Stage pointing to FSxN via S3 Access Point
-- =============================================================================
-- Creates External Stages for each medallion layer (bronze/silver/gold).
-- Stages use the Storage Integration created in 01_storage_integration.sql.
-- =============================================================================

USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;

-- Create database for FSxN lakehouse data
CREATE DATABASE IF NOT EXISTS FSXN_LAKEHOUSE
  COMMENT = 'FSx for NetApp ONTAP Lakehouse data via S3 Access Point';

USE DATABASE FSXN_LAKEHOUSE;

-- Create schemas for medallion architecture
CREATE SCHEMA IF NOT EXISTS BRONZE COMMENT = 'Raw ingested data from FSxN';
CREATE SCHEMA IF NOT EXISTS SILVER COMMENT = 'Cleaned and transformed data';
CREATE SCHEMA IF NOT EXISTS GOLD COMMENT = 'Business-ready aggregates';

-- =============================================================================
-- External Stage - Root (all data)
-- =============================================================================
CREATE OR REPLACE STAGE FSXN_LAKEHOUSE.PUBLIC.FSXN_ROOT_STAGE
  STORAGE_INTEGRATION = fsxn_storage_integration
  URL = 's3://<S3AccessPointAlias>/'
  COMMENT = 'Root stage for FSxN volume via S3 Access Point';

-- =============================================================================
-- External Stage - Bronze Layer
-- =============================================================================
CREATE OR REPLACE STAGE FSXN_LAKEHOUSE.BRONZE.FSXN_BRONZE_STAGE
  STORAGE_INTEGRATION = fsxn_storage_integration
  URL = 's3://<S3AccessPointAlias>/bronze/'
  COMMENT = 'Bronze layer - raw data on FSxN';

-- =============================================================================
-- External Stage - Silver Layer
-- =============================================================================
CREATE OR REPLACE STAGE FSXN_LAKEHOUSE.SILVER.FSXN_SILVER_STAGE
  STORAGE_INTEGRATION = fsxn_storage_integration
  URL = 's3://<S3AccessPointAlias>/silver/'
  COMMENT = 'Silver layer - cleaned data on FSxN';

-- =============================================================================
-- External Stage - Gold Layer
-- =============================================================================
CREATE OR REPLACE STAGE FSXN_LAKEHOUSE.GOLD.FSXN_GOLD_STAGE
  STORAGE_INTEGRATION = fsxn_storage_integration
  URL = 's3://<S3AccessPointAlias>/gold/'
  COMMENT = 'Gold layer - business-ready data on FSxN';

-- =============================================================================
-- Validate Stages
-- =============================================================================

-- List files in bronze stage
LIST @FSXN_LAKEHOUSE.BRONZE.FSXN_BRONZE_STAGE;

-- List files in silver stage
LIST @FSXN_LAKEHOUSE.SILVER.FSXN_SILVER_STAGE;

-- List files in gold stage
LIST @FSXN_LAKEHOUSE.GOLD.FSXN_GOLD_STAGE;
