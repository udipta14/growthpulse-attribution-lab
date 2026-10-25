# Databricks notebook source
# MAGIC %md
# MAGIC # GrowthPulse synthetic pipeline (Databricks adaptation)
# MAGIC
# MAGIC This notebook shows how the same synthetic campaign-touch schema can be
# MAGIC staged as Bronze, validated into Silver, and aggregated into a Gold table.
# MAGIC Replace the placeholder Volume path with a location you control. It has not
# MAGIC been run in a Databricks workspace as part of this portfolio demo.

# COMMAND ----------
from pyspark.sql import functions as F
from pyspark.sql.window import Window

SOURCE = "/Volumes/<catalog>/<schema>/<volume>/synthetic_touchpoints_sample.csv"
BRONZE = "<catalog>.<schema>.growthpulse_bronze_touchpoints"
SILVER = "<catalog>.<schema>.growthpulse_silver_touchpoints"
QUARANTINE = "<catalog>.<schema>.growthpulse_quarantine_touchpoints"
GOLD = "<catalog>.<schema>.growthpulse_daily_channel_metrics"

raw = (spark.read.option("header", True).option("inferSchema", True).csv(SOURCE)
       .withColumn("ingested_at", F.current_timestamp()))
raw.write.format("delta").mode("overwrite").saveAsTable(BRONZE)

# COMMAND ----------
required = ["event_id", "user_id", "event_date", "channel", "medium", "campaign"]
missing_required = None
for column in required:
    condition = F.col(column).isNull() | (F.trim(F.col(column).cast("string")) == "")
    missing_required = condition if missing_required is None else missing_required | condition

parsed = raw.withColumn("event_date_parsed", F.to_date("event_date", "yyyy-MM-dd"))
bad_date = F.col("event_date_parsed").isNull()
paid_missing_campaign = F.lower(F.col("channel")).isin("meta", "google", "tiktok", "affiliate") & (F.trim(F.col("campaign")) == "")
rank_window = Window.partitionBy("event_id").orderBy(F.col("ingested_at").asc())
deduped = parsed.withColumn("duplicate_rank", F.row_number().over(rank_window))
duplicate = F.col("duplicate_rank") > 1

quarantine = (deduped.filter(missing_required | bad_date | paid_missing_campaign | duplicate)
              .withColumn("quality_reason", F.when(missing_required, "missing_required")
                    .when(bad_date, "invalid_event_date")
                    .when(paid_missing_campaign, "paid_campaign_missing_utm")
                    .otherwise("duplicate_event_id")))
valid = deduped.filter(~(missing_required | bad_date | paid_missing_campaign | duplicate))

valid.write.format("delta").mode("overwrite").saveAsTable(SILVER)
quarantine.write.format("delta").mode("overwrite").saveAsTable(QUARANTINE)

# COMMAND ----------
gold = (valid.groupBy(F.to_date("event_date_parsed").alias("event_date"), "channel", "medium", "campaign")
        .agg(F.countDistinct("user_id").alias("users"), F.count("event_id").alias("touches")))
gold.write.format("delta").mode("overwrite").saveAsTable(GOLD)

# COMMAND ----------
display(gold.orderBy(F.desc("event_date")).limit(100))
display(quarantine.groupBy("quality_reason").count())
