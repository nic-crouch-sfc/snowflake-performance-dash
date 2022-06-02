
SHOW STREAMS;

select * 
from table(result_scan(last_query_id())) 
where "stale" = true;


