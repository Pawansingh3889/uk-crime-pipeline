-- One-time Snowflake setup for the UK crime pipeline.
-- Run top to bottom in a Snowsight worksheet as a user with ACCOUNTADMIN.
-- Before running, paste your public key (without the BEGIN/END lines) into RSA_PUBLIC_KEY below.

-- Wear the "builder" badge, which is allowed to create machines, databases and tables.
USE ROLE SYSADMIN;

-- Create the smallest machine that runs queries; it switches itself off after 60 idle seconds so it stops costing money.
CREATE WAREHOUSE IF NOT EXISTS CRIME_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE;

-- Create the building (database) and a room inside it (schema) for raw, untouched data.
CREATE DATABASE IF NOT EXISTS CRIME_DB;
CREATE SCHEMA IF NOT EXISTS CRIME_DB.RAW;

-- Create the main shelf for crimes, with the same columns as the Postgres version so dbt works on both.
CREATE TABLE IF NOT EXISTS CRIME_DB.RAW.CRIMES (
  crime_id        STRING,
  fetch_month     STRING,
  city            STRING,
  category        STRING,
  location_type   STRING,
  latitude        STRING,
  longitude       STRING,
  street_name     STRING,
  outcome_status  STRING,
  month           STRING,
  loaded_at       TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Create the loading dock where the loader drops its files before they are unpacked.
CREATE STAGE IF NOT EXISTS CRIME_DB.RAW.CRIMES_STAGE FILE_FORMAT = (TYPE = JSON);

-- Wear the "security" badge, which is allowed to create badges and give out permissions.
USE ROLE SECURITYADMIN;

-- Make two staff badges: one for stocking the raw shelf, one for cooking the summary tables.
CREATE ROLE IF NOT EXISTS CRIME_LOADER;
CREATE ROLE IF NOT EXISTS CRIME_TRANSFORMER;
-- Let the builder badge see everything the two staff badges create.
GRANT ROLE CRIME_LOADER TO ROLE SYSADMIN;
GRANT ROLE CRIME_TRANSFORMER TO ROLE SYSADMIN;

-- Let both badges use the machine, enter the building and enter the raw room.
GRANT USAGE ON WAREHOUSE CRIME_WH TO ROLE CRIME_LOADER;
GRANT USAGE ON WAREHOUSE CRIME_WH TO ROLE CRIME_TRANSFORMER;
GRANT USAGE ON DATABASE CRIME_DB TO ROLE CRIME_LOADER;
GRANT USAGE ON DATABASE CRIME_DB TO ROLE CRIME_TRANSFORMER;
GRANT USAGE ON SCHEMA CRIME_DB.RAW TO ROLE CRIME_LOADER;
GRANT USAGE ON SCHEMA CRIME_DB.RAW TO ROLE CRIME_TRANSFORMER;

-- The loader badge can read and add to the raw shelf, use the loading dock, and make its own scratch table.
GRANT SELECT, INSERT ON TABLE CRIME_DB.RAW.CRIMES TO ROLE CRIME_LOADER;
GRANT READ, WRITE ON STAGE CRIME_DB.RAW.CRIMES_STAGE TO ROLE CRIME_LOADER;
GRANT CREATE TABLE ON SCHEMA CRIME_DB.RAW TO ROLE CRIME_LOADER;

-- The transformer badge can only read the raw shelf, and can build its own room for summary tables.
GRANT SELECT ON TABLE CRIME_DB.RAW.CRIMES TO ROLE CRIME_TRANSFORMER;
GRANT CREATE SCHEMA ON DATABASE CRIME_DB TO ROLE CRIME_TRANSFORMER;

-- Create a robot worker for the pipeline that logs in with a secret key file, never a password.
CREATE USER IF NOT EXISTS CRIME_PIPELINE
  TYPE = SERVICE
  DEFAULT_ROLE = CRIME_LOADER
  DEFAULT_WAREHOUSE = CRIME_WH
  RSA_PUBLIC_KEY = 'PASTE_PUBLIC_KEY_HERE';
-- Hand the robot worker both staff badges.
GRANT ROLE CRIME_LOADER TO USER CRIME_PIPELINE;
GRANT ROLE CRIME_TRANSFORMER TO USER CRIME_PIPELINE;

-- Wear the "owner" badge, the only one allowed to set spending limits.
USE ROLE ACCOUNTADMIN;
-- Set a monthly budget of 5 credits: warn at 80 percent, switch the machine off at 100 percent.
CREATE RESOURCE MONITOR IF NOT EXISTS CRIME_RM
  WITH CREDIT_QUOTA = 5 FREQUENCY = MONTHLY START_TIMESTAMP = IMMEDIATELY
  TRIGGERS ON 80 PERCENT DO NOTIFY
           ON 100 PERCENT DO SUSPEND;
-- Attach the budget to the machine.
ALTER WAREHOUSE CRIME_WH SET RESOURCE_MONITOR = CRIME_RM;
