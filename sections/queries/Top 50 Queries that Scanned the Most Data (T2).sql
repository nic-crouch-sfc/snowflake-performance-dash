
select
          
          QUERY_ID
          --reconfigure the url if your account is not in AWS US-West
         ,'https://app.snowflake.com/{params.snowflake.region}/{params.snowflake.account}/compute/history/queries/'||Q.QUERY_ID||'/detail?autoRefreshInSeconds=0' as QUERY_PROFILE_URL
         ,ROW_NUMBER() OVER(ORDER BY PARTITIONS_SCANNED DESC) as QUERY_ID_INT
         ,QUERY_TEXT
         ,TOTAL_ELAPSED_TIME/1000 AS QUERY_EXECUTION_TIME_SECONDS
         ,PARTITIONS_SCANNED
         ,PARTITIONS_TOTAL
        ,DIV0(PARTITIONS_SCANNED,PARTITIONS_TOTAL) PARTITIONS_PCT

from SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY Q
 where 1=1
  and TO_DATE(Q.START_TIME) >     DATEADD(month,-1,TO_DATE(CURRENT_TIMESTAMP())) 
    and TOTAL_ELAPSED_TIME > 0 --only get queries that actually used compute
    and ERROR_CODE iS NULL
    and PARTITIONS_SCANNED is not null
   
  order by  PARTITIONS_SCANNED desc
   
   LIMIT 50
   ;


