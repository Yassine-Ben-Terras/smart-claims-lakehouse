# Databricks notebook source
@dlt.table(
    name="claim_images_meta",
    comment="Raw accident claim images metadata ingested from ADLS Gen2", 
    table_properties={"quality": "bronze"}
)
def raw_images():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .load(f"/Volumes/smart_claims_dev/00_landing/claims/metadata"))
