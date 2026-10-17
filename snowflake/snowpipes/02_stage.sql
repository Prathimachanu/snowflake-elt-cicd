-- {{ENV}} and {{S3_BUCKET}} are replaced by scripts/deploy.py
CREATE STAGE IF NOT EXISTS RAW.WEATHER_STAGE
  URL = 's3://{{S3_BUCKET}}/{{ENV}}/weather/'
  STORAGE_INTEGRATION = S3_INT
  FILE_FORMAT = RAW.JSON_FF;
